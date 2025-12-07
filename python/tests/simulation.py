"""
Network Simulation Harness for TGP Testing

Provides in-memory network simulation with configurable:
- Packet loss rates (0-99%)
- Packet reordering
- Packet duplication
- Asymmetric loss patterns

The simulation is deterministic when seeded, enabling reproducible testing.
"""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, TypeVar


class ChannelBehavior(Enum):
    """Defines how the channel handles messages."""
    LOSSY = "lossy"          # Random loss with configured probability
    PERFECT = "perfect"      # All messages delivered
    ADVERSARIAL = "adversarial"  # Worst-case loss patterns


@dataclass
class ChannelConfig:
    """Configuration for a simulated network channel."""
    loss_rate: float = 0.0           # 0.0 to 1.0 (0% to 100% loss)
    reorder_probability: float = 0.0  # Probability of message reordering
    duplicate_probability: float = 0.0  # Probability of message duplication
    behavior: ChannelBehavior = ChannelBehavior.LOSSY

    def __post_init__(self) -> None:
        if not 0.0 <= self.loss_rate <= 1.0:
            raise ValueError(f"loss_rate must be in [0, 1], got {self.loss_rate}")
        if not 0.0 <= self.reorder_probability <= 1.0:
            raise ValueError(f"reorder_probability must be in [0, 1]")
        if not 0.0 <= self.duplicate_probability <= 1.0:
            raise ValueError(f"duplicate_probability must be in [0, 1]")


T = TypeVar("T")


@dataclass
class MessageInFlight(Generic[T]):
    """A message currently in the simulated network."""
    payload: T
    sender: str
    receiver: str
    tick_sent: int
    delivery_tick: int  # When this message will be delivered (if not lost)


@dataclass
class SimulatedChannel(Generic[T]):
    """
    A simulated bidirectional network channel between two parties.

    Supports:
    - Configurable packet loss
    - Packet reordering
    - Packet duplication
    - Deterministic behavior via seeding
    """
    party_a: str
    party_b: str
    config: ChannelConfig
    rng: random.Random

    # Internal state
    messages_a_to_b: deque[MessageInFlight[T]] = field(default_factory=deque)
    messages_b_to_a: deque[MessageInFlight[T]] = field(default_factory=deque)
    current_tick: int = 0

    # Statistics
    total_sent_a_to_b: int = 0
    total_sent_b_to_a: int = 0
    total_lost_a_to_b: int = 0
    total_lost_b_to_a: int = 0
    total_delivered_a_to_b: int = 0
    total_delivered_b_to_a: int = 0

    def send(self, sender: str, payload: T) -> bool:
        """
        Send a message from sender to the other party.
        Returns True if message was sent (may still be lost in transit).
        """
        if sender == self.party_a:
            receiver = self.party_b
            queue = self.messages_a_to_b
            self.total_sent_a_to_b += 1
        elif sender == self.party_b:
            receiver = self.party_a
            queue = self.messages_b_to_a
            self.total_sent_b_to_a += 1
        else:
            raise ValueError(f"Unknown sender: {sender}")

        # Determine if message is lost
        if self._should_lose():
            if sender == self.party_a:
                self.total_lost_a_to_b += 1
            else:
                self.total_lost_b_to_a += 1
            return False

        # Calculate delivery tick (1 tick latency + possible reorder delay)
        delay = 1
        if self.rng.random() < self.config.reorder_probability:
            delay += self.rng.randint(1, 3)  # Add 1-3 tick delay for reordering

        msg = MessageInFlight(
            payload=payload,
            sender=sender,
            receiver=receiver,
            tick_sent=self.current_tick,
            delivery_tick=self.current_tick + delay,
        )
        queue.append(msg)

        # Handle duplication
        if self.rng.random() < self.config.duplicate_probability:
            dup = MessageInFlight(
                payload=payload,
                sender=sender,
                receiver=receiver,
                tick_sent=self.current_tick,
                delivery_tick=self.current_tick + delay + self.rng.randint(1, 2),
            )
            queue.append(dup)

        return True

    def _should_lose(self) -> bool:
        """Determine if the current message should be lost."""
        if self.config.behavior == ChannelBehavior.PERFECT:
            return False
        return self.rng.random() < self.config.loss_rate

    def receive(self, receiver: str) -> list[T]:
        """
        Receive all messages for the given party at the current tick.
        Returns list of payloads (may be empty).
        """
        if receiver == self.party_a:
            queue = self.messages_b_to_a
            stat_attr = "total_delivered_b_to_a"
        elif receiver == self.party_b:
            queue = self.messages_a_to_b
            stat_attr = "total_delivered_a_to_b"
        else:
            raise ValueError(f"Unknown receiver: {receiver}")

        delivered = []
        remaining = deque()

        for msg in queue:
            if msg.delivery_tick <= self.current_tick:
                delivered.append(msg.payload)
                setattr(self, stat_attr, getattr(self, stat_attr) + 1)
            else:
                remaining.append(msg)

        # Update queue
        if receiver == self.party_a:
            self.messages_b_to_a = remaining
        else:
            self.messages_a_to_b = remaining

        return delivered

    def tick(self) -> None:
        """Advance simulation by one tick."""
        self.current_tick += 1

    def get_statistics(self) -> dict[str, Any]:
        """Get channel statistics."""
        return {
            "total_sent_a_to_b": self.total_sent_a_to_b,
            "total_sent_b_to_a": self.total_sent_b_to_a,
            "total_lost_a_to_b": self.total_lost_a_to_b,
            "total_lost_b_to_a": self.total_lost_b_to_a,
            "total_delivered_a_to_b": self.total_delivered_a_to_b,
            "total_delivered_b_to_a": self.total_delivered_b_to_a,
            "loss_rate_a_to_b": (
                self.total_lost_a_to_b / self.total_sent_a_to_b
                if self.total_sent_a_to_b > 0 else 0.0
            ),
            "loss_rate_b_to_a": (
                self.total_lost_b_to_a / self.total_sent_b_to_a
                if self.total_sent_b_to_a > 0 else 0.0
            ),
        }


@dataclass
class SimulationResult:
    """Result of a protocol simulation run."""
    party_a_outcome: str  # "attack", "abort", or "undecided"
    party_b_outcome: str  # "attack", "abort", or "undecided"
    ticks_elapsed: int
    channel_stats: dict[str, Any]
    party_a_state: Any
    party_b_state: Any

    @property
    def is_symmetric(self) -> bool:
        """Check if both parties reached the same outcome."""
        return self.party_a_outcome == self.party_b_outcome

    @property
    def is_asymmetric(self) -> bool:
        """Check if parties reached different outcomes (FAILURE)."""
        # Both undecided is symmetric (abort)
        if self.party_a_outcome == "undecided" and self.party_b_outcome == "undecided":
            return False
        # Both same is symmetric
        if self.party_a_outcome == self.party_b_outcome:
            return False
        # One attack, one abort = ASYMMETRIC FAILURE
        # One attack/abort, one undecided = ASYMMETRIC FAILURE
        return True

    @property
    def outcome_type(self) -> str:
        """Describe the outcome type."""
        if self.is_asymmetric:
            return "ASYMMETRIC_FAILURE"
        if self.party_a_outcome == "attack":
            return "MUTUAL_ATTACK"
        if self.party_a_outcome == "abort":
            return "MUTUAL_ABORT"
        return "UNDECIDED"


@dataclass
class ProtocolSimulator:
    """
    Runs the Two Generals Protocol simulation.

    Drives both parties through the protocol using a simulated channel,
    detecting when both parties reach fixpoint or timeout.
    """
    channel: SimulatedChannel
    max_ticks: int = 1000
    flood_interval: int = 1  # How often parties flood (every N ticks)

    def run(
        self,
        party_a_factory: Callable[[], Any],
        party_b_factory: Callable[[], Any],
    ) -> SimulationResult:
        """
        Run the simulation with the given party implementations.

        Args:
            party_a_factory: Callable that creates party A's protocol instance
            party_b_factory: Callable that creates party B's protocol instance

        Returns:
            SimulationResult with outcomes for both parties
        """
        party_a = party_a_factory()
        party_b = party_b_factory()

        for tick in range(self.max_ticks):
            # Each party floods their current messages
            if tick % self.flood_interval == 0:
                for msg in party_a.get_outgoing_messages():
                    self.channel.send(self.channel.party_a, msg)
                for msg in party_b.get_outgoing_messages():
                    self.channel.send(self.channel.party_b, msg)

            # Advance the channel
            self.channel.tick()

            # Each party receives and processes messages
            for msg in self.channel.receive(self.channel.party_a):
                party_a.receive_message(msg)
            for msg in self.channel.receive(self.channel.party_b):
                party_b.receive_message(msg)

            # Check for fixpoint
            a_done = party_a.has_reached_fixpoint()
            b_done = party_b.has_reached_fixpoint()

            if a_done and b_done:
                break

        return SimulationResult(
            party_a_outcome=party_a.get_decision(),
            party_b_outcome=party_b.get_decision(),
            ticks_elapsed=tick + 1,
            channel_stats=self.channel.get_statistics(),
            party_a_state=party_a,
            party_b_state=party_b,
        )


def create_channel(
    loss_rate: float,
    seed: int | None = None,
    party_a: str = "Alice",
    party_b: str = "Bob",
) -> SimulatedChannel:
    """
    Create a simulated channel with the given loss rate.

    Args:
        loss_rate: Probability of packet loss (0.0 to 1.0)
        seed: Random seed for reproducibility
        party_a: Name of party A
        party_b: Name of party B

    Returns:
        Configured SimulatedChannel
    """
    rng = random.Random(seed)
    config = ChannelConfig(loss_rate=loss_rate)
    return SimulatedChannel(
        party_a=party_a,
        party_b=party_b,
        config=config,
        rng=rng,
    )


def create_adversarial_channel(
    loss_pattern: list[bool],
    seed: int | None = None,
    party_a: str = "Alice",
    party_b: str = "Bob",
) -> SimulatedChannel:
    """
    Create a channel with a specific adversarial loss pattern.

    Args:
        loss_pattern: List of booleans - True = lose this message, False = deliver
        seed: Random seed for any random behavior
        party_a: Name of party A
        party_b: Name of party B

    Returns:
        Configured SimulatedChannel with adversarial behavior
    """
    rng = random.Random(seed)
    config = ChannelConfig(behavior=ChannelBehavior.ADVERSARIAL)
    channel = SimulatedChannel(
        party_a=party_a,
        party_b=party_b,
        config=config,
        rng=rng,
    )
    # Store the loss pattern for adversarial use
    channel._loss_pattern = loss_pattern
    channel._loss_index = 0

    # Override should_lose to use the pattern
    original_should_lose = channel._should_lose
    def pattern_should_lose():
        if channel._loss_index >= len(loss_pattern):
            # Pattern exhausted - use random loss based on average
            return original_should_lose()
        result = loss_pattern[channel._loss_index]
        channel._loss_index += 1
        return result

    channel._should_lose = pattern_should_lose
    return channel
