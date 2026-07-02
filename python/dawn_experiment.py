"""
Dawn Experiment: per-party deadlines + in-flight messages.

Uses the repo's own SimulatedParty (tests/test_theseus.py) unmodified.
The ONLY change vs the existing harness: each party decides at its own
deadline ("dawn") from its own local state, instead of the simulation
looping until both parties reach fixpoint and reading decisions at a
single shared terminal instant.

Adversaries:
  - Oblivious: i.i.d. random loss, no protocol knowledge.
  - Adaptive (fair-lossy-compliant): drops NOTHING. It only DELAYS
    Alice->Bob packets of type T/Q until after dawn. Every packet is
    eventually delivered, so the channel satisfies fair-lossy. It just
    schedules the last observation past the deadline.
"""
import random
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from tests.test_theseus import SimulatedParty, MsgType  # repo's own party


def run_once(loss_rate: float, dawn: int, adaptive: bool, rng: random.Random):
    alice = SimulatedParty(name="Alice", identity=0)
    bob = SimulatedParty(name="Bob", identity=1)

    in_flight_a2b = []   # (deliver_at_tick, msg)
    in_flight_b2a = []
    delayed_past_dawn = []  # adaptive adversary's holding pen (delivered after dawn)

    a_final = b_final = None

    for tick in range(dawn + 50):  # run past dawn so delayed packets deliver
        # --- dawn: each party decides from its own local state, then freezes
        if tick == dawn:
            a_final = "attack" if alice.decision == "attack" else "abort"
            b_final = "attack" if bob.decision == "attack" else "abort"

        # --- flooding
        for msg in alice.get_outgoing_messages():
            if rng.random() >= loss_rate:  # oblivious loss (both conditions)
                if adaptive and msg.get("type") in (MsgType.T, MsgType.Q):
                    # fair-lossy-compliant: delay past dawn, never drop
                    delayed_past_dawn.append(msg)
                else:
                    in_flight_a2b.append((tick + 1, msg))
        for msg in bob.get_outgoing_messages():
            if rng.random() >= loss_rate:
                in_flight_b2a.append((tick + 1, msg))

        # adaptive adversary releases its held packets after dawn
        if adaptive and tick == dawn:
            for msg in delayed_past_dawn:
                in_flight_a2b.append((tick + 1, msg))
            delayed_past_dawn = []

        # --- delivery
        for due, msg in [x for x in in_flight_a2b if x[0] <= tick]:
            bob.receive_message(msg)
        in_flight_a2b = [x for x in in_flight_a2b if x[0] > tick]
        for due, msg in [x for x in in_flight_b2a if x[0] <= tick]:
            alice.receive_message(msg)
        in_flight_b2a = [x for x in in_flight_b2a if x[0] > tick]

    return a_final, b_final


def run_condition(label, loss_rate, dawn, adaptive, runs, seed):
    rng = random.Random(seed)
    tally = defaultdict(int)
    for _ in range(runs):
        a, b = run_once(loss_rate, dawn, adaptive, rng)
        if a == b == "attack":
            tally["both_attack"] += 1
        elif a == b == "abort":
            tally["both_abort"] += 1
        else:
            tally["ASYMMETRIC"] += 1
    asym = tally["ASYMMETRIC"]
    print(f"{label:<46} attack={tally['both_attack']:>5}  "
          f"abort={tally['both_abort']:>5}  ASYMMETRIC={asym:>5}  "
          f"({100.0*asym/runs:.1f}%)")
    return tally


if __name__ == "__main__":
    RUNS = 1000
    print(f"runs per condition: {RUNS}; decision rule: repo's own "
          f"(attack upon constructing Q); dawn = per-party deadline\n")

    print("--- Condition 1: OBLIVIOUS adversary, generous dawn (the 10k-test regime, timed) ---")
    run_condition("oblivious, 50% loss, dawn=200", 0.50, 200, False, RUNS, seed=1)

    print("\n--- Condition 2: OBLIVIOUS adversary, dawn tightness sweep (measuring eps(tau)) ---")
    for dawn in (6, 8, 10, 14, 20, 40, 80):
        run_condition(f"oblivious, 50% loss, dawn={dawn}", 0.50, dawn, False, RUNS, seed=dawn)

    print("\n--- Condition 3: ADAPTIVE adversary (fair-lossy-compliant: delays, never drops) ---")
    run_condition("adaptive, 0% base loss, dawn=200", 0.00, 200, True, RUNS, seed=42)
    run_condition("adaptive, 50% base loss, dawn=200", 0.50, 200, True, RUNS, seed=43)
