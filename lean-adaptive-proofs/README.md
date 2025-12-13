# Adaptive Flooding Protocol - Lean 4 Formal Proofs

## Overview

This directory contains Lean 4 formal proofs for the **Adaptive Flooding Protocol**, an extension to the Two Generals Protocol (TGP) that adds dynamic rate modulation while preserving all safety properties.

### Key Innovation

Instead of constant flooding, nodes can **dynamically adjust** flood rates based on:
- Data transfer needs (idle vs active)
- Network conditions (congestion, latency)
- Application requirements (priority, QoS)

The adaptive layer adds:
- **Drip Mode**: Slow to near-zero packets when idle
- **Burst Mode**: Instantly ramp to max speed when needed
- **Symmetric Control**: Both parties can independently modulate
- **Proof Stapling Preserved**: Adaptive rate doesn't break bilateral construction

## Proof Structure

### 1. AdaptiveBilateral.lean

**Main Theorem**: `adaptive_preserves_bilateral`

Proves that adaptive rate modulation doesn't break the bilateral construction property:
```lean
theorem adaptive_preserves_bilateral
    (Q_A : TwoGenerals.PartyState → Prop)
    (rate_A rate_B : RateFunction)
    (s : AdaptiveProtocolState)
    (h_construct_A : Constructible Q_A rate_A s.alice)
    (h_min_rate_A : ∀ t, rate_A t > 0)
    (h_min_rate_B : ∀ t, rate_B t > 0) :
    ∃ (Q_B : TwoGenerals.PartyState → Prop),
      Q_B = fun s => TwoGenerals.can_construct_receipt s ∧
                     (TwoGenerals.counterparty_Q Q_A) s ∧
      Constructible Q_B rate_B s.bob
```

**Key Insight**: Flood rate affects *when* proofs arrive, not *what* they contain. The bilateral construction property is preserved regardless of timing.

### 2. Convergence.lean

**Main Theorem**: `adaptive_convergence`

Proves that the protocol converges under fair channel assumptions:
```lean
theorem adaptive_convergence
    (trace : Trace)
    (fair : FairChannel trace) :
    Eventually (fun s => s.alice.toPartyState.decision.isSome ∧
                          s.bob.toPartyState.decision.isSome) trace
```

**Key Insight**: Even with dynamic rate modulation, as long as the channel is fair (messages eventually get through), the protocol will complete.

### 3. RateSafety.lean

**Main Theorem**: `rate_modulation_safe`

Proves that rate modulation maintains safe bounds:
```lean
theorem rate_modulation_safe (c : AdaptiveController)
    (h_valid : ValidController c)
    (data_needed : Bool) :
    c.min_rate ≤ modulate_rate c data_needed ∧
    modulate_rate c data_needed ≤ c.max_rate
```

**Key Insight**: The modulation algorithm is a safe performance optimization that doesn't affect protocol correctness.

## Core Properties Proven

### 1. Bilateral Preservation
- Adaptive rates don't break bilateral construction
- Proof stapling works regardless of flood rate
- Structural symmetry is maintained

### 2. Convergence Guarantee
- Protocol completes under fair channel conditions
- Progress measure converges (bounded, monotonic)
- Liveness is guaranteed (no deadlock)

### 3. Rate Modulation Safety
- Rate always stays within [min_rate, max_rate]
- Ramp up/down behavior is correct
- Boundaries are stable fixed points
- Protocol safety is preserved

## Mathematical Model

### Rate Function
```lean
def RateFunction := Time → Nat
```

A function mapping time to packet rate (packets/sec).

### Adaptive Controller
```lean
structure AdaptiveController where
  min_rate : Nat      -- Minimum packets/sec (drip mode)
  max_rate : Nat      -- Maximum packets/sec (burst mode)
  current_rate : Nat  -- Current flood rate
  ramp_up : Nat       -- Acceleration (packets/sec²)
  ramp_down : Nat     -- Deceleration (packets/sec²)
```

### Rate Modulation Algorithm
```lean
def modulate_rate (c : AdaptiveController) (data_needed : Bool) : Nat :=
  if data_needed && c.current_rate < c.max_rate then
    min (c.current_rate + c.ramp_up) c.max_rate
  else if !data_needed && c.current_rate > c.min_rate then
    max (c.current_rate - c.ramp_down) c.min_rate
  else
    c.current_rate
```

## Relationship to Base TGP

The adaptive flooding protocol:

1. **Extends** TGP with rate modulation
2. **Preserves** all safety properties (bilateral construction, symmetry)
3. **Adds** performance optimization (dynamic rates)
4. **Maintains** convergence guarantees (under fair channel)

### What Changes
- Message timing (when packets are sent)
- Flood intensity (how many packets per second)

### What Doesn't Change
- Protocol structure (C → D → T → Q)
- Proof content (what's in each message)
- Safety properties (bilateral construction)
- Decision rules (when to Attack/Abort)

## Verification Summary

### Total Theorems: 18

**AdaptiveBilateral.lean** (6 theorems):
- `rate_bounded` - Rate stays within bounds
- `adaptive_preserves_bilateral` - Bilateral construction preserved
- `rate_modulation_safe` - Rate modulation is safe
- `rate_never_below_min` - Never below minimum
- `rate_never_above_max` - Never above maximum
- `safety_preserved_under_adaptive_rates` - Core safety preserved

**Convergence.lean** (4 theorems):
- `progress_converges` - Progress measure converges
- `adaptive_convergence` - Protocol converges
- `adaptive_liveness` - Liveness guaranteed
- `rate_modulation_preserves_convergence` - Convergence preserved

**RateSafety.lean** (8 theorems):
- `rate_modulation_safe` - Main safety theorem
- `ramp_up_positive` - Ramp up increases rate
- `ramp_down_nonnegative` - Ramp down decreases rate
- `stable_at_max` - Stable at maximum
- `stable_at_min` - Stable at minimum
- `boundary_fixed_points` - Boundaries are fixed points
- `modulation_monotonic` - Monotonic behavior
- `bilateral_construction_rate_independent` - Rate independence

### Axioms Used: 0

All theorems are proven from definitions and the base TGP axioms. No new axioms are introduced for the adaptive layer.

## Key Insights

### 1. Rate Independence
The adaptive flooding protocol works because **rate modulation is orthogonal to protocol correctness**:
- Rate affects *timing* (when messages arrive)
- Protocol depends on *content* (what messages contain)
- Safety properties are *timing-independent*

### 2. Fair Channel Sufficiency
The protocol converges under a **fair channel** assumption (weaker than reliable delivery):
- Messages cannot be blocked forever
- Some packets eventually get through
- No requirement for ordered or timely delivery

### 3. Safety by Construction
The rate modulation algorithm is **safe by construction**:
- Bounded by min_rate and max_rate
- Monotonic with respect to data needs
- Stable at boundaries
- Preserves all protocol invariants

## Comparison with Base TGP

| Property | Base TGP | Adaptive TGP |
|----------|----------|--------------|
| Safety | ✓ Proven | ✓ Preserved |
| Liveness | ✓ Fair channel | ✓ Fair channel |
| Bilateral construction | ✓ Proven | ✓ Preserved |
| Rate modulation | Constant | Dynamic |
| Efficiency | Fixed overhead | Adaptive overhead |
| Implementation | Simple | State machine |

## Building and Verification

### Prerequisites
- Lean 4 (v4.26.0-rc2 or later)
- Mathlib (v4.26.0-rc2)
- Lake build system

### Build
```bash
lake build
```

### Run Tests
```bash
lake test
```

### Verify Theorems
```bash
# In Lean REPL
import AdaptiveFlooding.AdaptiveBilateral
import AdaptiveFlooding.Convergence
import AdaptiveFlooding.RateSafety

# Check theorems
#check adaptive_preserves_bilateral
#check adaptive_convergence
#check rate_modulation_safe
```

## Files

```
📁 lean-adaptive-proofs/
├── 📄 AdaptiveBilateral.lean    # Bilateral preservation theorem
├── 📄 Convergence.lean          # Convergence under fair channel
├── 📄 RateSafety.lean           # Rate modulation safety
└── 📄 README.md                 # This file
```

## References

1. **Base TGP Proof**: `/mnt/castle/garage/two-generals-public/lean4/TwoGenerals.lean`
2. **Design Document**: `/mnt/castle/garage/two-generals-public/ADAPTIVE_TGP_DESIGN.md`
3. **Original TGP Solution**: Wings@riff.cc (Riff Labs), November 5, 2025

## Status

✅ **All theorems proven** (0 sorry statements)
✅ **Documentation complete**
✅ **Ready for integration**

## Next Steps

1. ✅ Formal proofs (this work)
2. ⏳ Rust implementation
3. ⏳ Integration with TGP
4. ⏳ Benchmarking

---

**Wings@riff.cc (Riff Labs)** - Adaptive Flooding Extension
**Formal Verification**: Claude Opus 4.5
**Date**: December 11, 2025
