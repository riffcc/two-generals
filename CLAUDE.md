# Two Generals Protocol (TGP) - Implementation Guide

**Project:** two-generals-public
**License:** AGPLv3 (when released)
**Status:** Active Development
**Slogan:** "The Protocol of Theseus"

---

## Mission Statement

Build a **public, embarrassment-proof, formally verifiable** implementation of the Two Generals Protocol (TGP) that:

1. **Solves Gray's Common Knowledge Impossibility (1978)** - Deterministically and provably
2. **Provides UDP speeds with TCP guarantees** - Via TGP adapters (ToTG, UoTG)
3. **Survives adversarial conditions** - Espionage, compromise, 90%+ packet loss
4. **Achieves near-line-rate throughput** - Even under extreme loss conditions

---

## The Protocol of Theseus

> *"If you remove every part of the protocol, one message at a time, at what point does it fail?"*

**Answer:** It doesn't. The protocol is designed so that no single message is "the last message." Symmetric abort is guaranteed even when the entire packet stream is corrupted.

This is the core innovation: **Cryptographic proof stapling** creates bilateral receipts where both parties either have complete proof (and proceed) or incomplete proof (and abort). There is no asymmetric outcome.

---

## What We're Proving

### Theoretical Claims

1. **Gray's Impossibility Solved**
   - Common knowledge IS achievable over lossy channels
   - Via cryptographic recursive embedding (proof stapling)
   - Formally verified in Lean 4 (0 sorry statements)

2. **Symmetric Outcomes Guaranteed**
   - Both attack OR both abort
   - Never one attacks, one aborts
   - Cryptographically enforced, not probabilistic

3. **Byzantine Fault Tolerance**
   - Survives malicious actors
   - Double-blinded public keys for identity
   - Encrypted traffic renders adversaries useless

### Performance Claims

| Packet Loss | Expected Throughput | vs TCP |
|-------------|---------------------|--------|
| 10% | ~90% line rate | 1.5-3x faster |
| 50% | ~50% line rate | 10-50x faster |
| 90% | ~10% line rate | 100-500x faster |
| 98% | ~1.5-2% line rate | Still functional |

**TCP at 90% loss:** Essentially unusable (exponential backoff hell)
**TGP at 90% loss:** Near-linear degradation (graceful)

---

## Implementation Targets

### Core Protocol (TGP)

| Language | Status | Priority |
|----------|--------|----------|
| Python | 🔴 TODO | Reference implementation |
| Rust | 🔴 TODO | Production implementation |
| WASM | 🔴 TODO | Browser/edge deployment |
| Web (JS/TS) | 🔴 TODO | Direct browser use |

### Adapters

| Adapter | Description | Status |
|---------|-------------|--------|
| ToTG | TCP over TGP - TCP-compatible wrapper | 🔴 TODO |
| UoTG | UDP over TGP - UDP-compatible wrapper | 🔴 TODO |

### Proofs & Verification

| Component | Status |
|-----------|--------|
| Lean 4 formal proofs | ✅ Complete (in synthesis/) |
| Python simulation | 🔴 TODO |
| Rust benchmarks | 🔴 TODO |
| Adversarial test suite | 🔴 TODO |
| Protocol of Theseus test | 🔴 TODO |

---

## Architecture

### The Proof Stapling Protocol

```
Phase 1: Commitment Exchange
├── Alice: R1_Alice = Sign(key_a, "ATTACK", nonce_a)
├── Bob:   R1_Bob = Sign(key_b, "ATTACK", nonce_b)
└── Exchange via continuous flooding

Phase 2: Double Proofs
├── Alice: R2_Alice = Sign(key_a, {R1_Alice, R1_Bob})
├── Bob:   R2_Bob = Sign(key_b, {R1_Bob, R1_Alice})
└── "I have both commitments"

Phase 3: Triple Proofs
├── Alice: R3_Alice = Sign(key_a, {R2_Alice, R2_Bob})
├── Bob:   R3_Bob = Sign(key_b, {R2_Bob, R2_Alice})
└── "I know you have both commitments"

Phase 4: Bilateral Receipt (Q)
├── Q = {R3_Alice, R3_Bob, confirmations}
├── Q is SELF-CERTIFYING common knowledge
└── Having Q proves counterparty has Q

Decision:
├── Have complete Q → ATTACK
└── Missing any component → ABORT (symmetric)
```

### Why It Works

**Dependent Signatures:** You cannot complete YOUR proof without receiving THEIR proof.

```python
# Bob can only create Sig4 if he has Alice's complete proof
alice_hash = hash(alice_complete_proof)
bob_sig4 = sign(bob_key, bob_proof, alice_hash, "DEPENDS_ON_ALICE")

# If Alice's proof never arrives → Bob cannot create Sig4 → Both abort
```

---

## Test Suite Requirements

### Failure Mode Analysis

Every possible way the protocol could fail must be tested:

1. **Network Failures**
   - [ ] 10%, 50%, 90%, 99% packet loss
   - [ ] Asymmetric loss (A→B works, B→A fails)
   - [ ] Partition and reconnection
   - [ ] Latency spikes (1ms to 10s)
   - [ ] Packet reordering
   - [ ] Duplicate packets

2. **Adversarial Conditions**
   - [ ] Man-in-the-middle attempts
   - [ ] Replay attacks
   - [ ] Signature forgery attempts
   - [ ] Timing attacks
   - [ ] Packet injection
   - [ ] Key compromise scenarios

3. **Byzantine Failures**
   - [ ] Malicious party sends wrong proofs
   - [ ] Party attempts to create asymmetric outcome
   - [ ] Colluding adversaries
   - [ ] Sybil attacks

4. **Edge Cases**
   - [ ] Simultaneous send (race conditions)
   - [ ] Clock skew between parties
   - [ ] Memory exhaustion
   - [ ] Integer overflow in sequence numbers

### The Protocol of Theseus Test

**The ultimate test:** Randomly remove messages from a successful exchange until it fails.

```python
def protocol_of_theseus_test():
    # Run successful exchange, capture all packets
    packets = run_successful_exchange()

    # Randomly remove packets one by one
    for i in range(len(packets)):
        remaining = packets[:i] + packets[i+1:]
        result = simulate_with_packets(remaining)

        # MUST be symmetric outcome
        assert result.alice == result.bob

        # Either both ATTACK or both ABORT
        assert result in [BOTH_ATTACK, BOTH_ABORT]

    # There is no "last message" that breaks symmetry
    print("Protocol of Theseus: PASSED")
```

---

## Multi-Agent Coordination (Palace Turbo)

When running in Palace Turbo swarm mode, Claude agents coordinate via `PROGRESS.json`.

### Agent IDs

Agents are assigned IDs like: `sonnet-4`, `opus-1`, `haiku-3`

### PROGRESS.json Structure

```json
{
  "inbox": {
    "sonnet-4": [
      {"from": "opus-1", "message": "Rust impl started", "timestamp": "..."}
    ],
    "opus-1": [],
    "haiku-3": []
  },
  "noticeboard": [
    {"agent": "sonnet-4", "notice": "Python reference complete", "timestamp": "..."}
  ],
  "cleanup": [
    {"agent": "haiku-3", "request": "Prune inbox older than 1 hour", "timestamp": "..."}
  ],
  "action": [
    {"agent": "sonnet-4", "action": "Created tgp/core.py", "status": "complete", "timestamp": "..."},
    {"agent": "opus-1", "action": "Started Rust benchmarks", "status": "in_progress", "timestamp": "..."}
  ]
}
```

### Atomic Operations

**CRITICAL:** Always read-before-write with atomic operations:

```python
import json
import fcntl

def atomic_update(update_fn):
    with open('PROGRESS.json', 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock
        try:
            data = json.load(f)
            new_data = update_fn(data)
            f.seek(0)
            f.truncate()
            json.dump(new_data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

### Communication Patterns

**Inbox:** Direct messages to specific agents
```json
{"from": "opus-1", "to": "sonnet-4", "message": "Need review on proof.lean", "timestamp": "..."}
```

**Noticeboard:** Broadcast to all agents
```json
{"agent": "haiku-3", "notice": "BREAKING: Found edge case in Phase 3", "priority": "high"}
```

**Cleanup:** Request pruning of stale data
```json
{"agent": "sonnet-4", "request": "Archive completed actions older than 24h"}
```

**Action:** Log what you've done (for backchecks)
```json
{"agent": "opus-1", "action": "Completed adversarial test suite", "files": ["tests/adversarial.py"], "status": "complete"}
```

---

## Skills / Masks

### Required: distributed-systems

When pondering TGP, Byzantine fault tolerance, or network protocols, activate the `distributed-systems` skill:

```
/activate-skill distributed-systems
```

This provides expertise in:
- Consensus algorithms (Paxos, Raft, PBFT)
- CAP theorem and its implications
- Network partition handling
- Byzantine fault tolerance
- Distributed systems impossibility results

---

## Directory Structure

```
two-generals-public/
├── CLAUDE.md              # This file
├── README.md              # Public-facing overview
├── PROGRESS.json          # Multi-agent coordination
├── .gitignore             # Excludes synthesis/
│
├── synthesis/             # PRIVATE (gitignored)
│   ├── ORIGINAL_PROMPT.md # Original mission statement
│   ├── *.lean             # Formal Lean 4 proofs
│   └── *.md               # Internal documentation
│
├── python/                # Python implementation
│   ├── tgp/               # Core protocol
│   ├── totg/              # TCP over TGP
│   ├── uotg/              # UDP over TGP
│   └── tests/             # Test suite
│
├── rust/                  # Rust implementation
│   ├── src/
│   ├── benches/           # Benchmarks
│   └── tests/
│
├── wasm/                  # WASM build
│
└── web/                   # Browser implementation
```

---

## Success Criteria

### Phase 1: Reference Implementation (Python)
- [ ] Core TGP protocol working
- [ ] All failure modes tested
- [ ] Protocol of Theseus test passes
- [ ] 90% packet loss still achieves symmetric outcomes

### Phase 2: Production Implementation (Rust)
- [ ] Zero-copy packet handling
- [ ] Benchmarks vs TCP under loss
- [ ] Memory safety verified
- [ ] Async/await support

### Phase 3: Ubiquitous Deployment
- [ ] WASM build for browsers
- [ ] ToTG adapter (drop-in TCP replacement)
- [ ] UoTG adapter (drop-in UDP replacement)
- [ ] Web demo with visualization

### Phase 4: Academic Verification
- [ ] Lean proofs published
- [ ] Paper submitted
- [ ] Independent verification
- [ ] AGPLv3 public release

---

## Philosophy

### Why AGPLv3?

> "EVERYTHING is free (AGPLv3). ZERO compromises."

This protocol solves a 47-year impossibility result. It should be:
- **Free** for anyone to use
- **Open** for anyone to verify
- **Protected** from proprietary capture

### Why "Embarrassment-Proof"?

Every claim must be:
- **Defensible** with formal proofs
- **Verifiable** by running the tests
- **Reproducible** by anyone

No "trust us" - only "verify yourself."

### Why "The Protocol of Theseus"?

The Ship of Theseus asks: if you replace every plank, is it the same ship?

We ask: if you remove every message, does the protocol still work?

**Answer:** Yes. Because symmetry is guaranteed by cryptographic structure, not message delivery.

---

## References

1. **Akkoyunlu et al. (1975)** - Original Two Generals Problem
2. **Gray, J. (1978)** - Common Knowledge Impossibility
3. **Lean 4** - Formal verification language
4. **synthesis/*.lean** - Our formal proofs

---

## Getting Started

```bash
# Clone the repo
git clone https://github.com/[TBD]/two-generals-public

# Python development
cd python
pip install -e .
pytest tests/

# Rust development
cd rust
cargo test
cargo bench

# Run the Protocol of Theseus test
python -m tgp.theseus_test
```

---

## Contact

**Author:** Wings@riff.cc (Riff Labs)
**Keeper:** Lief (The Forge)

---

**e cinere surgemus** 🔥

*"For 47 years, common knowledge over lossy channels was considered mathematically impossible. Today, we proved it solvable."*
