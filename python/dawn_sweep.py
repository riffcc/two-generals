"""
ε(τ) decay sweep: asymmetry probability vs per-party deadline ("dawn"),
across loss rates. Uses the repo's own SimulatedParty (tests/test_theseus.py),
oblivious adversary only (i.i.d. loss, no protocol knowledge) — this measures
the residual ε after any adaptive capability is removed by indistinguishability.

Outputs a table (asymmetry% vs dawn, per loss rate) and pgfplots coordinates
for a decay-curve figure for the paper.
"""
import random
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from tests.test_theseus import SimulatedParty, MsgType  # repo's own party

RUNS = 1000


def run_once(loss_rate, dawn, rng):
    alice = SimulatedParty(name="Alice", identity=0)
    bob = SimulatedParty(name="Bob", identity=1)
    in_flight_a2b, in_flight_b2a = [], []
    a_final = b_final = None
    for tick in range(dawn + 50):
        if tick == dawn:
            a_final = "attack" if alice.decision == "attack" else "abort"
            b_final = "attack" if bob.decision == "attack" else "abort"
        for msg in alice.get_outgoing_messages():
            if rng.random() >= loss_rate:
                in_flight_a2b.append((tick + 1, msg))
        for msg in bob.get_outgoing_messages():
            if rng.random() >= loss_rate:
                in_flight_b2a.append((tick + 1, msg))
        for due, msg in [x for x in in_flight_a2b if x[0] <= tick]:
            bob.receive_message(msg)
        in_flight_a2b = [x for x in in_flight_a2b if x[0] > tick]
        for due, msg in [x for x in in_flight_b2a if x[0] <= tick]:
            alice.receive_message(msg)
        in_flight_b2a = [x for x in in_flight_b2a if x[0] > tick]
    return a_final, b_final


def asymmetry_rate(loss_rate, dawn, seed):
    rng = random.Random(seed)
    asym = 0
    for _ in range(RUNS):
        a, b = run_once(loss_rate, dawn, rng)
        if not (a == b):
            asym += 1
    return 100.0 * asym / RUNS


# Dawn ranges tuned per loss rate to capture peak -> ~0 decay.
SWEEP = {
    0.1: [3, 4, 5, 6, 8, 10, 14, 20],
    0.3: [4, 5, 6, 8, 10, 14, 20, 30],
    0.5: [6, 8, 10, 14, 20, 30, 40],
    0.7: [8, 10, 14, 20, 30, 40, 60, 80],
    0.9: [15, 20, 30, 40, 60, 80, 120, 200],
}

if __name__ == "__main__":
    print(f"runs per (loss,dawn) cell: {RUNS}; oblivious adversary; "
          f"decision rule: repo's own (attack on Q construction)\n")
    results = {}
    for p, dawns in SWEEP.items():
        results[p] = []
        for dawn in dawns:
            rate = asymmetry_rate(p, dawn, seed=int(p * 1000) + dawn)
            results[p].append((dawn, rate))
            print(f"  p={p:<4} dawn={dawn:<4}  asymmetry={rate:5.1f}%")
        print()

    print("=" * 70)
    print("pgfplots coordinates (asymmetry% vs dawn) — paste into \\addplot:")
    print("=" * 70)
    for p, pts in results.items():
        coords = " ".join(f"({d},{r:.1f})" for d, r in pts)
        print(f"  % p={p}\n  {coords}")
