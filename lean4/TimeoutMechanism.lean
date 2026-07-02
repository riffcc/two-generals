/-
  ⚠️  DEPRECATED — LEGACY (v1) LAYER  ⚠️

  This file is part of the SUPERSEDED `lean4/` v1 formalization.
  The CANONICAL, current formalization is `lean4/v2/` (6-packet C→D→T model),
  which is what the paper claims (`paper/main.tex`). New work belongs in v2.

  KNOWN UNSOUNDNESS IN THIS FILE:
  `bilateral_receipt_property` (below) is an *axiom* asserting
  `alice.has_receipt → bob.has_receipt`, i.e. a ZERO-WIDTH delivery window.
  This is the bounded-deadline ε assumed into existence. The theorem
  `timeout_safety_with_bilateral` inherits its conclusion from this axiom —
  it is NOT independently proven for the timed case. The honest treatment
  lives in v2 as the terminal-state symmetry result (`LocalDetect.lean`,
  `gray_unreliable_always_symmetric`); the timed/deadline regime is
  intentionally left unmechanized there and stated in the paper as
  safety-with-probability 1−ε.

  ----------------------------------------------------------------
  Original v1 module doc:

  Timeout Mechanism for Two Generals Protocol.
  Formalizes coordinated abort via timeout mechanism.
-/

import Mathlib.Tactic

namespace TimeoutMechanism

-- Time type for timeout calculations
axiom Time : Type
noncomputable axiom Time.zero : Time
noncomputable axiom Time.add : Time → Time → Time
axiom Time.le : Time → Time → Prop
axiom Time.lt : Time → Time → Prop
noncomputable axiom Time.sub : Time → Time → Time
noncomputable axiom Time.repr : Time → String

noncomputable instance : OfNat Time n := ⟨Time.zero⟩
noncomputable instance : Add Time := ⟨Time.add⟩
instance : LE Time := ⟨Time.le⟩
instance : LT Time := ⟨Time.lt⟩
noncomputable instance : Sub Time := ⟨Time.sub⟩
noncomputable instance : Repr Time := ⟨fun t _ => Time.repr t⟩

-- Decidability for time comparisons
axiom time_lt_decidable : ∀ (a b : Time), Decidable (a < b)
axiom time_le_decidable : ∀ (a b : Time), Decidable (a ≤ b)

-- Boolean theorems (previously axioms, now proven via Mathlib)
theorem bool_not_true_eq_false (b : Bool) (h : ¬b = true) : b = false := by
  cases b <;> simp_all

theorem bool_not_false_eq_true (b : Bool) (h : ¬b = false) : b = true := by
  cases b <;> simp_all

-- Time axioms
axiom time_le_refl : ∀ (t : Time), t ≤ t
axiom time_le_trans : ∀ (a b c : Time), a ≤ b → b ≤ c → a ≤ c
axiom time_add_comm : ∀ (a b : Time), a + b = b + a
axiom time_add_le : ∀ (a b c : Time), a ≤ b → a + c ≤ b + c
axiom time_le_antisymm : ∀ (a b : Time), a ≤ b → b ≤ a → a = b

/-! ## Timeout Configuration -/

-- Global timeout configuration (shared by both parties)
structure TimeoutConfig where
  max_wait : Time              -- Maximum time to wait for messages
  start_time : Time            -- Protocol start time

noncomputable instance : Repr TimeoutConfig := ⟨fun _ _ => "TimeoutConfig"⟩

-- Current time in the protocol
axiom current_time : Time

-- Check if timeout has been exceeded
noncomputable def is_timeout (config : TimeoutConfig) (now : Time) : Bool :=
  -- Timeout if (now - start_time) > max_wait
  -- Simplified to: now > start_time + max_wait
  match time_lt_decidable (config.start_time + config.max_wait) now with
  | Decidable.isTrue _ => true
  | Decidable.isFalse _ => false

/-! ## Decision Types -/

-- Decision outcomes
inductive Decision : Type where
  | Attack : Decision
  | Abort : Decision
  deriving Repr, DecidableEq

-- Decisions are distinct (previously axiom, now proven via decide)
theorem attack_ne_abort : Decision.Attack ≠ Decision.Abort := by decide

-- Party state with receipt capability
structure PartyState where
  has_receipt : Bool           -- Whether party has bilateral receipt
  decision : Option Decision   -- Decision made (if any)
  deriving Repr

/-! ## Decision Logic -/

-- Make decision based on receipt and timeout
-- If has receipt: Attack
-- If timeout and no receipt: Abort
-- Otherwise: No decision yet
noncomputable def decide_with_timeout (state : PartyState) (config : TimeoutConfig) (now : Time) : Option Decision :=
  if state.has_receipt then
    some Decision.Attack
  else if is_timeout config now then
    some Decision.Abort
  else
    none

/-! ## Protocol State With Timeout -/

structure ProtocolStateTimeout where
  alice : PartyState
  bob : PartyState
  config : TimeoutConfig
  current_time : Time

noncomputable instance : Repr ProtocolStateTimeout := ⟨fun _ _ => "ProtocolStateTimeout"⟩

-- Both parties make decisions using same timeout config
noncomputable def protocol_decisions (s : ProtocolStateTimeout) : ProtocolStateTimeout :=
  { s with
    alice := { s.alice with decision := decide_with_timeout s.alice s.config s.current_time },
    bob := { s.bob with decision := decide_with_timeout s.bob s.config s.current_time }
  }

/-! ## Timeout Theorems -/

-- Theorem 1: Receipt always leads to Attack decision
theorem receipt_implies_attack (state : PartyState) (config : TimeoutConfig) (now : Time)
  (h_receipt : state.has_receipt = true) :
  decide_with_timeout state config now = some Decision.Attack := by
  unfold decide_with_timeout
  simp [h_receipt]

-- Theorem 2: Timeout without receipt leads to Abort decision
theorem timeout_without_receipt_implies_abort (state : PartyState) (config : TimeoutConfig) (now : Time)
  (h_no_receipt : state.has_receipt = false)
  (h_timeout : is_timeout config now = true) :
  decide_with_timeout state config now = some Decision.Abort := by
  unfold decide_with_timeout
  simp [h_no_receipt, h_timeout]

-- Theorem 3: Coordinated timeout → coordinated abort
-- This is the key safety property for timeout mechanism
theorem timeout_coordination (s : ProtocolStateTimeout)
  (h_no_receipts : s.alice.has_receipt = false ∧ s.bob.has_receipt = false)
  (h_timeout : is_timeout s.config s.current_time = true) :
  (protocol_decisions s).alice.decision = some Decision.Abort ∧
  (protocol_decisions s).bob.decision = some Decision.Abort := by
  unfold protocol_decisions
  simp
  constructor
  · -- Alice aborts
    have h_alice := timeout_without_receipt_implies_abort s.alice s.config s.current_time h_no_receipts.1 h_timeout
    exact h_alice
  · -- Bob aborts
    have h_bob := timeout_without_receipt_implies_abort s.bob s.config s.current_time h_no_receipts.2 h_timeout
    exact h_bob

/-! ## Safety Under Timeout -/

-- Note: timeout_safety without bilateral receipt property has edge cases where
-- one party has receipt and other doesn't. These cases are impossible in the real
-- protocol (bilateral receipt property ensures both parties have receipt or neither do).
-- See timeout_safety_with_bilateral below for the complete, correct safety theorem.

/-! ## Integration With Protocol -/

-- Axiom: Bilateral receipt means both parties have it
-- ⚠️ UNPROVEN AND UNSOUND FOR THE TIMED CASE: this asserts a zero-width
-- delivery window (alice.has_receipt → bob.has_receipt at the same instant),
-- which is exactly the bounded-deadline ε assumed away. See the file header.
-- Do NOT cite timeout_safety_with_bilateral as a mechanized result.
axiom bilateral_receipt_property : ∀ (s : ProtocolStateTimeout),
  s.alice.has_receipt = true → s.bob.has_receipt = true

axiom bilateral_receipt_property_sym : ∀ (s : ProtocolStateTimeout),
  s.bob.has_receipt = true → s.alice.has_receipt = true

-- Theorem: With bilateral receipt property, safety always holds
theorem timeout_safety_with_bilateral (s : ProtocolStateTimeout)
  (h_both : (protocol_decisions s).alice.decision.isSome = true ∧
            (protocol_decisions s).bob.decision.isSome = true) :
  (protocol_decisions s).alice.decision = (protocol_decisions s).bob.decision := by
  simp [protocol_decisions]
  -- Case split on Alice's receipt status
  by_cases h_alice_receipt : s.alice.has_receipt = true
  · -- Alice has receipt → Bob has receipt (bilateral property)
    have h_bob_receipt := bilateral_receipt_property s h_alice_receipt
    -- Both attack
    have ha := receipt_implies_attack s.alice s.config s.current_time h_alice_receipt
    have hb := receipt_implies_attack s.bob s.config s.current_time h_bob_receipt
    simp [ha, hb]
  · -- Alice doesn't have receipt
    have h_alice_false := bool_not_true_eq_false s.alice.has_receipt h_alice_receipt
    by_cases h_bob_receipt : s.bob.has_receipt = true
    · -- Bob has receipt → Alice has receipt (bilateral property)
      have h_alice_has := bilateral_receipt_property_sym s h_bob_receipt
      -- Contradiction with h_alice_receipt
      simp [h_alice_has] at h_alice_receipt
    · -- Neither has receipt, both must timeout
      have h_bob_false := bool_not_true_eq_false s.bob.has_receipt h_bob_receipt
      -- For both to have decisions without receipts, timeout must have occurred
      by_cases h_timeout : is_timeout s.config s.current_time = true
      · -- Both timeout → both abort
        have ha := timeout_without_receipt_implies_abort s.alice s.config s.current_time h_alice_false h_timeout
        have hb := timeout_without_receipt_implies_abort s.bob s.config s.current_time h_bob_false h_timeout
        simp [ha, hb]
      · -- No timeout, no receipts → neither has decision (contradicts h_both)
        have h_timeout_false := bool_not_true_eq_false (is_timeout s.config s.current_time) h_timeout
        -- Alice decision must be none
        have ha : decide_with_timeout s.alice s.config s.current_time = none := by
          unfold decide_with_timeout
          simp [h_alice_false, h_timeout_false]
        -- But h_both.1 says Alice has a decision
        have h_alice_decision : (protocol_decisions s).alice.decision = none := by
          simp [protocol_decisions, ha]
        rw [h_alice_decision] at h_both
        simp at h_both

/-! ## Practical Examples -/

-- Example: Standard timeout configuration (5 seconds)
noncomputable def standard_timeout_config : TimeoutConfig :=
  { max_wait := 0,  -- Placeholder: 5 seconds
    start_time := 0 }

-- Example: Both parties timeout without receipts
noncomputable def timeout_scenario : ProtocolStateTimeout :=
  { alice := { has_receipt := false, decision := none },
    bob := { has_receipt := false, decision := none },
    config := standard_timeout_config,
    current_time := 0 }  -- Placeholder: start_time + 10 seconds

/-! ## Verification Summary -/

-- ✅ Layer 3 (Timeout Mechanism) COMPLETE: 7 theorems proven, 0 sorry statements
--
-- PROVEN THEOREMS:
-- 1. receipt_implies_attack ✓
--    If party has bilateral receipt → always decides Attack
--
-- 2. timeout_without_receipt_implies_abort ✓
--    If party has no receipt and timeout occurs → decides Abort
--
-- 3. timeout_coordination ✓
--    If neither party has receipt and timeout occurs → both decide Abort
--    KEY: This proves coordinated failure via timeout mechanism
--
-- 4. timeout_safety_with_bilateral ✓
--    With bilateral receipt property → decisions always coordinated
--    Uses bilateral_receipt_property axioms (to be proven in Layer 4)
--    This is the COMPLETE safety theorem for the timeout mechanism
--
-- 5. bool_not_true_eq_false ✓ - NEW: Proven via Mathlib (was axiom)
-- 6. bool_not_false_eq_true ✓ - NEW: Proven via Mathlib (was axiom)
-- 7. attack_ne_abort ✓ - NEW: Proven via decide (was axiom)
--
-- AXIOMS ELIMINATED via Mathlib:
-- - bool_not_true_eq_false (boolean logic)
-- - bool_not_false_eq_true (boolean logic)
-- - attack_ne_abort (Decision.Attack ≠ Decision.Abort)
--
-- REMAINING AXIOMS (14 - Time type and protocol properties):
-- - Time type axioms (7): Time, zero, add, le, lt, sub, repr
-- - Time decidability (2): time_lt_decidable, time_le_decidable
-- - Time properties (5): le_refl, le_trans, add_comm, add_le, le_antisymm
-- - current_time: Current time value
-- - bilateral_receipt_property: Alice has receipt → Bob has receipt
-- - bilateral_receipt_property_sym: Bob has receipt → Alice has receipt
--
-- KEY RESULTS:
-- 1. Timeout provides coordinated abort (when neither has receipt)
-- 2. Receipt provides coordinated attack (when both have receipt)
-- 3. Mixed cases (one has, one doesn't) are excluded by bilateral axioms
-- 4. Integration with Layer 2 (NetworkModel) ensures high-probability receipt delivery
-- 5. Integration with Layer 1 (TwoGenerals) provides bilateral receipt property
--
-- NEXT: Layer 4 (MainTheorem) will integrate all layers and prove bilateral property
-- from TwoGenerals.lean's cryptographic structure, validating the bilateral axioms.

#check receipt_implies_attack
#check timeout_without_receipt_implies_abort
#check timeout_coordination
#check timeout_safety_with_bilateral

end TimeoutMechanism
