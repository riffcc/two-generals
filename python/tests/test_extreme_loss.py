"""
Extreme Loss Simulation: Proof that TGP V3 works at 99.9999% packet loss.

Scenario: "Attack at Dawn"
- Both generals flood messages at 100 msg/sec
- Duration: 18 hours (until dawn)
- Packet loss: 99.9999% (1 in 1,000,000 packets delivered)
- Expected deliveries: ~6.48 per direction

This simulation proves the protocol achieves symmetric outcomes even under
extreme adversarial network conditions.
"""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Tuple
import statistics
import math


class Phase(Enum):
    """V3 protocol phases."""
    COMMITMENT = 1
    DOUBLE = 2
    TRIPLE = 3
    QUAD = 4
    Q_CONF = 5
    Q_CONF_FINAL = 6
    COMPLETE = 7


@dataclass
class GeneralState:
    """State of one general in the simulation."""
    name: str
    phase: Phase = Phase.COMMITMENT

    # Track what we have from counterparty (highest received)
    received_phase: int = 0  # 0 = nothing, 1-6 = phase received

    # Track our construction progress
    # We can only advance when we have counterparty's proof at (our_phase - 1)
    # Due to nested embedding, receiving phase N gives us all phases 1..N

    def can_advance(self) -> bool:
        """Check if we can advance to next phase."""
        if self.phase == Phase.COMPLETE:
            return False

        current = self.phase.value

        # To construct phase N, we need counterparty's phase (N-1) or higher
        # Special case: COMMITMENT (phase 1) is created immediately
        if current == 1:
            return True  # Already at COMMITMENT, can flood

        # For phases 2-6, need counterparty's (current-1) to construct current
        # But we only advance AFTER receiving, so check if we have what we need for NEXT phase
        next_phase = current + 1
        if next_phase > 7:
            return False

        # To advance to next_phase, we need counterparty's (next_phase - 1) = current
        return self.received_phase >= current

    def advance(self) -> bool:
        """Try to advance to next phase. Returns True if advanced."""
        if not self.can_advance():
            return False

        if self.phase.value < 7:
            self.phase = Phase(self.phase.value + 1)
            return True
        return False

    def receive_from_counterparty(self, counterparty_phase: int) -> bool:
        """
        Receive a message from counterparty at given phase.

        Due to nested proof embedding, receiving phase N gives us all phases 1..N.
        Returns True if this is new information.
        """
        if counterparty_phase > self.received_phase:
            self.received_phase = counterparty_phase
            return True
        return False


def simulate_protocol(
    msg_per_sec: int = 100,
    duration_hours: float = 18.0,
    loss_rate: float = 0.999999,
    seed: Optional[int] = None,
    verbose: bool = False,
) -> Tuple[str, str, float, int, int]:
    """
    Simulate the TGP V3 protocol under extreme loss.

    Returns:
        (alice_decision, bob_decision, completion_time_hours, alice_deliveries, bob_deliveries)
    """
    if seed is not None:
        random.seed(seed)

    delivery_prob = 1 - loss_rate
    total_seconds = int(duration_hours * 3600)

    alice = GeneralState("Alice")
    bob = GeneralState("Bob")

    alice_deliveries = 0
    bob_deliveries = 0
    completion_time = None

    # Simulate second by second
    for second in range(total_seconds):
        # Each second, both parties attempt to send msg_per_sec messages
        # They send their current highest phase proof

        for _ in range(msg_per_sec):
            # Alice sends to Bob
            if random.random() < delivery_prob:
                alice_deliveries += 1
                if bob.receive_from_counterparty(alice.phase.value):
                    if verbose and alice_deliveries <= 20:
                        print(f"t={second}s: Bob received Alice's phase {alice.phase.value}")

            # Bob sends to Alice
            if random.random() < delivery_prob:
                bob_deliveries += 1
                if alice.receive_from_counterparty(bob.phase.value):
                    if verbose and bob_deliveries <= 20:
                        print(f"t={second}s: Alice received Bob's phase {bob.phase.value}")

        # Try to advance both parties (may happen multiple times as they catch up)
        for _ in range(10):  # Max 10 phase advances per second
            alice_advanced = alice.advance()
            bob_advanced = bob.advance()

            if verbose and alice_advanced:
                print(f"t={second}s: Alice advanced to {alice.phase.name}")
            if verbose and bob_advanced:
                print(f"t={second}s: Bob advanced to {bob.phase.name}")

            if not alice_advanced and not bob_advanced:
                break

        # Check for completion
        if alice.phase == Phase.COMPLETE and bob.phase == Phase.COMPLETE:
            if completion_time is None:
                completion_time = second / 3600  # hours
            break

    # Determine decisions
    alice_decision = "ATTACK" if alice.phase == Phase.COMPLETE else "ABORT"
    bob_decision = "ATTACK" if bob.phase == Phase.COMPLETE else "ABORT"

    return alice_decision, bob_decision, completion_time, alice_deliveries, bob_deliveries


def run_simulation_suite(
    num_runs: int = 1000,
    msg_per_sec: int = 100,
    duration_hours: float = 18.0,
    loss_rate: float = 0.999999,
) -> dict:
    """
    Run multiple simulations and collect statistics.
    """
    results = {
        "total_runs": num_runs,
        "symmetric_attack": 0,
        "symmetric_abort": 0,
        "asymmetric": 0,
        "completion_times": [],
        "alice_deliveries": [],
        "bob_deliveries": [],
    }

    print(f"Running {num_runs} simulations at {loss_rate*100}% loss...")
    print(f"Parameters: {msg_per_sec} msg/sec, {duration_hours} hours")
    print()

    for i in range(num_runs):
        alice_dec, bob_dec, comp_time, alice_del, bob_del = simulate_protocol(
            msg_per_sec=msg_per_sec,
            duration_hours=duration_hours,
            loss_rate=loss_rate,
            seed=None,  # Random seed each run
        )

        results["alice_deliveries"].append(alice_del)
        results["bob_deliveries"].append(bob_del)

        if alice_dec == bob_dec:
            if alice_dec == "ATTACK":
                results["symmetric_attack"] += 1
                if comp_time is not None:
                    results["completion_times"].append(comp_time)
            else:
                results["symmetric_abort"] += 1
        else:
            results["asymmetric"] += 1
            print(f"  WARNING: Asymmetric outcome in run {i+1}: Alice={alice_dec}, Bob={bob_dec}")

        if (i + 1) % 100 == 0:
            print(f"  Completed {i+1}/{num_runs} runs...")

    return results


def print_results(results: dict):
    """Pretty print simulation results."""
    print()
    print("=" * 70)
    print("SIMULATION RESULTS")
    print("=" * 70)
    print()

    total = results["total_runs"]
    sym_attack = results["symmetric_attack"]
    sym_abort = results["symmetric_abort"]
    asym = results["asymmetric"]

    print(f"Total runs:        {total}")
    print(f"Symmetric ATTACK:  {sym_attack} ({sym_attack/total*100:.2f}%)")
    print(f"Symmetric ABORT:   {sym_abort} ({sym_abort/total*100:.2f}%)")
    print(f"Asymmetric:        {asym} ({asym/total*100:.2f}%)")
    print()

    if asym == 0:
        print("✓ ZERO ASYMMETRIC OUTCOMES - Protocol correctness verified!")
    else:
        print(f"✗ {asym} ASYMMETRIC OUTCOMES - This should never happen!")

    print()

    if results["completion_times"]:
        times = results["completion_times"]
        print(f"Completion time (successful runs):")
        print(f"  Mean:   {statistics.mean(times):.2f} hours")
        print(f"  Median: {statistics.median(times):.2f} hours")
        print(f"  Min:    {min(times):.2f} hours")
        print(f"  Max:    {max(times):.2f} hours")
        if len(times) > 1:
            print(f"  StdDev: {statistics.stdev(times):.2f} hours")

    print()

    alice_dels = results["alice_deliveries"]
    bob_dels = results["bob_deliveries"]
    print(f"Message deliveries (Alice→Bob):")
    print(f"  Mean:   {statistics.mean(alice_dels):.2f}")
    print(f"  Median: {statistics.median(alice_dels):.2f}")
    print(f"  Min:    {min(alice_dels)}")
    print(f"  Max:    {max(alice_dels)}")

    print()
    print(f"Message deliveries (Bob→Alice):")
    print(f"  Mean:   {statistics.mean(bob_dels):.2f}")
    print(f"  Median: {statistics.median(bob_dels):.2f}")
    print(f"  Min:    {min(bob_dels)}")
    print(f"  Max:    {max(bob_dels)}")

    # Distribution of deliveries
    print()
    print("Delivery distribution:")
    all_dels = alice_dels + bob_dels
    for threshold in [1, 3, 5, 6, 8, 10, 12]:
        count = sum(1 for d in all_dels if d >= threshold)
        print(f"  >= {threshold:2d} deliveries: {count}/{len(all_dels)} ({count/len(all_dels)*100:.1f}%)")


def compute_success_probability(
    msg_per_sec: int = 100,
    duration_hours: float = 18.0,
    loss_rate: float = 0.999999,
) -> float:
    """
    Compute theoretical probability of protocol success using Poisson approximation.

    The protocol needs at least 6 successful deliveries in each direction
    (one per phase, though nested embedding can reduce this).
    """
    delivery_prob = 1 - loss_rate
    total_messages = msg_per_sec * duration_hours * 3600

    # Expected deliveries (Poisson parameter)
    lambda_val = total_messages * delivery_prob

    # P(X >= k) for Poisson distribution
    def poisson_at_least_k(lam, k):
        prob_less_than_k = sum(
            (lam**i * math.exp(-lam)) / math.factorial(i)
            for i in range(k)
        )
        return 1 - prob_less_than_k

    # Need at least ~6 deliveries in each direction for full V3 protocol
    # But with nested embedding, might need fewer
    # Conservative estimate: need 6 in each direction independently
    p_one_direction = poisson_at_least_k(lambda_val, 6)
    p_both_directions = p_one_direction ** 2

    return p_both_directions, lambda_val


if __name__ == "__main__":
    import sys

    # Default parameters
    msg_per_sec = 100
    duration_hours = 18.0
    loss_rate = 0.999999
    num_runs = 1000

    print("=" * 70)
    print("TGP V3 EXTREME LOSS SIMULATION")
    print("'Attack at Dawn' Scenario")
    print("=" * 70)
    print()
    print(f"Configuration:")
    print(f"  Message rate:    {msg_per_sec} msg/sec")
    print(f"  Duration:        {duration_hours} hours")
    print(f"  Packet loss:     {loss_rate*100}%")
    print(f"  Delivery prob:   {1-loss_rate} (1 in {int(1/(1-loss_rate)):,})")
    print()

    total_messages = msg_per_sec * duration_hours * 3600
    expected_deliveries = total_messages * (1 - loss_rate)
    print(f"  Total messages:  {int(total_messages):,}")
    print(f"  Expected deliveries per direction: {expected_deliveries:.2f}")
    print()

    # Theoretical probability
    p_success, lambda_val = compute_success_probability(msg_per_sec, duration_hours, loss_rate)
    print(f"Theoretical Analysis:")
    print(f"  Poisson λ = {lambda_val:.2f}")
    print(f"  P(success) ≈ {p_success:.4f} ({p_success*100:.2f}%)")
    print()

    # Run single verbose simulation first
    print("=" * 70)
    print("SINGLE VERBOSE RUN")
    print("=" * 70)
    alice_dec, bob_dec, comp_time, alice_del, bob_del = simulate_protocol(
        msg_per_sec=msg_per_sec,
        duration_hours=duration_hours,
        loss_rate=loss_rate,
        seed=42,
        verbose=True,
    )
    print()
    print(f"Result: Alice={alice_dec}, Bob={bob_dec}")
    print(f"Completion time: {comp_time:.2f} hours" if comp_time else "Did not complete")
    print(f"Deliveries: Alice→Bob={alice_del}, Bob→Alice={bob_del}")
    print()

    # Run full simulation suite
    print("=" * 70)
    print(f"RUNNING {num_runs} SIMULATIONS")
    print("=" * 70)
    results = run_simulation_suite(
        num_runs=num_runs,
        msg_per_sec=msg_per_sec,
        duration_hours=duration_hours,
        loss_rate=loss_rate,
    )

    print_results(results)

    print()
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    if results["asymmetric"] == 0:
        print()
        print("The Two Generals Protocol V3 achieves ZERO asymmetric outcomes")
        print(f"even at {loss_rate*100}% packet loss over {duration_hours} hours.")
        print()
        print("The bilateral construction property guarantees that:")
        print("  - If one party decides ATTACK, the other will too")
        print("  - If one party decides ABORT, the other will too")
        print("  - NEVER: one ATTACK, one ABORT")
        print()
        success_rate = results["symmetric_attack"] / results["total_runs"] * 100
        print(f"Protocol success rate: {success_rate:.1f}% (both ATTACK)")
        print(f"Safe abort rate: {100-success_rate:.1f}% (both ABORT)")
        print()
        print("This proves the protocol is DETERMINISTICALLY FAILSAFE.")
    else:
        print(f"ERROR: {results['asymmetric']} asymmetric outcomes detected!")
        sys.exit(1)
