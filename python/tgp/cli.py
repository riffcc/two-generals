#!/usr/bin/env python3
"""
TGP Command-Line Interface

Run Two Generals Protocol nodes for distributed coordination.

Usage:
    # Generate a keypair
    python -m tgp.cli keygen --output alice.key

    # Run as initiator (Alice)
    python -m tgp.cli run \
        --role initiator \
        --key alice.key \
        --peer-key bob.pub \
        --local 0.0.0.0:8000 \
        --remote 10.7.1.37:8000

    # Run as responder (Bob)
    python -m tgp.cli run \
        --role responder \
        --key bob.key \
        --peer-key alice.pub \
        --local 0.0.0.0:8000 \
        --remote 10.8.1.37:8000
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .crypto import KeyPair, PublicKey
from .types import Party
from .protocol import TwoGenerals, ProtocolState, ProtocolMessage
from .network import (
    UDPTransport,
    UDPEndpoint,
    FloodingEngine,
    FloodingConfig,
    serialize_message,
    deserialize_message,
    parse_header,
    MessageType,
    HEADER_SIZE,
)


# =============================================================================
# Key Management
# =============================================================================


def save_keypair(keypair: KeyPair, path: Path) -> None:
    """Save keypair to file (JSON format with base64 encoding)."""
    data = {
        "type": "tgp-keypair",
        "version": 1,
        "seed": base64.b64encode(keypair.to_seed()).decode("ascii"),
        "public_key": base64.b64encode(keypair.public_key.to_bytes()).decode("ascii"),
    }
    path.write_text(json.dumps(data, indent=2))
    print(f"Keypair saved to: {path}")
    print(f"Public key: {data['public_key']}")


def load_keypair(path: Path) -> KeyPair:
    """Load keypair from file."""
    data = json.loads(path.read_text())
    if data.get("type") != "tgp-keypair":
        raise ValueError(f"Invalid keypair file: {path}")
    seed = base64.b64decode(data["seed"])
    return KeyPair.from_seed(seed)


def save_public_key(public_key: PublicKey, path: Path) -> None:
    """Save public key to file."""
    data = {
        "type": "tgp-public-key",
        "version": 1,
        "public_key": base64.b64encode(public_key.to_bytes()).decode("ascii"),
    }
    path.write_text(json.dumps(data, indent=2))
    print(f"Public key saved to: {path}")


def load_public_key(path: Path) -> PublicKey:
    """Load public key from file or base64 string."""
    text = path.read_text().strip()

    # Try JSON format first
    try:
        data = json.loads(text)
        if "public_key" in data:
            return PublicKey.from_bytes(base64.b64decode(data["public_key"]))
    except json.JSONDecodeError:
        pass

    # Try raw base64
    try:
        return PublicKey.from_bytes(base64.b64decode(text))
    except Exception:
        pass

    raise ValueError(f"Could not parse public key from: {path}")


def parse_endpoint(s: str) -> UDPEndpoint:
    """Parse 'host:port' string into UDPEndpoint."""
    if ":" not in s:
        raise ValueError(f"Invalid endpoint format: {s} (expected host:port)")

    # Handle IPv6 addresses like [::1]:8000
    if s.startswith("["):
        bracket_end = s.index("]")
        host = s[1:bracket_end]
        port = int(s[bracket_end + 2:])
    else:
        host, port_str = s.rsplit(":", 1)
        port = int(port_str)

    return UDPEndpoint(host=host, port=port)


# =============================================================================
# Protocol Runner
# =============================================================================


@dataclass
class NodeConfig:
    """Configuration for running a TGP node."""
    role: str  # "initiator" or "responder"
    keypair: KeyPair
    peer_public_key: PublicKey
    local_endpoint: UDPEndpoint
    remote_endpoint: UDPEndpoint
    timeout: float = 30.0
    flood_interval: float = 0.1
    verbose: bool = False


class TGPNode:
    """
    A TGP node that can run the protocol over UDP.

    Handles the complete lifecycle:
    1. Bind to local UDP port
    2. Start flooding engine
    3. Exchange proofs with peer
    4. Output final decision (ATTACK/ABORT)
    """

    def __init__(self, config: NodeConfig) -> None:
        self.config = config
        self.party = Party.ALICE if config.role == "initiator" else Party.BOB

        self.protocol = TwoGenerals.create(
            party=self.party,
            keypair=config.keypair,
            counterparty_public_key=config.peer_public_key,
        )

        self.transport: Optional[UDPTransport] = None
        self.engine: Optional[FloodingEngine] = None

    async def run(self) -> str:
        """
        Run the protocol to completion.

        Returns:
            "ATTACK" if fixpoint achieved, "ABORT" otherwise
        """
        if self.config.verbose:
            print(f"Starting TGP node as {self.config.role}")
            print(f"  Local:  {self.config.local_endpoint.host}:{self.config.local_endpoint.port}")
            print(f"  Remote: {self.config.remote_endpoint.host}:{self.config.remote_endpoint.port}")
            print(f"  Party:  {self.party.name}")
            print(f"  Timeout: {self.config.timeout}s")

        # Create UDP transport
        self.transport = await UDPTransport.create(
            local=self.config.local_endpoint,
            remote=self.config.remote_endpoint,
        )

        try:
            # Create flooding engine with custom receive handling
            flood_config = FloodingConfig(
                flood_interval=self.config.flood_interval,
            )

            # Run protocol with manual message handling
            result = await self._run_protocol()
            return result

        finally:
            if self.transport:
                await self.transport.close()

    async def _run_protocol(self) -> str:
        """Run the protocol loop."""
        assert self.transport is not None

        # Start concurrent send and receive tasks
        send_task = asyncio.create_task(self._flood_loop())
        recv_task = asyncio.create_task(self._receive_loop())

        try:
            # Wait for completion or timeout
            done, pending = await asyncio.wait(
                [send_task, recv_task],
                timeout=self.config.timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Check result
            if self.protocol.is_complete:
                if self.config.verbose:
                    print(f"Protocol complete! State: {self.protocol.state.name}")
                return "ATTACK"
            else:
                if self.config.verbose:
                    print(f"Protocol timed out. State: {self.protocol.state.name}")
                return "ABORT"

        except Exception as e:
            if self.config.verbose:
                print(f"Protocol error: {e}")
            return "ABORT"

    async def _flood_loop(self) -> None:
        """
        Continuously flood current proof level.

        Per the paper: "flood Q_X continuously" - we don't stop after
        constructing Q, we keep flooding so the counterparty receives it.
        The loop runs until the timeout cancels it.
        """
        assert self.transport is not None

        while True:  # Run until cancelled by timeout
            # Get messages to send
            messages = self.protocol.get_messages_to_send()

            for msg in messages:
                try:
                    data = serialize_message(msg)
                    await self.transport.send(data)

                    if self.config.verbose:
                        print(f"  -> Sent {msg.state.name} ({len(data)} bytes)")
                except ConnectionError:
                    return

            # Wait before next flood
            await asyncio.sleep(self.config.flood_interval)

    async def _receive_loop(self) -> None:
        """
        Receive and process incoming messages.

        Keep receiving even after completing - the counterparty may
        still be sending their proofs.
        """
        assert self.transport is not None

        while True:  # Run until cancelled by timeout
            try:
                data = await self.transport.receive_timeout(1.0)
                if data is None:
                    continue

                # Parse and process message
                if len(data) >= HEADER_SIZE:
                    msg_type, length = parse_header(data)

                    if self.config.verbose:
                        print(f"  <- Recv {msg_type.name} ({len(data)} bytes)")

                    # Process the message through the protocol
                    self._process_message(data)

            except asyncio.TimeoutError:
                continue
            except ConnectionError:
                return

    def _process_message(self, data: bytes) -> None:
        """Process a received message."""
        # Parse header
        if len(data) < HEADER_SIZE:
            return

        try:
            msg_type, length = parse_header(data)
            payload = data[HEADER_SIZE:HEADER_SIZE + length]

            # Deserialize based on type
            proof = deserialize_message(msg_type, payload)

            # Deliver to protocol - it handles verification and state transitions
            self.protocol.receive(proof)
        except Exception as e:
            if self.config.verbose:
                print(f"  ! Error processing message: {e}")


# =============================================================================
# CLI Commands
# =============================================================================


def cmd_keygen(args: argparse.Namespace) -> int:
    """Generate a new keypair."""
    output = Path(args.output)

    # Generate keypair
    keypair = KeyPair.generate()

    # Save keypair
    save_keypair(keypair, output)

    # Also save public key separately
    pub_path = output.with_suffix(".pub")
    save_public_key(keypair.public_key, pub_path)

    return 0


def cmd_show_key(args: argparse.Namespace) -> int:
    """Show public key from keypair file."""
    path = Path(args.key)

    if not path.exists():
        print(f"Error: Key file not found: {path}", file=sys.stderr)
        return 1

    # Try loading as keypair first
    try:
        keypair = load_keypair(path)
        pub_b64 = base64.b64encode(keypair.public_key.to_bytes()).decode("ascii")
        print(f"Public key: {pub_b64}")
        return 0
    except Exception:
        pass

    # Try loading as public key
    try:
        pub = load_public_key(path)
        pub_b64 = base64.b64encode(pub.to_bytes()).decode("ascii")
        print(f"Public key: {pub_b64}")
        return 0
    except Exception as e:
        print(f"Error loading key: {e}", file=sys.stderr)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    """Run a TGP node."""
    # Load keypair
    key_path = Path(args.key)
    if not key_path.exists():
        print(f"Error: Key file not found: {key_path}", file=sys.stderr)
        return 1

    try:
        keypair = load_keypair(key_path)
    except Exception as e:
        print(f"Error loading keypair: {e}", file=sys.stderr)
        return 1

    # Load peer public key
    peer_path = Path(args.peer_key)
    if not peer_path.exists():
        print(f"Error: Peer key file not found: {peer_path}", file=sys.stderr)
        return 1

    try:
        peer_pub = load_public_key(peer_path)
    except Exception as e:
        print(f"Error loading peer key: {e}", file=sys.stderr)
        return 1

    # Parse endpoints
    try:
        local = parse_endpoint(args.local)
    except ValueError as e:
        print(f"Error parsing local endpoint: {e}", file=sys.stderr)
        return 1

    try:
        remote = parse_endpoint(args.remote)
    except ValueError as e:
        print(f"Error parsing remote endpoint: {e}", file=sys.stderr)
        return 1

    # Create config
    config = NodeConfig(
        role=args.role,
        keypair=keypair,
        peer_public_key=peer_pub,
        local_endpoint=local,
        remote_endpoint=remote,
        timeout=args.timeout,
        flood_interval=args.interval,
        verbose=args.verbose,
    )

    # Run node
    node = TGPNode(config)

    try:
        result = asyncio.run(node.run())
        print(f"\nResult: {result}")
        return 0 if result == "ATTACK" else 1
    except KeyboardInterrupt:
        print("\nAborted by user")
        return 130


def cmd_demo(args: argparse.Namespace) -> int:
    """Run a local demo between two parties."""
    from .network import run_simulation

    print("TGP Local Demo")
    print("=" * 60)

    # Generate keypairs
    alice_keys = KeyPair.generate()
    bob_keys = KeyPair.generate()

    print(f"Alice public key: {base64.b64encode(alice_keys.public_key.to_bytes()).decode()[:32]}...")
    print(f"Bob public key:   {base64.b64encode(bob_keys.public_key.to_bytes()).decode()[:32]}...")
    print()

    # Create protocol instances
    alice = TwoGenerals.create(Party.ALICE, alice_keys, bob_keys.public_key)
    bob = TwoGenerals.create(Party.BOB, bob_keys, alice_keys.public_key)

    print(f"Loss rate: {args.loss * 100:.0f}%")
    print(f"Max rounds: {args.rounds}")
    print()

    # Run simulation
    def on_message(party: Party, msg: ProtocolMessage) -> None:
        if args.verbose:
            print(f"  {party.name} -> {msg.state.name}")

    alice_final, bob_final = run_simulation(
        alice, bob,
        max_rounds=args.rounds,
        loss_rate=args.loss,
        on_message=on_message if args.verbose else None,
    )

    print(f"Alice state: {alice_final.state.name}")
    print(f"Bob state:   {bob_final.state.name}")
    print()

    alice_decision = "ATTACK" if alice_final.is_complete else "ABORT"
    bob_decision = "ATTACK" if bob_final.is_complete else "ABORT"

    print(f"Alice decision: {alice_decision}")
    print(f"Bob decision:   {bob_decision}")

    if alice_decision == bob_decision:
        print(f"\n✓ Symmetric outcome: Both {alice_decision}")
        return 0
    else:
        print(f"\n✗ ASYMMETRIC OUTCOME - Protocol violation!")
        return 1


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Two Generals Protocol CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # keygen command
    keygen_parser = subparsers.add_parser("keygen", help="Generate a new keypair")
    keygen_parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output file for keypair (also creates .pub file)",
    )

    # show-key command
    showkey_parser = subparsers.add_parser("show-key", help="Show public key")
    showkey_parser.add_argument(
        "key",
        help="Key file to read",
    )

    # run command
    run_parser = subparsers.add_parser("run", help="Run a TGP node")
    run_parser.add_argument(
        "--role", "-r",
        required=True,
        choices=["initiator", "responder"],
        help="Role in the protocol",
    )
    run_parser.add_argument(
        "--key", "-k",
        required=True,
        help="Path to keypair file",
    )
    run_parser.add_argument(
        "--peer-key", "-p",
        required=True,
        help="Path to peer's public key file",
    )
    run_parser.add_argument(
        "--local", "-l",
        required=True,
        help="Local endpoint (host:port)",
    )
    run_parser.add_argument(
        "--remote", "-R",
        required=True,
        help="Remote endpoint (host:port)",
    )
    run_parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=30.0,
        help="Protocol timeout in seconds (default: 30)",
    )
    run_parser.add_argument(
        "--interval", "-i",
        type=float,
        default=0.1,
        help="Flood interval in seconds (default: 0.1)",
    )
    run_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    # demo command
    demo_parser = subparsers.add_parser("demo", help="Run local demo")
    demo_parser.add_argument(
        "--loss",
        type=float,
        default=0.0,
        help="Simulated packet loss rate (0.0-0.99)",
    )
    demo_parser.add_argument(
        "--rounds",
        type=int,
        default=100,
        help="Maximum simulation rounds",
    )
    demo_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show message exchanges",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "keygen":
        return cmd_keygen(args)
    elif args.command == "show-key":
        return cmd_show_key(args)
    elif args.command == "run":
        return cmd_run(args)
    elif args.command == "demo":
        return cmd_demo(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
