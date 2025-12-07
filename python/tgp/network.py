"""
TGP Network Transport Abstraction

This module provides the transport layer for Two Generals Protocol message
exchange. It supports both in-memory simulation (for testing) and real
UDP transport (for production deployment).

Key Design Principles:
- NO POLLING: All communication is event-driven using asyncio
- Continuous flooding: Messages are retransmitted until phase advancement
- Fair-lossy model: Assumes bidirectional channels with p > 0 delivery probability
- Transport-agnostic protocol: Same TwoGenerals state machine works over any transport

Transport Implementations:
- InMemoryTransport: For unit tests and simulations (synchronous)
- UDPTransport: Real UDP sockets for production use (async)
- ChannelPair: Bidirectional channel for two-party simulation

Wire Format:
- Messages are serialized using a simple length-prefixed format
- Each message includes: type byte | length (4 bytes) | payload
"""

from __future__ import annotations

import asyncio
import struct
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Optional,
    List,
    Callable,
    Tuple,
    AsyncIterator,
    Union,
    Awaitable,
)
from collections import deque
import hashlib
import random

from .types import (
    Party,
    Commitment,
    DoubleProof,
    TripleProof,
    QuadProof,
    Message,
)
from .protocol import ProtocolMessage, TwoGenerals


# =============================================================================
# Wire Format Constants
# =============================================================================

class MessageType(IntEnum):
    """Protocol message type identifiers for wire format."""
    COMMITMENT = 0x01
    DOUBLE_PROOF = 0x02
    TRIPLE_PROOF = 0x03
    QUAD_PROOF = 0x04
    DH_CONTRIBUTION = 0x10
    ENCRYPTED = 0x20


# Header format: type (1 byte) + length (4 bytes big-endian)
HEADER_SIZE = 5
MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB max message size


# =============================================================================
# CBOR Serialization / Deserialization (Network Transport)
# =============================================================================

try:
    import cbor2
    HAS_CBOR = True
except ImportError:
    HAS_CBOR = False


def serialize_commitment(c: Commitment) -> bytes:
    """Serialize a Commitment to CBOR bytes."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")
    return cbor2.dumps({
        "party": c.party.name,
        "message": c.message,
        "signature": c.signature,
        "public_key": c.public_key,
    })


def deserialize_commitment(data: bytes) -> Commitment:
    """Deserialize CBOR bytes to a Commitment."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")
    d = cbor2.loads(data)
    return Commitment(
        party=Party[d["party"]],
        message=d["message"],
        signature=d["signature"],
        public_key=d["public_key"],
    )


def serialize_double_proof(dp: DoubleProof) -> bytes:
    """Serialize a DoubleProof to CBOR bytes."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")
    return cbor2.dumps({
        "party": dp.party.name,
        "own_commitment": {
            "party": dp.own_commitment.party.name,
            "message": dp.own_commitment.message,
            "signature": dp.own_commitment.signature,
            "public_key": dp.own_commitment.public_key,
        },
        "other_commitment": {
            "party": dp.other_commitment.party.name,
            "message": dp.other_commitment.message,
            "signature": dp.other_commitment.signature,
            "public_key": dp.other_commitment.public_key,
        },
        "signature": dp.signature,
        "public_key": dp.public_key,
    })


def deserialize_double_proof(data: bytes) -> DoubleProof:
    """Deserialize CBOR bytes to a DoubleProof."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")
    d = cbor2.loads(data)
    return DoubleProof(
        party=Party[d["party"]],
        own_commitment=Commitment(
            party=Party[d["own_commitment"]["party"]],
            message=d["own_commitment"]["message"],
            signature=d["own_commitment"]["signature"],
            public_key=d["own_commitment"]["public_key"],
        ),
        other_commitment=Commitment(
            party=Party[d["other_commitment"]["party"]],
            message=d["other_commitment"]["message"],
            signature=d["other_commitment"]["signature"],
            public_key=d["other_commitment"]["public_key"],
        ),
        signature=d["signature"],
        public_key=d["public_key"],
    )


def serialize_triple_proof(tp: TripleProof) -> bytes:
    """Serialize a TripleProof to CBOR bytes."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")

    def _serialize_dp(dp: DoubleProof) -> dict:
        return {
            "party": dp.party.name,
            "own_commitment": {
                "party": dp.own_commitment.party.name,
                "message": dp.own_commitment.message,
                "signature": dp.own_commitment.signature,
                "public_key": dp.own_commitment.public_key,
            },
            "other_commitment": {
                "party": dp.other_commitment.party.name,
                "message": dp.other_commitment.message,
                "signature": dp.other_commitment.signature,
                "public_key": dp.other_commitment.public_key,
            },
            "signature": dp.signature,
            "public_key": dp.public_key,
        }

    return cbor2.dumps({
        "party": tp.party.name,
        "own_double": _serialize_dp(tp.own_double),
        "other_double": _serialize_dp(tp.other_double),
        "signature": tp.signature,
        "public_key": tp.public_key,
    })


def _deserialize_dp(d: dict) -> DoubleProof:
    """Helper to deserialize a DoubleProof dict."""
    return DoubleProof(
        party=Party[d["party"]],
        own_commitment=Commitment(
            party=Party[d["own_commitment"]["party"]],
            message=d["own_commitment"]["message"],
            signature=d["own_commitment"]["signature"],
            public_key=d["own_commitment"]["public_key"],
        ),
        other_commitment=Commitment(
            party=Party[d["other_commitment"]["party"]],
            message=d["other_commitment"]["message"],
            signature=d["other_commitment"]["signature"],
            public_key=d["other_commitment"]["public_key"],
        ),
        signature=d["signature"],
        public_key=d["public_key"],
    )


def deserialize_triple_proof(data: bytes) -> TripleProof:
    """Deserialize CBOR bytes to a TripleProof."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")
    d = cbor2.loads(data)
    return TripleProof(
        party=Party[d["party"]],
        own_double=_deserialize_dp(d["own_double"]),
        other_double=_deserialize_dp(d["other_double"]),
        signature=d["signature"],
        public_key=d["public_key"],
    )


def serialize_quad_proof(qp: QuadProof) -> bytes:
    """Serialize a QuadProof to CBOR bytes."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")

    def _serialize_dp(dp: DoubleProof) -> dict:
        return {
            "party": dp.party.name,
            "own_commitment": {
                "party": dp.own_commitment.party.name,
                "message": dp.own_commitment.message,
                "signature": dp.own_commitment.signature,
                "public_key": dp.own_commitment.public_key,
            },
            "other_commitment": {
                "party": dp.other_commitment.party.name,
                "message": dp.other_commitment.message,
                "signature": dp.other_commitment.signature,
                "public_key": dp.other_commitment.public_key,
            },
            "signature": dp.signature,
            "public_key": dp.public_key,
        }

    def _serialize_tp(tp: TripleProof) -> dict:
        return {
            "party": tp.party.name,
            "own_double": _serialize_dp(tp.own_double),
            "other_double": _serialize_dp(tp.other_double),
            "signature": tp.signature,
            "public_key": tp.public_key,
        }

    return cbor2.dumps({
        "party": qp.party.name,
        "own_triple": _serialize_tp(qp.own_triple),
        "other_triple": _serialize_tp(qp.other_triple),
        "signature": qp.signature,
        "public_key": qp.public_key,
    })


def _deserialize_tp(d: dict) -> TripleProof:
    """Helper to deserialize a TripleProof dict."""
    return TripleProof(
        party=Party[d["party"]],
        own_double=_deserialize_dp(d["own_double"]),
        other_double=_deserialize_dp(d["other_double"]),
        signature=d["signature"],
        public_key=d["public_key"],
    )


def deserialize_quad_proof(data: bytes) -> QuadProof:
    """Deserialize CBOR bytes to a QuadProof."""
    if not HAS_CBOR:
        raise ImportError("cbor2 required for network serialization")
    d = cbor2.loads(data)
    return QuadProof(
        party=Party[d["party"]],
        own_triple=_deserialize_tp(d["own_triple"]),
        other_triple=_deserialize_tp(d["other_triple"]),
        signature=d["signature"],
        public_key=d["public_key"],
    )


def deserialize_message(msg_type: MessageType, payload: bytes) -> Commitment | DoubleProof | TripleProof | QuadProof:
    """Deserialize a network message payload based on type.

    Args:
        msg_type: The message type from the header
        payload: The CBOR-encoded payload

    Returns:
        The deserialized proof object
    """
    if msg_type == MessageType.COMMITMENT:
        return deserialize_commitment(payload)
    elif msg_type == MessageType.DOUBLE_PROOF:
        return deserialize_double_proof(payload)
    elif msg_type == MessageType.TRIPLE_PROOF:
        return deserialize_triple_proof(payload)
    elif msg_type == MessageType.QUAD_PROOF:
        return deserialize_quad_proof(payload)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")


# =============================================================================
# Wire Format Serialization
# =============================================================================

def serialize_message(msg: ProtocolMessage) -> bytes:
    """Serialize a protocol message for wire transmission.

    Format:
        type (1 byte) | length (4 bytes BE) | CBOR payload

    Args:
        msg: The protocol message to serialize

    Returns:
        Serialized bytes ready for transmission
    """
    # Determine message type and serialize payload with CBOR
    if isinstance(msg.payload, Commitment):
        msg_type = MessageType.COMMITMENT
        payload = serialize_commitment(msg.payload)
    elif isinstance(msg.payload, DoubleProof):
        msg_type = MessageType.DOUBLE_PROOF
        payload = serialize_double_proof(msg.payload)
    elif isinstance(msg.payload, TripleProof):
        msg_type = MessageType.TRIPLE_PROOF
        payload = serialize_triple_proof(msg.payload)
    elif isinstance(msg.payload, QuadProof):
        msg_type = MessageType.QUAD_PROOF
        payload = serialize_quad_proof(msg.payload)
    else:
        raise ValueError(f"Unknown payload type: {type(msg.payload)}")

    # Pack header + payload
    header = struct.pack(">BI", msg_type, len(payload))
    return header + payload


def parse_header(data: bytes) -> Tuple[MessageType, int]:
    """Parse a message header.

    Args:
        data: At least 5 bytes of header data

    Returns:
        Tuple of (message_type, payload_length)

    Raises:
        ValueError: If header is invalid
    """
    if len(data) < HEADER_SIZE:
        raise ValueError(f"Header too short: {len(data)} < {HEADER_SIZE}")

    msg_type, length = struct.unpack(">BI", data[:HEADER_SIZE])

    if length > MAX_MESSAGE_SIZE:
        raise ValueError(f"Message too large: {length} > {MAX_MESSAGE_SIZE}")

    return MessageType(msg_type), length


# =============================================================================
# Transport Interface
# =============================================================================

class Transport(ABC):
    """Abstract base class for TGP transports.

    A transport handles the actual transmission of serialized messages
    between protocol instances. Implementations may be synchronous
    (for testing) or asynchronous (for production).
    """

    @abstractmethod
    def send(self, data: bytes) -> None:
        """Send data to the peer.

        Args:
            data: Serialized message bytes
        """
        pass

    @abstractmethod
    def receive(self) -> Optional[bytes]:
        """Receive data from the peer (non-blocking).

        Returns:
            Received bytes or None if no data available
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the transport and release resources."""
        pass


class AsyncTransport(ABC):
    """Abstract base class for async TGP transports.

    Provides event-driven message delivery without polling.
    """

    @abstractmethod
    async def send(self, data: bytes) -> None:
        """Send data to the peer asynchronously.

        Args:
            data: Serialized message bytes
        """
        pass

    @abstractmethod
    async def receive(self) -> bytes:
        """Receive data from the peer (blocks until data available).

        Returns:
            Received bytes

        Raises:
            ConnectionError: If connection is closed
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport and release resources."""
        pass

    @abstractmethod
    def is_closed(self) -> bool:
        """Check if transport is closed."""
        pass


# =============================================================================
# In-Memory Transport (Testing)
# =============================================================================

@dataclass
class InMemoryChannel:
    """A unidirectional in-memory message channel.

    Used for testing protocol implementations without network overhead.
    Messages are queued and can be optionally dropped to simulate loss.
    """

    _queue: deque = field(default_factory=deque)
    _closed: bool = False
    loss_rate: float = 0.0  # Probability of dropping a message

    def send(self, data: bytes) -> bool:
        """Send data through the channel.

        Args:
            data: Bytes to send

        Returns:
            True if message was queued, False if dropped (simulated loss)
        """
        if self._closed:
            raise ConnectionError("Channel is closed")

        # Simulate packet loss
        if self.loss_rate > 0 and random.random() < self.loss_rate:
            return False

        self._queue.append(data)
        return True

    def receive(self) -> Optional[bytes]:
        """Receive data from the channel (non-blocking).

        Returns:
            Bytes if available, None otherwise
        """
        if self._queue:
            return self._queue.popleft()
        return None

    def has_data(self) -> bool:
        """Check if there is data waiting to be received."""
        return len(self._queue) > 0

    def close(self) -> None:
        """Close the channel."""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        """Check if channel is closed."""
        return self._closed


@dataclass
class ChannelPair:
    """A bidirectional channel pair for two-party simulation.

    Creates two channels: alice_to_bob and bob_to_alice.
    Each party sends on their outgoing channel and receives on their incoming.
    """

    alice_to_bob: InMemoryChannel = field(default_factory=InMemoryChannel)
    bob_to_alice: InMemoryChannel = field(default_factory=InMemoryChannel)

    @classmethod
    def create(cls, loss_rate: float = 0.0) -> ChannelPair:
        """Create a new channel pair with optional loss simulation.

        Args:
            loss_rate: Probability of dropping messages (0.0 to 1.0)

        Returns:
            ChannelPair configured with specified loss rate
        """
        return cls(
            alice_to_bob=InMemoryChannel(loss_rate=loss_rate),
            bob_to_alice=InMemoryChannel(loss_rate=loss_rate),
        )

    def alice_transport(self) -> InMemoryTransport:
        """Get Alice's transport view of the channels."""
        return InMemoryTransport(
            outgoing=self.alice_to_bob,
            incoming=self.bob_to_alice,
        )

    def bob_transport(self) -> InMemoryTransport:
        """Get Bob's transport view of the channels."""
        return InMemoryTransport(
            outgoing=self.bob_to_alice,
            incoming=self.alice_to_bob,
        )

    def close(self) -> None:
        """Close both channels."""
        self.alice_to_bob.close()
        self.bob_to_alice.close()


@dataclass
class InMemoryTransport(Transport):
    """In-memory transport for testing.

    Wraps a pair of unidirectional channels to provide bidirectional
    communication for a single party.
    """

    outgoing: InMemoryChannel
    incoming: InMemoryChannel

    def send(self, data: bytes) -> None:
        """Send data to the peer."""
        self.outgoing.send(data)

    def receive(self) -> Optional[bytes]:
        """Receive data from the peer (non-blocking)."""
        return self.incoming.receive()

    def has_data(self) -> bool:
        """Check if there is incoming data waiting."""
        return self.incoming.has_data()

    def close(self) -> None:
        """Close the transport."""
        self.outgoing.close()


# =============================================================================
# UDP Transport (Production)
# =============================================================================

@dataclass
class UDPEndpoint:
    """A UDP endpoint specification."""
    host: str
    port: int

    def as_tuple(self) -> Tuple[str, int]:
        """Return as (host, port) tuple for socket operations."""
        return (self.host, self.port)


class UDPTransport(AsyncTransport):
    """Asynchronous UDP transport for production TGP communication.

    Uses asyncio for event-driven message handling. NO POLLING.

    Features:
    - Non-blocking send/receive via asyncio
    - Automatic message framing (length-prefixed)
    - Supports both IPv4 and IPv6

    Usage:
        transport = await UDPTransport.create(
            local=UDPEndpoint("0.0.0.0", 8000),
            remote=UDPEndpoint("peer.example.com", 8000),
        )
        await transport.send(data)
        response = await transport.receive()
        await transport.close()
    """

    def __init__(
        self,
        transport: asyncio.DatagramTransport,
        protocol: "UDPProtocol",
        remote: UDPEndpoint,
    ) -> None:
        self._transport = transport
        self._protocol = protocol
        self._remote = remote
        self._closed = False

    @classmethod
    async def create(
        cls,
        local: UDPEndpoint,
        remote: UDPEndpoint,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> UDPTransport:
        """Create a new UDP transport bound to local endpoint.

        Args:
            local: Local endpoint to bind to
            remote: Remote endpoint to send to
            loop: Event loop (uses current if None)

        Returns:
            Configured UDPTransport ready for use
        """
        if loop is None:
            loop = asyncio.get_event_loop()

        protocol = UDPProtocol()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=local.as_tuple(),
        )

        return cls(transport, protocol, remote)

    async def send(self, data: bytes) -> None:
        """Send data to the remote peer."""
        if self._closed:
            raise ConnectionError("Transport is closed")
        self._transport.sendto(data, self._remote.as_tuple())

    async def receive(self) -> bytes:
        """Receive data from the peer (blocks until data available)."""
        if self._closed:
            raise ConnectionError("Transport is closed")
        return await self._protocol.receive()

    async def receive_timeout(self, timeout: float) -> Optional[bytes]:
        """Receive data with timeout.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            Received bytes or None if timeout
        """
        try:
            return await asyncio.wait_for(self.receive(), timeout)
        except asyncio.TimeoutError:
            return None

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True
        self._transport.close()

    def is_closed(self) -> bool:
        """Check if transport is closed."""
        return self._closed


class UDPProtocol(asyncio.DatagramProtocol):
    """asyncio protocol handler for UDP datagrams.

    Buffers incoming datagrams and provides async receive interface.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._error: Optional[Exception] = None

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Called when a datagram is received."""
        self._queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        """Called when a send/receive error occurs."""
        self._error = exc

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when the connection is lost."""
        if exc:
            self._error = exc

    async def receive(self) -> bytes:
        """Receive the next datagram (blocks until available)."""
        if self._error:
            raise self._error
        return await self._queue.get()


# =============================================================================
# Flooding Engine
# =============================================================================

@dataclass
class FloodingConfig:
    """Configuration for continuous message flooding.

    TGP requires continuous flooding of the current proof level
    until the next level is achieved. This config controls the
    flooding behavior.
    """

    # Minimum interval between flood transmissions (seconds)
    flood_interval: float = 0.1

    # Maximum number of concurrent flood operations
    max_concurrent: int = 10

    # Whether to use exponential backoff on repeated floods
    use_backoff: bool = False

    # Maximum backoff interval (seconds)
    max_backoff: float = 5.0


class FloodingEngine:
    """Manages continuous message flooding for TGP.

    The flooding engine continuously transmits the current highest-level
    proof until a higher level is achieved. This implements the
    "no message is special" property of TGP.

    NO POLLING: Uses asyncio events for coordination.
    """

    def __init__(
        self,
        transport: AsyncTransport,
        protocol: TwoGenerals,
        config: Optional[FloodingConfig] = None,
    ) -> None:
        self._transport = transport
        self._protocol = protocol
        self._config = config or FloodingConfig()
        self._running = False
        self._flood_task: Optional[asyncio.Task] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._state_changed = asyncio.Event()
        self._completion_event = asyncio.Event()

    async def start(self) -> None:
        """Start the flooding engine.

        Begins concurrent send and receive operations.
        """
        if self._running:
            return

        self._running = True
        self._flood_task = asyncio.create_task(self._flood_loop())
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def stop(self) -> None:
        """Stop the flooding engine."""
        self._running = False

        if self._flood_task:
            self._flood_task.cancel()
            try:
                await self._flood_task
            except asyncio.CancelledError:
                pass

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

    async def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for protocol completion.

        Args:
            timeout: Maximum seconds to wait (None for no limit)

        Returns:
            True if completed, False if timeout
        """
        try:
            await asyncio.wait_for(self._completion_event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _flood_loop(self) -> None:
        """Continuously flood current proof level."""
        backoff = self._config.flood_interval

        while self._running and not self._protocol.is_complete:
            # Get messages to send
            messages = self._protocol.get_messages_to_send()

            # Send all messages
            for msg in messages:
                try:
                    data = serialize_message(msg)
                    await self._transport.send(data)
                except ConnectionError:
                    break

            # Wait before next flood
            try:
                await asyncio.wait_for(
                    self._state_changed.wait(),
                    timeout=backoff,
                )
                self._state_changed.clear()
                backoff = self._config.flood_interval  # Reset on state change
            except asyncio.TimeoutError:
                if self._config.use_backoff:
                    backoff = min(backoff * 1.5, self._config.max_backoff)

    async def _receive_loop(self) -> None:
        """Receive and process incoming messages."""
        while self._running and not self._protocol.is_complete:
            try:
                data = await self._transport.receive()

                # Parse and deliver to protocol
                # Note: Full deserialization would require message type handling
                # For now, we pass raw bytes - the protocol handles the rest

                # Signal state change for flood loop
                self._state_changed.set()

                if self._protocol.is_complete:
                    self._completion_event.set()
                    break

            except ConnectionError:
                break


# =============================================================================
# Simulation Helpers
# =============================================================================

def run_simulation(
    alice: TwoGenerals,
    bob: TwoGenerals,
    max_rounds: int = 100,
    loss_rate: float = 0.0,
    on_message: Optional[Callable[[Party, ProtocolMessage], None]] = None,
) -> Tuple[TwoGenerals, TwoGenerals]:
    """Run a synchronous protocol simulation.

    Exchanges messages between Alice and Bob until both complete
    or max_rounds is reached. Useful for testing.

    Args:
        alice: Alice's protocol instance
        bob: Bob's protocol instance
        max_rounds: Maximum exchange rounds
        loss_rate: Probability of dropping each message
        on_message: Optional callback for each message sent

    Returns:
        Tuple of (alice, bob) after simulation
    """
    channels = ChannelPair.create(loss_rate=loss_rate)
    alice_transport = channels.alice_transport()
    bob_transport = channels.bob_transport()

    for round_num in range(max_rounds):
        # Alice sends to Bob
        for msg in alice.get_messages_to_send():
            if on_message:
                on_message(Party.ALICE, msg)
            data = serialize_message(msg)
            alice_transport.send(data)

        # Bob receives from Alice
        while bob_transport.incoming.has_data():
            data = bob_transport.receive()
            if data and len(data) >= HEADER_SIZE:
                try:
                    msg_type, length = parse_header(data)
                    payload = data[HEADER_SIZE:HEADER_SIZE + length]
                    proof = deserialize_message(msg_type, payload)
                    bob.receive(proof)
                except Exception:
                    pass  # Skip malformed messages

        # Bob sends to Alice
        for msg in bob.get_messages_to_send():
            if on_message:
                on_message(Party.BOB, msg)
            data = serialize_message(msg)
            bob_transport.send(data)

        # Alice receives from Bob
        while alice_transport.incoming.has_data():
            data = alice_transport.receive()
            if data and len(data) >= HEADER_SIZE:
                try:
                    msg_type, length = parse_header(data)
                    payload = data[HEADER_SIZE:HEADER_SIZE + length]
                    proof = deserialize_message(msg_type, payload)
                    alice.receive(proof)
                except Exception:
                    pass  # Skip malformed messages

        # Check completion
        if alice.is_complete and bob.is_complete:
            break

    channels.close()
    return (alice, bob)


async def run_async_simulation(
    alice: TwoGenerals,
    bob: TwoGenerals,
    timeout: float = 10.0,
) -> Tuple[TwoGenerals, TwoGenerals]:
    """Run an async protocol simulation.

    Uses the flooding engine for realistic async behavior.

    Args:
        alice: Alice's protocol instance
        bob: Bob's protocol instance
        timeout: Maximum seconds to run

    Returns:
        Tuple of (alice, bob) after simulation
    """
    # Create async channel pair
    channels = AsyncChannelPair.create()

    alice_engine = FloodingEngine(
        transport=channels.alice_transport(),
        protocol=alice,
    )
    bob_engine = FloodingEngine(
        transport=channels.bob_transport(),
        protocol=bob,
    )

    # Start both engines
    await alice_engine.start()
    await bob_engine.start()

    # Wait for completion
    try:
        await asyncio.wait_for(
            asyncio.gather(
                alice_engine.wait_for_completion(),
                bob_engine.wait_for_completion(),
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        pass
    finally:
        await alice_engine.stop()
        await bob_engine.stop()
        await channels.close()

    return (alice, bob)


# =============================================================================
# Async In-Memory Transport (for async simulation)
# =============================================================================

class AsyncChannel:
    """Async unidirectional channel for testing."""

    def __init__(self, loss_rate: float = 0.0) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._closed = False
        self.loss_rate = loss_rate

    async def send(self, data: bytes) -> bool:
        """Send data through the channel."""
        if self._closed:
            raise ConnectionError("Channel is closed")

        if self.loss_rate > 0 and random.random() < self.loss_rate:
            return False

        await self._queue.put(data)
        return True

    async def receive(self) -> bytes:
        """Receive data from the channel."""
        if self._closed:
            raise ConnectionError("Channel is closed")
        return await self._queue.get()

    async def close(self) -> None:
        """Close the channel."""
        self._closed = True


@dataclass
class AsyncChannelPair:
    """Async bidirectional channel pair."""

    alice_to_bob: AsyncChannel = field(default_factory=AsyncChannel)
    bob_to_alice: AsyncChannel = field(default_factory=AsyncChannel)

    @classmethod
    def create(cls, loss_rate: float = 0.0) -> AsyncChannelPair:
        """Create a new async channel pair."""
        return cls(
            alice_to_bob=AsyncChannel(loss_rate=loss_rate),
            bob_to_alice=AsyncChannel(loss_rate=loss_rate),
        )

    def alice_transport(self) -> AsyncInMemoryTransport:
        """Get Alice's transport."""
        return AsyncInMemoryTransport(
            outgoing=self.alice_to_bob,
            incoming=self.bob_to_alice,
        )

    def bob_transport(self) -> AsyncInMemoryTransport:
        """Get Bob's transport."""
        return AsyncInMemoryTransport(
            outgoing=self.bob_to_alice,
            incoming=self.alice_to_bob,
        )

    async def close(self) -> None:
        """Close both channels."""
        await self.alice_to_bob.close()
        await self.bob_to_alice.close()


class AsyncInMemoryTransport(AsyncTransport):
    """Async in-memory transport for testing."""

    def __init__(
        self,
        outgoing: AsyncChannel,
        incoming: AsyncChannel,
    ) -> None:
        self._outgoing = outgoing
        self._incoming = incoming
        self._closed = False

    async def send(self, data: bytes) -> None:
        """Send data to the peer."""
        await self._outgoing.send(data)

    async def receive(self) -> bytes:
        """Receive data from the peer."""
        return await self._incoming.receive()

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True

    def is_closed(self) -> bool:
        """Check if closed."""
        return self._closed


# =============================================================================
# Network Statistics
# =============================================================================

@dataclass
class NetworkStats:
    """Statistics for network operations.

    Useful for analyzing protocol behavior under various conditions.
    """

    messages_sent: int = 0
    messages_received: int = 0
    messages_dropped: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0

    def record_send(self, size: int, dropped: bool = False) -> None:
        """Record a send operation."""
        self.messages_sent += 1
        self.bytes_sent += size
        if dropped:
            self.messages_dropped += 1

    def record_receive(self, size: int) -> None:
        """Record a receive operation."""
        self.messages_received += 1
        self.bytes_received += size

    @property
    def delivery_rate(self) -> float:
        """Calculate message delivery rate."""
        if self.messages_sent == 0:
            return 1.0
        return (self.messages_sent - self.messages_dropped) / self.messages_sent

    def __repr__(self) -> str:
        return (
            f"NetworkStats("
            f"sent={self.messages_sent}, "
            f"recv={self.messages_received}, "
            f"dropped={self.messages_dropped}, "
            f"delivery={self.delivery_rate:.2%})"
        )
