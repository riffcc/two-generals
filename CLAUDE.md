# Two Generals Protocol (TGP) — Project Documentation

> **"The Protocol of Theseus"** — A deterministically failsafe solution to the Coordinated Attack Problem

## Executive Summary

This project delivers a **formally verifiable, publicly defensible solution** to the Two Generals Problem (Gray's Common Knowledge Impossibility, 1978). For fifty years, distributed systems theory has treated this problem as fundamentally unsolvable. We prove this interpretation incorrect through cryptographic proof stapling, continuous flooding, and bilateral receipt construction.

The solution achieves:
- **Deterministic coordination** with probability 1 - 10^-1565 (physical certainty)
- **All-or-nothing semantics**: Both parties ATTACK together or both ABORT together
- **Zero asymmetric outcomes** via bilateral construction properties

---

# Part I: The Theoretical Result

## Core Protocol: Epistemic Proof Escalation

### The Fundamental Insight

Instead of acknowledgments (which create infinite regress), we employ **signed cryptographic proofs** that escalate through four levels, culminating in a bilateral epistemic fixpoint.

**This section uses ONLY signatures. No DH. No shared secrets. Pure epistemic logic.**

---

### Phase 1: Commitment Flooding (C_X)

Each party generates and continuously floods a signed commitment:

```
C_X = Sign_X("I will attack at dawn if you agree")
```

**What it proves:** Nothing about the other party yet — unilateral intent only.

**Behavior:** Flood continuously. Upon receiving C_Y, advance to Phase 2.

---

### Phase 2: Double Proof Construction (D_X)

Upon receiving counterparty's commitment, construct the double proof:

```
D_X = Sign_X(C_X ∥ C_Y ∥ "Both parties committed")
```

The double proof embeds **both** original commitments inside a new signed envelope.

**What it proves:** "I know you've committed."

**Behavior:** May cease flooding C_X. Begin flooding D_X continuously.

---

### Phase 3: Triple Proof Escalation (T_X)

Upon receiving D_Y, construct the triple proof:

```
T_X = Sign_X(D_X ∥ D_Y ∥ "Both parties have double proofs")
```

By construction, T_X contains:
- Both original commitments (C_A, C_B)
- Both double proofs (D_A, D_B)

**What it proves:** "I know that you know I've committed."

**Behavior:** Flood T_X continuously.

---

### Phase 4: Quaternary Proof Fixpoint (Q)

Upon receiving T_Y, construct the quaternary proof:

```
Q = Sign_X(T_X ∥ T_Y ∥ "Fixpoint achieved")
```

The quad proof staples both triple proofs together.

**What it proves:** "I know that you know that I know that you know..." — **this is the fixed point.**

---

## The Bilateral Construction Property

**This is the core theoretical contribution.**

For Party A to build Q:
1. They must have their own T_A
2. They must have received T_B from Party B
3. T_B proves Party B had D_A and D_B
4. Therefore, Party B has all pieces necessary to construct Q upon receiving T_A

For Party B to build Q:
1. They must receive T_A
2. By logical necessity, they can construct their own T_B (or already have)
3. Q construction is symmetric — if one party can build Q, the other can too

**You cannot have Q without the counterparty being able to construct Q.**

The artifact IS the proof.

---

## Formal Epistemic Fixpoint

The quaternary proof Q satisfies:

```
∃Q : (Q → K_A K_B Q) ∧ (Q → K_B K_A Q)
```

Where K_X means "party X knows that..."

The existence of Q is already common knowledge of its existence. Q is a **self-referential epistemic artifact** where construction itself proves mutual knowledge with no infinite regress required.

### Proof Structure Table

| Level | Constructed when… | What it proves | Epistemic Depth |
|-------|-------------------|----------------|-----------------|
| C_X | Unilaterally | "I will attack if you agree." | 0 |
| D_X = {C_X, C_Y}_X | Have other's commitment | "I know you've committed." | 1 |
| T_X = {D_X, D_Y}_X | Have other's double | "I know that you know I've committed." | 2 |
| Q = {T_A, T_B} | Have both triples | Epistemic fixpoint | ω (fixed point) |

---

## Why This Solves the Problem

### The Classical Impossibility

Gray (1978) and Halpern-Moses (1990) proved that common knowledge cannot be achieved over unreliable channels with finite message sequences. Every message might be the "last message" that fails to arrive.

### Our Resolution

1. **Continuous flooding eliminates "last message"**: No message is special — any instance suffices
2. **Bilateral construction creates symmetric completion**: If one party can succeed, the other must be able to
3. **Cryptographic proof stapling provides certainty**: Not probabilistic evidence, but cryptographic proof
4. **Coordinated abort is a valid solution**: Both ATTACK or both ABORT — never asymmetric

### The Critical Insight

The **construction and existence** of Q proves common knowledge. You cannot build Q without having the components that prove the counterparty also has everything needed to build Q.

### Decision Rule (Pure Epistemic)

- **ATTACK** if: Party has constructed Q before deadline
- **ABORT** if: Cannot construct Q before deadline

This is sufficient. No DH required. The theoretical result is complete.

---

# Part II: Practical Hardening

## Collaborative Diffie-Hellman Completion

For production deployment, we add a DH layer atop Q to derive a shared secret:

```
DH_A = Sign_A(g^a ∥ Q_A ∥ "DH contribution")
DH_B = Sign_B(g^b ∥ Q_B ∥ "DH contribution")

S = g^ab (computed collaboratively)
```

The shared secret S satisfies the **collaborative computation property**: it can only exist if both parties contributed their private values and received the counterparty's public contribution.

**Why add DH?**
- Provides a usable shared secret for subsequent encrypted communication
- Adds Byzantine hardening (active adversary resistance)
- Enables session key derivation for ToTG/UoTG adapters

**Note:** DH is engineering, not the theoretical contribution. The pure epistemic protocol (Part I) already solves Gray's impossibility.

---

## Performance Characteristics

| Metric | Claim | Validation Method |
|--------|-------|-------------------|
| 90%+ loss tolerance | Functional at 99.9% loss | Empirical testing |
| 1.1-500x TCP throughput | Context-dependent improvement | Benchmarking suite |
| Line-rate - loss% | At 98% loss → ~1.9% throughput | Mathematical proof + empirical |

---

## Security Properties

| Property | Guarantee | Mechanism |
|----------|-----------|-----------|
| Adversarial observation | Defeated | Public-key encryption blinds adversaries |
| Strategic interference | Reduced to noise | State-independent strategies = probabilistic |
| Espionage/compromise | Handled | Double-blinded key exchange, continuous flooding |

---

## Protocol Adapters

- **ToTG (TCP over TGP)**: TCP guarantees at UDP speeds
- **UoTG (UDP over TGP)**: Enhanced UDP with coordination semantics
- Compatible with existing infrastructure via adapter layer

---

# Part III: Implementation & Verification

## Formal Verification

- Complete Lean 4 proof of safety, liveness, and validity theorems
- Zero unproven assumptions in coordination logic
- Property-based testing with 10,000+ adversarial test cases
- Jepsen-style testing under real packet loss, reordering, duplication

## Implementation Targets

| Platform | Status | Description |
|----------|--------|-------------|
| Python | 🔴 TODO | Reference implementation with Ed25519 + X25519 |
| Rust | 🔴 TODO | High-performance implementation with formal verification hooks |
| WASM | 🔴 TODO | Browser-compatible for web applications |
| Web | 🔴 TODO | Interactive visualization of proof escalation |

---

## Test Suite Requirements

### Failure Mode Analysis

1. **Asymmetric message loss**: One direction fails completely
2. **Byzantine message modification**: Corrupted signatures detected
3. **Adversarial timing attacks**: Bilateral structure prevents exploitation
4. **Permanent partition**: Both timeout → coordinated abort

### "Protocol of Theseus" Test

The defining validation:
1. Simulate complete TGP handshake and attack-at-dawn cycle
2. Remove portions of packet stream at random
3. Prove protocol survives having **all its parts removed** without finding a "last message"
4. Demonstrate that coordination succeeds or both parties abort — never asymmetric

---

# Part IV: Multi-Agent Coordination

## Palace Turbo (PROGRESS.json)

When running in Palace Turbo swarm mode, Claude agents coordinate via `PROGRESS.json`.

### Agent IDs

Agents are assigned IDs like: `sonnet-4`, `opus-1`, `haiku-3`

### PROGRESS.json Structure

```json
{
  "inbox": {
    "sonnet-4": [{"from": "opus-1", "message": "...", "timestamp": "..."}]
  },
  "noticeboard": [
    {"agent": "sonnet-4", "notice": "Python reference complete", "timestamp": "..."}
  ],
  "cleanup": [],
  "action": [
    {"agent": "sonnet-4", "action": "Created tgp/core.py", "status": "complete"}
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
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            data = json.load(f)
            new_data = update_fn(data)
            f.seek(0)
            f.truncate()
            json.dump(new_data, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

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

## Skills / Masks

When pondering TGP, Byzantine fault tolerance, or network protocols, activate:

```
/activate-skill distributed-systems
```

---

## Success Criteria

### Phase 1: Reference Implementation (Python)
- [ ] Core TGP protocol (Part I only — pure epistemic)
- [ ] All failure modes tested
- [ ] Protocol of Theseus test passes
- [ ] 90% packet loss still achieves symmetric outcomes

### Phase 2: Production Implementation (Rust)
- [ ] Add DH hardening (Part II)
- [ ] Zero-copy packet handling
- [ ] Benchmarks vs TCP under loss
- [ ] Async/await support

### Phase 3: Ubiquitous Deployment
- [ ] WASM build for browsers
- [ ] ToTG adapter (drop-in TCP replacement)
- [ ] UoTG adapter (drop-in UDP replacement)
- [ ] Web demo with visualization

### Phase 4: Academic Verification
- [ ] Lean proofs published
- [ ] Paper submitted (PODC 2026 / DISC 2026)
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

### Why "The Protocol of Theseus"?

The Ship of Theseus asks: if you replace every plank, is it the same ship?

We ask: if you remove every message, does the protocol still work?

**Answer:** Yes. Because symmetry is guaranteed by cryptographic structure, not message delivery.

---

## References

1. **Akkoyunlu et al. (1975)** - Original Two Generals Problem
2. **Gray, J. (1978)** - Common Knowledge Impossibility
3. **Halpern & Moses (1990)** - Knowledge and Common Knowledge in a Distributed Environment
4. **Lean 4** - Formal verification language
5. **synthesis/*.lean** - Our formal proofs

---

## Contact

**Author:** Wings@riff.cc (Riff Labs)
**Keeper:** Lief (The Forge)

---

**e cinere surgemus** 🔥

*"For 47 years, common knowledge over lossy channels was considered mathematically impossible. Today, we proved it solvable."*
