/-
  Channel Models: When Does Bilateral Flooding Actually Work?

  This file explicitly defines the channel models under which the
  bilateral_t_flooding axiom is VALID vs INVALID.

  KEY INSIGHT: The axiom is NOT universally true. It requires specific
  channel properties that must be explicitly stated and justified.

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

namespace ChannelModels

/-! ## The Core Problem: Local Observability

    Alice's knowledge at decision time:
    - What she created (C_A, D_A, T_A)
    - What she received (C_B, D_B, T_B)
    - The current time vs deadline

    Alice CANNOT directly observe:
    - Whether Bob received T_A
    - Bob's current state
    - Bob's decision

    The bilateral_t_flooding axiom CLAIMS that if Alice has T_B,
    then Bob "will" have T_A. But this requires justification.
-/

/-! ## Channel Model Taxonomy -/

-- A channel model defines message delivery properties
structure ChannelModel where
  -- Is there a bound on delivery time?
  bounded_delay : Bool
  -- Maximum delay (if bounded)
  max_delay : Option Nat
  -- Is loss random or adversarial?
  loss_is_random : Bool
  -- Probability of delivery per attempt (if random)
  delivery_prob : Option Float
  -- Can adversary selectively delay specific messages?
  adversary_can_target : Bool
  deriving Repr

/-! ## Model 1: Synchronous Channel

    Properties:
    - Messages delivered within Δ time units
    - No message loss (or loss is detectable)
    - Adversary cannot delay beyond Δ

    BILATERAL FLOODING VALID: YES
    Proof: If both create T at time t, both flood for Δ.
           All messages arrive by t + Δ. Symmetric by construction.
-/

def synchronous_channel (delta : Nat) : ChannelModel := {
  bounded_delay := true,
  max_delay := some delta,
  loss_is_random := false,  -- No loss
  delivery_prob := some 1.0,
  adversary_can_target := false
}

-- Under synchronous channel, bilateral flooding is PROVABLE
axiom synchronous_bilateral_guarantee :
  ∀ (delta : Nat) (t_alice_created t_bob_created : Nat),
  -- If both created T and both flood for delta time
  t_alice_created + delta < t_bob_created + delta + delta →
  -- Then both receive by max(t_alice_created, t_bob_created) + delta
  True  -- (Simplified; real proof would track message arrival)

/-! ## Model 2: Probabilistic Bounded-Delay Channel

    Properties:
    - Each message has probability p of arriving within Δ
    - Loss is random (not adversarial)
    - Flooding N times gives P(success) = 1 - (1-p)^N

    BILATERAL FLOODING VALID: PROBABILISTICALLY
    As N → ∞, P(both receive | both created) → 1
-/

def probabilistic_channel (p : Float) (delta : Nat) : ChannelModel := {
  bounded_delay := true,
  max_delay := some delta,
  loss_is_random := true,
  delivery_prob := some p,
  adversary_can_target := false
}

-- Probability of at least one success in N attempts
def prob_at_least_one (p : Float) (n : Nat) : Float :=
  1.0 - Float.pow (1.0 - p) n.toFloat

-- Probability BOTH parties receive (assuming independence)
def prob_both_receive (p : Float) (n : Nat) : Float :=
  let p_one := prob_at_least_one p n
  p_one * p_one

-- Example: 99.9% loss, 100 attempts
-- P(one receives) = 1 - 0.999^100 ≈ 0.0952
-- P(both receive) ≈ 0.009 (0.9%)

-- Example: 99.9% loss, 10000 attempts
-- P(one receives) = 1 - 0.999^10000 ≈ 0.99995
-- P(both receive) ≈ 0.9999 (99.99%)

-- The key insight: with enough flooding, probability approaches 1
-- But it's NEVER exactly 1 in finite time

axiom probabilistic_bilateral_approaches_certainty :
  ∀ (p : Float) (epsilon : Float),
  0 < p → p < 1 → 0 < epsilon →
  ∃ (n : Nat), prob_both_receive p n > 1.0 - epsilon

/-! ## Model 3: Fair-Lossy Channel (TGP's Assumed Model)

    Properties:
    - Messages sent infinitely often are delivered with probability 1
    - Loss pattern is "fair" (not adversarially targeted)
    - No bound on individual message delay
    - But: infinite flooding guarantees eventual delivery

    BILATERAL FLOODING VALID: YES (in the limit)
    Key assumption: Both parties flood CONTINUOUSLY until deadline
    And: The deadline is set with enough margin for convergence

    CRITICAL CAVEAT: This is an ASYMPTOTIC guarantee.
    At any finite deadline, there's nonzero (but vanishing) failure probability.
-/

def fair_lossy_channel : ChannelModel := {
  bounded_delay := false,  -- No fixed bound
  max_delay := none,
  loss_is_random := true,
  delivery_prob := none,  -- Varies; but infinite attempts → delivery
  adversary_can_target := false  -- Loss is fair/random
}

-- The fair-lossy guarantee (informal)
-- ∀ message m, if sender floods m infinitely, receiver eventually gets m

-- The bilateral implication:
-- If Alice and Bob both create T and both flood infinitely,
-- both eventually receive the other's T.

-- BUT: "eventually" has no time bound!
-- This is where the deadline problem emerges.

/-! ## Model 4: Adversarial Channel

    Properties:
    - Adversary controls message delivery
    - Can selectively delay or drop messages
    - Can create asymmetric delivery patterns

    BILATERAL FLOODING VALID: NO
    Counterexample: Adversary delays T_A until after deadline,
                   while allowing T_B to arrive.
-/

def adversarial_channel : ChannelModel := {
  bounded_delay := false,
  max_delay := none,
  loss_is_random := false,
  delivery_prob := none,
  adversary_can_target := true  -- This breaks everything
}

-- Under adversarial channel, asymmetry IS possible
-- The adversary can:
-- 1. Let T_B reach Alice before deadline
-- 2. Block T_A from reaching Bob until after deadline
-- Result: Alice attacks, Bob aborts

/-! ## The Timing Attack Scenario

    t=0:   Both start flooding C
    t=10:  Both have C, both create D
    t=20:  Both have D, both create T
    t=25:  Alice receives T_B
    t=30:  DEADLINE
    t=35:  Bob would have received T_A

    At t=30:
    - Alice: has T_A (created), has T_B (received) → ATTACK
    - Bob: has T_B (created), no T_A → ABORT

    This IS asymmetric!

    The question: Under which channel models can this happen?
-/

-- Timing attack is POSSIBLE under:
-- 1. Adversarial channels (adversary delays T_A)
-- 2. Probabilistic channels with insufficient flooding time
-- 3. Fair-lossy channels with premature deadline

-- Timing attack is IMPOSSIBLE under:
-- 1. Synchronous channels (both receive within Δ)
-- 2. Probabilistic channels with sufficient flooding time
-- 3. Fair-lossy channels with "eventually" deadline

/-! ## Resolution: The Margin-Based Deadline

    The key insight: the deadline must be set with sufficient MARGIN
    that the probability of asymmetric delivery is acceptably small.

    Deadline = T_protocol + T_margin

    Where:
    - T_protocol: Time for protocol to reach T level
    - T_margin: Time for bilateral T exchange with high probability

    The margin depends on the channel model:
    - Synchronous: T_margin = Δ (deterministic)
    - Probabilistic: T_margin = f(p, target_probability)
    - Fair-lossy: T_margin = ??? (no fixed bound)
-/

-- Compute required margin for target probability
def required_margin (p : Float) (target : Float) (floods_per_unit : Nat) : Nat :=
  -- Solve: 1 - (1-p)^n > target
  -- n > log(1-target) / log(1-p)
  -- This is a simplification; actual computation would use logarithms
  let n := (1000 : Nat)  -- Placeholder
  n / floods_per_unit

/-! ## What TGP Actually Guarantees

    Under FAIR-LOSSY channel with SYNCHRONIZED DEADLINES:

    1. SAFETY: If both parties decide, they decide the same way.
       - If both have both T's by deadline: both ATTACK
       - If neither has both T's by deadline: both ABORT
       - Mixed states depend on channel model

    2. LIVENESS (probabilistic): With enough flooding time,
       both parties will have both T's with probability → 1.

    3. NO GUARANTEE against adversarial channels.

    The bilateral_t_flooding axiom is VALID under:
    - Synchronous channels (deterministic)
    - Probabilistic channels with margin → ∞ (probabilistic)
    - Fair-lossy channels with margin → ∞ (probabilistic)

    The axiom is INVALID under:
    - Adversarial channels
    - Any channel with insufficient margin
-/

/-! ## The Honest Acknowledgment

    The 6-packet TGP protocol DOES NOT solve the Two Generals Problem
    under ALL channel models. Specifically:

    1. It DOES solve it under synchronous channels (trivially)

    2. It DOES solve it probabilistically under fair-lossy channels,
       where "solve" means:
       - P(symmetric outcome) → 1 as flooding time → ∞
       - At any finite deadline, P(asymmetric) > 0 but vanishing

    3. It does NOT solve it under adversarial channels.

    The claim "TGP solves Two Generals" should be qualified:
    - "TGP solves Two Generals under fair-lossy channels"
    - "TGP achieves probabilistic consensus with arbitrarily high probability"
    - "TGP guarantees safety (no unilateral attack) but not perfect liveness"

    This is still a significant result! Gray's original impossibility
    assumes a specific channel model. TGP works under different assumptions.
-/

/-! ## Why Q Was Originally Included (Hypothesis)

    The Q level might have been an attempt to provide additional
    confirmation that would help with the timing problem.

    Q_A = Sign_A(T_A || T_B)

    If Alice has Q_B, she knows:
    - Bob had T_A and T_B when he signed Q_B
    - Bob was able to create Q_B (so Bob had the full picture)

    But this doesn't actually help! The same timing attack applies:
    - Alice receives Q_B before deadline
    - Bob doesn't receive Q_A before deadline
    - Same asymmetry, just one level deeper

    The Q level adds no structural improvement because:
    - It doesn't change the local observability problem
    - It doesn't change the channel model
    - It just adds one more round of the same pattern

    Conclusion: Q was eliminated because it provides no benefit,
    not because T "solves" the timing problem. The timing problem
    exists at every level and is resolved by channel model choice,
    not by adding more levels.
-/

/-! ## The Two Generals Problem: Precise Formulation

    There are actually MULTIPLE versions of the problem:

    Version 1 (Gray 1978): Achieve COMMON KNOWLEDGE over unreliable channel
    - IMPOSSIBLE under any finite protocol (proven)

    Version 2 (Practical): Achieve COORDINATED ACTION with high probability
    - SOLVABLE with flooding under fair-lossy channels
    - This is what TGP does

    Version 3 (Byzantine): Achieve consensus with f Byzantine faults
    - SOLVABLE with 3f+1 parties (BFT extension)

    TGP's contribution: Showing that Version 2 is solvable with a
    specific protocol structure (proof stapling + flooding).

    The bilateral_t_flooding axiom is the bridge between the
    protocol structure and the channel model. It's valid precisely
    when the channel model guarantees symmetric eventual delivery.
-/

/-! ## Summary: Channel Model Validity Table

    | Channel Model          | bilateral_t_flooding | Notes                    |
    |------------------------|---------------------|--------------------------|
    | Synchronous (Δ-bound)  | ✓ VALID             | Deterministic            |
    | Probabilistic (p, Δ)   | ✓ VALID (limit)     | As margin → ∞            |
    | Fair-lossy             | ✓ VALID (limit)     | As margin → ∞            |
    | Adversarial            | ✗ INVALID           | Timing attack possible   |

    The protocol's guarantees are CONDITIONAL on channel model.
    This should be explicitly stated in any formal claims.
-/

-- Validity predicate for the bilateral axiom
def bilateral_axiom_valid (m : ChannelModel) : Bool :=
  !m.adversary_can_target

-- The axiom is justified iff channel is not adversarial
theorem axiom_requires_fair_channel :
  ∀ (m : ChannelModel),
  bilateral_axiom_valid m = true ↔ m.adversary_can_target = false := by
  intro m
  unfold bilateral_axiom_valid
  simp [Bool.not_eq_true']

#check axiom_requires_fair_channel

end ChannelModels
