"""
Protocol of Theseus Test Suite

The Ship of Theseus asks: if you replace every plank, is it the same ship?
We ask: if you remove every message, does the protocol still work?

Answer: Yes. Because symmetry is guaranteed by cryptographic structure,
not message delivery.

This test validates the core theoretical claim of TGP:
- Under ANY packet loss rate (0-98%), outcomes are ALWAYS symmetric
- Both parties either ATTACK together or ABORT together
- There is NEVER an asymmetric outcome (one attacks, one aborts)

The test uses property-based testing (Hypothesis) to generate:
- Random packet loss patterns
- Random network delays
- Random message reordering
- Adversarial loss patterns

10,000+ runs must show ZERO asymmetric outcomes.
"""
from __future__ import annotations

import random
import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Any
import struct

# Try to import hypothesis for property-based testing
try:
    from hypothesis import given, settings, strategies as st, assume
    from hypothesis.stateful import RuleBasedStateMachine, rule, precondition
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

import pytest

from tests.simulation import (
    SimulatedChannel,
    ChannelConfig,
    ChannelBehavior,
    ProtocolSimulator,
    SimulationResult,
    create_channel,
)


# =============================================================================
# Minimal Protocol Implementation for Testing
# =============================================================================
#
# We implement a minimal version of the protocol here to avoid circular
# dependencies and make the test self-contained. This mirrors the spec
# exactly: C -> D -> T -> Q with continuous flooding.
# =============================================================================


class Phase(Enum):
    """Protocol phases."""
    INIT = 0
    COMMITMENT = 1
    DOUBLE = 2
    TRIPLE = 3
    QUAD = 4
    COMPLETE = 5


class MsgType(Enum):
    """Message types."""
    C = 1  # Commitment
    D = 2  # DoubleProof
    T = 3  # TripleProof
    Q = 4  # QuadProof


@dataclass
class SimulatedParty:
    """
    Minimal TGP party implementation for Protocol of Theseus testing.

    Implements the pure epistemic protocol (Part I):
    - Commitment (C): Sign("I will attack if you agree")
    - DoubleProof (D): Sign(C_mine || C_theirs || "both committed")
    - TripleProof (T): Sign(D_mine || D_theirs || "both have doubles")
    - QuadProof (Q): Sign(T_mine || T_theirs || "fixpoint achieved")

    Key insight: Each level embeds the previous. Receiving a higher-level
    proof gives you all lower-level proofs for free.
    """
    name: str
    identity: int  # 0=Alice, 1=Bob
    phase: Phase = Phase.INIT
    sequence: int = 0

    # Own proofs
    my_c: Optional[dict] = None
    my_d: Optional[dict] = None
    my_t: Optional[dict] = None
    my_q: Optional[dict] = None

    # Received proofs from counterparty
    their_c: Optional[dict] = None
    their_d: Optional[dict] = None
    their_t: Optional[dict] = None
    their_q: Optional[dict] = None

    # Final decision
    decision: str = "undecided"

    def __post_init__(self):
        """Initialize with commitment."""
        self._create_commitment()

    def _sign(self, data: bytes) -> bytes:
        """Simulate signing (deterministic for testing)."""
        return hashlib.sha256(data + f":{self.name}".encode()).digest()

    def _create_commitment(self):
        """Create initial commitment."""
        msg = f"I will attack at dawn if you agree - {self.name}".encode()
        self.my_c = {
            "type": MsgType.C,
            "party": self.identity,
            "message": msg,
            "signature": self._sign(msg),
        }
        self.phase = Phase.COMMITMENT

    def _create_double(self):
        """Create double proof from both commitments."""
        if self.my_c is None or self.their_c is None:
            return
        payload = (
            str(self.my_c).encode() +
            str(self.their_c).encode() +
            b"Both committed"
        )
        self.my_d = {
            "type": MsgType.D,
            "party": self.identity,
            "own_c": self.my_c,
            "other_c": self.their_c,
            "signature": self._sign(payload),
        }
        self.phase = Phase.DOUBLE

    def _create_triple(self):
        """Create triple proof from both doubles."""
        if self.my_d is None or self.their_d is None:
            return
        payload = (
            str(self.my_d).encode() +
            str(self.their_d).encode() +
            b"Both have doubles"
        )
        self.my_t = {
            "type": MsgType.T,
            "party": self.identity,
            "own_d": self.my_d,
            "other_d": self.their_d,
            "signature": self._sign(payload),
        }
        self.phase = Phase.TRIPLE

    def _create_quad(self):
        """Create quaternary proof (epistemic fixpoint)."""
        if self.my_t is None or self.their_t is None:
            return
        payload = (
            str(self.my_t).encode() +
            str(self.their_t).encode() +
            b"Fixpoint achieved"
        )
        self.my_q = {
            "type": MsgType.Q,
            "party": self.identity,
            "own_t": self.my_t,
            "other_t": self.their_t,
            "signature": self._sign(payload),
        }
        self.phase = Phase.QUAD
        self.decision = "attack"

    def get_outgoing_messages(self) -> List[dict]:
        """Get messages to flood based on current phase."""
        self.sequence += 1
        messages = []

        if self.phase == Phase.COMMITMENT and self.my_c:
            messages.append({"seq": self.sequence, **self.my_c})
        elif self.phase == Phase.DOUBLE and self.my_d:
            messages.append({"seq": self.sequence, **self.my_d})
        elif self.phase == Phase.TRIPLE and self.my_t:
            messages.append({"seq": self.sequence, **self.my_t})
        elif self.phase == Phase.QUAD and self.my_q:
            messages.append({"seq": self.sequence, **self.my_q})

        return messages

    def receive_message(self, msg: dict) -> None:
        """Process received message and advance state if possible."""
        msg_type = msg.get("type")
        party = msg.get("party")

        # Ignore our own messages
        if party == self.identity:
            return

        # Process based on message type
        if msg_type == MsgType.C:
            if self.their_c is None:
                self.their_c = msg
                # Can now create double
                self._create_double()

        elif msg_type == MsgType.D:
            if self.their_d is None:
                self.their_d = msg
                # Extract their commitment if we don't have it
                if self.their_c is None:
                    self.their_c = msg.get("own_c")
                    if self.my_d is None:
                        self._create_double()
                # Can now create triple
                if self.my_d is not None:
                    self._create_triple()

        elif msg_type == MsgType.T:
            if self.their_t is None:
                self.their_t = msg
                # Extract their double if we don't have it
                if self.their_d is None:
                    self.their_d = msg.get("own_d")
                    if self.their_c is None:
                        self.their_c = self.their_d.get("own_c")
                    if self.my_d is None:
                        self._create_double()
                    if self.my_t is None:
                        self._create_triple()
                # Can now create quad
                if self.my_t is not None:
                    self._create_quad()

        elif msg_type == MsgType.Q:
            if self.their_q is None:
                self.their_q = msg
                # Extract everything from the Q proof
                if self.their_t is None:
                    self.their_t = msg.get("own_t")
                    if self.their_d is None:
                        self.their_d = self.their_t.get("own_d")
                        if self.their_c is None:
                            self.their_c = self.their_d.get("own_c")
                    if self.my_d is None:
                        self._create_double()
                    if self.my_t is None:
                        self._create_triple()
                # We can construct our Q now
                if self.my_t is not None and self.my_q is None:
                    self._create_quad()
                # Mark complete
                self.phase = Phase.COMPLETE
                self.decision = "attack"

    def has_reached_fixpoint(self) -> bool:
        """Check if we've reached the epistemic fixpoint."""
        return self.phase == Phase.COMPLETE or self.my_q is not None

    def get_decision(self) -> str:
        """Get final decision: attack, abort, or undecided."""
        return self.decision


# =============================================================================
# Test Helpers
# =============================================================================


def run_simulation(
    loss_rate: float,
    seed: int,
    max_ticks: int = 500,
) -> SimulationResult:
    """
    Run a single TGP simulation with given parameters.

    Args:
        loss_rate: Packet loss probability (0.0 to 1.0)
        seed: Random seed for reproducibility
        max_ticks: Maximum simulation ticks

    Returns:
        SimulationResult with outcomes for both parties
    """
    rng = random.Random(seed)

    # Create channel with loss
    channel = create_channel(
        loss_rate=loss_rate,
        seed=seed,
        party_a="Alice",
        party_b="Bob",
    )

    # Create simulator
    simulator = ProtocolSimulator(
        channel=channel,
        max_ticks=max_ticks,
        flood_interval=1,
    )

    # Run simulation
    result = simulator.run(
        party_a_factory=lambda: SimulatedParty(name="Alice", identity=0),
        party_b_factory=lambda: SimulatedParty(name="Bob", identity=1),
    )

    return result


def run_theseus_test(
    loss_rates: List[float],
    runs_per_rate: int = 100,
    seed_base: int = 42,
) -> dict:
    """
    Run the Protocol of Theseus test across multiple loss rates.

    This validates the core claim: symmetric outcomes regardless of
    packet loss rate.

    Args:
        loss_rates: List of loss rates to test (0.0 to 0.98)
        runs_per_rate: Number of runs per loss rate
        seed_base: Base random seed

    Returns:
        Dictionary with test results
    """
    results = {
        "total_runs": 0,
        "symmetric_attack": 0,
        "symmetric_abort": 0,
        "asymmetric_failures": 0,
        "undecided": 0,
        "by_loss_rate": {},
    }

    for loss_rate in loss_rates:
        rate_results = {
            "runs": 0,
            "attack": 0,
            "abort": 0,
            "asymmetric": 0,
            "undecided": 0,
        }

        # Scale max_ticks based on loss rate to ensure fair-lossy conditions
        # At high loss rates, need more ticks for messages to get through
        # Formula: base_ticks * (1 / (1 - loss_rate)^2) capped at reasonable max
        if loss_rate >= 0.98:
            max_ticks = 10000  # Extreme loss needs many ticks
        elif loss_rate >= 0.95:
            max_ticks = 5000
        elif loss_rate >= 0.9:
            max_ticks = 2000
        elif loss_rate >= 0.7:
            max_ticks = 1000
        else:
            max_ticks = 500

        for i in range(runs_per_rate):
            seed = seed_base + int(loss_rate * 1000) * 10000 + i
            result = run_simulation(loss_rate=loss_rate, seed=seed, max_ticks=max_ticks)

            rate_results["runs"] += 1
            results["total_runs"] += 1

            if result.is_asymmetric:
                rate_results["asymmetric"] += 1
                results["asymmetric_failures"] += 1
            elif result.party_a_outcome == "attack":
                rate_results["attack"] += 1
                results["symmetric_attack"] += 1
            elif result.party_a_outcome == "abort":
                rate_results["abort"] += 1
                results["symmetric_abort"] += 1
            else:
                rate_results["undecided"] += 1
                results["undecided"] += 1

        results["by_loss_rate"][f"{loss_rate:.2f}"] = rate_results

    return results


# =============================================================================
# Basic Tests
# =============================================================================


class TestBasicProtocol:
    """Basic protocol functionality tests."""

    def test_perfect_channel(self):
        """Protocol works perfectly with no loss."""
        result = run_simulation(loss_rate=0.0, seed=42)

        assert result.is_symmetric, "Outcome must be symmetric"
        assert result.party_a_outcome == "attack", "Both should attack"
        assert result.party_b_outcome == "attack", "Both should attack"

    def test_moderate_loss(self):
        """Protocol handles 50% loss."""
        result = run_simulation(loss_rate=0.5, seed=42, max_ticks=1000)

        assert result.is_symmetric, "Outcome must be symmetric"
        # With 50% loss and enough ticks, should still reach attack
        # But might abort if unlucky - that's fine as long as symmetric

    def test_high_loss(self):
        """Protocol handles 90% loss."""
        result = run_simulation(loss_rate=0.9, seed=42, max_ticks=2000)

        assert result.is_symmetric, f"Outcome must be symmetric: A={result.party_a_outcome}, B={result.party_b_outcome}"

    def test_extreme_loss(self):
        """Protocol handles 98% loss."""
        result = run_simulation(loss_rate=0.98, seed=42, max_ticks=5000)

        assert result.is_symmetric, f"Outcome must be symmetric: A={result.party_a_outcome}, B={result.party_b_outcome}"


class TestSymmetryProperty:
    """Tests for the core symmetry property."""

    def test_no_asymmetric_outcomes_light(self):
        """Quick test: No asymmetric outcomes across loss rates."""
        loss_rates = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9]
        runs_per_rate = 10

        results = run_theseus_test(
            loss_rates=loss_rates,
            runs_per_rate=runs_per_rate,
        )

        assert results["asymmetric_failures"] == 0, (
            f"Found {results['asymmetric_failures']} asymmetric outcomes "
            f"in {results['total_runs']} runs"
        )

    def test_no_asymmetric_outcomes_medium(self):
        """Medium test: 50 runs per loss rate."""
        loss_rates = [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95]
        runs_per_rate = 50

        results = run_theseus_test(
            loss_rates=loss_rates,
            runs_per_rate=runs_per_rate,
        )

        assert results["asymmetric_failures"] == 0, (
            f"Found {results['asymmetric_failures']} asymmetric outcomes "
            f"in {results['total_runs']} runs"
        )


class TestProofEmbedding:
    """Tests for the self-certifying proof embedding property."""

    def test_q_contains_all_proofs(self):
        """QuadProof contains all lower-level proofs."""
        result = run_simulation(loss_rate=0.0, seed=42)

        alice = result.party_a_state
        bob = result.party_b_state

        # Both should have Q
        assert alice.my_q is not None
        assert bob.my_q is not None

        # Alice's Q contains Bob's T
        assert alice.my_q["other_t"] is not None
        assert alice.my_q["other_t"]["party"] == 1  # Bob

        # Bob's Q contains Alice's T
        assert bob.my_q["other_t"] is not None
        assert bob.my_q["other_t"]["party"] == 0  # Alice

    def test_receiving_t_provides_d(self):
        """Receiving T provides the embedded D for free."""
        # Run until one party has T but might not have received D directly
        result = run_simulation(loss_rate=0.0, seed=42)

        alice = result.party_a_state
        bob = result.party_b_state

        # If Alice has Bob's T, she has Bob's D
        if alice.their_t is not None:
            assert alice.their_d is not None or "own_d" in alice.their_t


# =============================================================================
# Property-Based Tests (Hypothesis)
# =============================================================================


if HAS_HYPOTHESIS:
    class TestTheseusProperty:
        """Property-based tests using Hypothesis."""

        @given(
            loss_rate=st.floats(min_value=0.0, max_value=0.98),
            seed=st.integers(min_value=0, max_value=2**31),
        )
        @settings(max_examples=100, deadline=30000)
        def test_symmetry_property(self, loss_rate: float, seed: int):
            """
            The Protocol of Theseus Property:

            For ANY packet loss rate and ANY random seed:
            - Outcomes are ALWAYS symmetric
            - Never: one attacks, one aborts

            This is the core theoretical claim.
            """
            result = run_simulation(
                loss_rate=loss_rate,
                seed=seed,
                max_ticks=2000,
            )

            # THE CORE PROPERTY: No asymmetric outcomes
            assert not result.is_asymmetric, (
                f"ASYMMETRIC FAILURE at loss_rate={loss_rate:.2f}, seed={seed}: "
                f"Alice={result.party_a_outcome}, Bob={result.party_b_outcome}"
            )

        @given(
            seed=st.integers(min_value=0, max_value=2**31),
        )
        @settings(max_examples=50, deadline=60000)
        def test_extreme_loss_symmetry(self, seed: int):
            """Even at 95-98% loss, symmetry holds."""
            loss_rate = 0.95 + (seed % 4) * 0.01  # 95%, 96%, 97%, 98%

            result = run_simulation(
                loss_rate=loss_rate,
                seed=seed,
                max_ticks=5000,
            )

            assert not result.is_asymmetric, (
                f"ASYMMETRIC at {loss_rate*100:.0f}% loss: "
                f"A={result.party_a_outcome}, B={result.party_b_outcome}"
            )

        @given(
            loss_pattern=st.lists(
                st.booleans(),
                min_size=10,
                max_size=100,
            ),
            seed=st.integers(min_value=0, max_value=2**31),
        )
        @settings(max_examples=50, deadline=30000)
        def test_adversarial_patterns(self, loss_pattern: List[bool], seed: int):
            """
            Test with adversarial loss patterns.

            The adversary can choose WHICH specific messages to drop,
            but still cannot force asymmetric outcomes.
            """
            # Create adversarial channel
            from tests.simulation import create_adversarial_channel

            channel = create_adversarial_channel(
                loss_pattern=loss_pattern,
                seed=seed,
            )

            simulator = ProtocolSimulator(
                channel=channel,
                max_ticks=1000,
            )

            result = simulator.run(
                party_a_factory=lambda: SimulatedParty(name="Alice", identity=0),
                party_b_factory=lambda: SimulatedParty(name="Bob", identity=1),
            )

            assert not result.is_asymmetric, (
                f"ASYMMETRIC with adversarial pattern: "
                f"A={result.party_a_outcome}, B={result.party_b_outcome}"
            )


# =============================================================================
# Full Protocol of Theseus Test
# =============================================================================


class TestProtocolOfTheseus:
    """
    The Complete Protocol of Theseus Test Suite.

    Named after the philosophical paradox: if you remove every plank
    from the Ship of Theseus, is it still the same ship?

    Our answer: if you remove (lose) every message from the protocol,
    does it still guarantee symmetric outcomes? YES.

    This test validates 10,000+ random scenarios with 0 asymmetric failures.
    """

    @pytest.mark.slow
    def test_full_theseus_10k(self):
        """
        Full Protocol of Theseus test: 10,000+ scenarios.

        Tests across loss rates from 0% to 98% with comprehensive coverage.
        ZERO asymmetric failures must be found.
        """
        # Loss rates from 0% to 98%
        loss_rates = [
            0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45,
            0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.98
        ]
        runs_per_rate = 500  # 21 * 500 = 10,500 runs

        results = run_theseus_test(
            loss_rates=loss_rates,
            runs_per_rate=runs_per_rate,
            seed_base=42,
        )

        # Print summary
        print(f"\n{'='*60}")
        print("PROTOCOL OF THESEUS TEST RESULTS")
        print(f"{'='*60}")
        print(f"Total runs: {results['total_runs']}")
        print(f"Symmetric ATTACK: {results['symmetric_attack']}")
        print(f"Symmetric ABORT: {results['symmetric_abort']}")
        print(f"Undecided: {results['undecided']}")
        print(f"ASYMMETRIC FAILURES: {results['asymmetric_failures']}")
        print(f"{'='*60}")

        # THE CRITICAL ASSERTION
        assert results["asymmetric_failures"] == 0, (
            f"THESEUS TEST FAILED: Found {results['asymmetric_failures']} "
            f"asymmetric outcomes in {results['total_runs']} runs. "
            f"This violates the core theoretical claim!"
        )

        print("✓ PROTOCOL OF THESEUS: VALIDATED")
        print("  All outcomes symmetric across 0-98% packet loss")
        print(f"{'='*60}\n")


# =============================================================================
# Benchmark Tests
# =============================================================================


class TestPerformance:
    """Performance benchmarks for the protocol."""

    def test_convergence_speed(self):
        """Measure ticks to convergence at various loss rates."""
        results = {}

        for loss_rate in [0.0, 0.3, 0.5, 0.7, 0.9]:
            ticks = []
            for seed in range(10):
                result = run_simulation(
                    loss_rate=loss_rate,
                    seed=seed,
                    max_ticks=2000,
                )
                if result.party_a_outcome == "attack":
                    ticks.append(result.ticks_elapsed)

            if ticks:
                avg = sum(ticks) / len(ticks)
                results[f"{loss_rate*100:.0f}%"] = {
                    "avg_ticks": avg,
                    "min": min(ticks),
                    "max": max(ticks),
                    "converged": len(ticks),
                }

        print("\nConvergence Speed by Loss Rate:")
        for rate, stats in results.items():
            print(f"  {rate}: avg={stats['avg_ticks']:.0f} ticks "
                  f"(min={stats['min']}, max={stats['max']}, "
                  f"converged={stats['converged']}/10)")


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    # Run the quick tests
    print("Running Protocol of Theseus Tests...")

    # Quick validation
    results = run_theseus_test(
        loss_rates=[0.0, 0.3, 0.5, 0.7, 0.9, 0.95],
        runs_per_rate=100,
    )

    print(f"\nResults ({results['total_runs']} runs):")
    print(f"  Symmetric ATTACK: {results['symmetric_attack']}")
    print(f"  Symmetric ABORT: {results['symmetric_abort']}")
    print(f"  Asymmetric (FAILURES): {results['asymmetric_failures']}")

    if results["asymmetric_failures"] == 0:
        print("\n✓ All tests passed! Protocol of Theseus validated.")
    else:
        print(f"\n✗ FAILURE: {results['asymmetric_failures']} asymmetric outcomes!")
        exit(1)
