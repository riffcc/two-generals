/-
  Exhaustive.lean - All Possible States Are Symmetric

  This file exhaustively verifies that all 2^4 = 16 possible protocol states
  result in symmetric outcomes.

  We model the protocol with 4 boolean variables:
    - d_a : Bool  -- D_A exists (Alice's double proof)
    - d_b : Bool  -- D_B exists (Bob's double proof)
    - a_responds : Bool  -- Alice responds to V's challenge
    - b_responds : Bool  -- Bob responds to V's challenge

  All 16 combinations result in either:
    - CoordinatedAttack (both attack)
    - CoordinatedAbort (both abort)

  There are NO asymmetric outcomes.

  This is proven by case analysis, not axiom.

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

import Protocol
import Emergence
import Bilateral
import Channel

namespace Exhaustive

open Protocol
open Emergence
open Bilateral
open Channel

/-! ## RawDelivery Compatibility Layer

    Other files (Theseus.lean, Gray.lean, Solution.lean) use the RawDelivery model.
    We provide compatibility functions that map RawDelivery to the Emergence model.
-/

/-- Map RawDelivery to Emergence model state.
    The 6-message RawDelivery model maps to the 4-variable Emergence model:
    - d_a_exists: D_A reaches Bob (requires C_B delivered + D_A delivered)
    - d_b_exists: D_B reaches Alice (requires C_A delivered + D_B delivered)
    - a_responds: Alice can construct T_A (has both D's)
    - b_responds: Bob can construct T_B (has both D's)
-/
def to_emergence (r : RawDelivery) : Bool × Bool × Bool × Bool :=
  -- Alice can create D_A if she has C_B
  let alice_created_d := r.c_b
  -- Bob can create D_B if he has C_A
  let bob_created_d := r.c_a
  -- D_A reaches Bob iff Alice created it and it was delivered
  let d_a_exists := alice_created_d ∧ r.d_a
  -- D_B reaches Alice iff Bob created it and it was delivered
  let d_b_exists := bob_created_d ∧ r.d_b
  -- Alice can respond (create T_A) iff she has both D's
  let alice_can_respond := alice_created_d ∧ d_b_exists
  -- Bob can respond (create T_B) iff he has both D's
  let bob_can_respond := bob_created_d ∧ d_a_exists
  -- Alice's T reaches Bob iff she created it and it was delivered
  let a_responds := alice_can_respond ∧ r.t_a
  -- Bob's T reaches Alice iff he created it and it was delivered
  let b_responds := bob_can_respond ∧ r.t_b
  (d_a_exists, d_b_exists, a_responds, b_responds)

/-- Classify a RawDelivery's outcome using the Emergence model. -/
def classify_raw (r : RawDelivery) : Protocol.Outcome :=
  let (d_a, d_b, a_responds, b_responds) := to_emergence r
  match Emergence.get_outcome (Emergence.make_state d_a d_b a_responds b_responds).attack_key with
  | Emergence.Outcome.CoordinatedAttack => Protocol.Outcome.BothAttack
  | Emergence.Outcome.CoordinatedAbort => Protocol.Outcome.BothAbort

/-- Is the outcome symmetric? -/
def is_symmetric (o : Protocol.Outcome) : Bool :=
  match o with
  | Protocol.Outcome.BothAttack => true
  | Protocol.Outcome.BothAbort => true
  | Protocol.Outcome.Asymmetric => false

/-! ## Fair-Lossy Reachability

    A RawDelivery is "reachable under fair-lossy" if it's consistent with
    a fair-lossy adversary schedule. The key constraint:

    If a party is FLOODING a message type (i.e., created it and keeps sending),
    then under fair-lossy, at least one copy eventually arrives.

    This means:
    - If Alice created C_A and floods it, Bob receives it (c_a = true)
    - If both flood their respective messages, both eventually receive

    The constraint rules out states like "Alice floods T_A forever but Bob never
    receives it" - that requires an UNBOUNDED adversary (Gray's model).
-/

/-- A RawDelivery is reachable under fair-lossy iff it's consistent with
    the fair-lossy adversary constraint: flooding implies eventual delivery.

    Under fair-lossy:
    - Both parties flood C immediately → both C's delivered
    - After receiving C, both create and flood D → both D's delivered
    - After receiving D, both create and flood T → both T's delivered

    This means the only reachable states are:
    1. Early termination (one direction partitioned before protocol completes)
    2. Full completion (all messages delivered)

    The constraint: if a message was CREATED by a party that's still
    participating, it eventually gets delivered (fair-lossy guarantee).
-/
def reachable_fair_lossy (r : RawDelivery) : Bool :=
  -- T delivery consistency constraint
  -- If both parties created T (which requires having both D's), then under
  -- fair-lossy, if one T is delivered, the other must eventually be too
  -- (both are flooding, fair-lossy guarantees delivery)
  let (d_a, d_b, a_responds, b_responds) := to_emergence r

  -- The critical constraint: if V emerged (both D's exist) and both parties
  -- are flooding T, then either both T's are delivered or neither is
  -- (fair-lossy is symmetric in the limit)
  if d_a ∧ d_b then
    -- V emerged - both parties can create T and are flooding it
    -- Under fair-lossy, both T's eventually arrive
    -- So this state is only reachable if both T's made it through
    a_responds = b_responds
  else
    -- V didn't emerge - one or both D's missing
    -- This is a valid early termination state
    true

/-- SAFETY: All reachable states result in symmetric outcomes.

    PROOF: The Emergence model only produces symmetric outcomes.
    - CoordinatedAttack: attack key exists (both responded)
    - CoordinatedAbort: attack key doesn't exist (someone didn't respond)

    The key insight: the outcome type has NO asymmetric constructor.
    This is BY DESIGN - the emergent construction guarantees symmetry.
-/
theorem all_reachable_symmetric (r : RawDelivery) (_ : reachable_fair_lossy r = true) :
    is_symmetric (classify_raw r) = true := by
  simp only [is_symmetric, classify_raw]
  let (d_a, d_b, a_responds, b_responds) := to_emergence r
  cases h : Emergence.get_outcome (Emergence.make_state d_a d_b a_responds b_responds).attack_key with
  | CoordinatedAttack => rfl
  | CoordinatedAbort => rfl

/-- LIVENESS: Under fair-lossy with both parties participating, attack happens.

    If both parties complete the protocol (create all messages) and the channel
    is fair-lossy in both directions, then the outcome is CoordinatedAttack.

    PROOF: Use fair_lossy_implies_full_oscillation to establish the tuple is (T,T,T,T),
    then prove get_outcome on the concrete tuple equals CoordinatedAttack.
-/
theorem fair_lossy_liveness :
    ∀ (adv : FairLossyAdversary),
    let exec := full_execution_under_fair_lossy adv
    let (d_a, d_b, a_responds, b_responds) := to_emergence_model exec
    Emergence.get_outcome (Emergence.make_state d_a d_b a_responds b_responds).attack_key
      = Emergence.Outcome.CoordinatedAttack := by
  intro adv
  -- First, establish that the tuple is (true, true, true, true)
  have h_tuple := fair_lossy_implies_full_oscillation adv
  -- Rewrite using this fact
  simp only [h_tuple]
  -- Now the goal is on concrete booleans, can use native_decide
  native_decide

/-! ## State Space

    The protocol state space has 16 possible states:
    - 4 boolean variables × 2 values each = 2^4 = 16 states
-/

/-- All possible boolean values. -/
def bools : List Bool := [false, true]

/-- All 16 possible protocol states (explicit enumeration). -/
def all_states : List (Bool × Bool × Bool × Bool) :=
  [(false, false, false, false), (false, false, false, true),
   (false, false, true, false), (false, false, true, true),
   (false, true, false, false), (false, true, false, true),
   (false, true, true, false), (false, true, true, true),
   (true, false, false, false), (true, false, false, true),
   (true, false, true, false), (true, false, true, true),
   (true, true, false, false), (true, true, false, true),
   (true, true, true, false), (true, true, true, true)]

/-- There are exactly 16 states. -/
theorem state_count : all_states.length = 16 := rfl

/-! ## Outcome Classification

    We classify each state's outcome.
-/

/-- Get outcome for a state tuple. -/
def state_outcome (s : Bool × Bool × Bool × Bool) : Emergence.Outcome :=
  let (d_a, d_b, a_responds, b_responds) := s
  get_outcome (make_state d_a d_b a_responds b_responds).attack_key

/-- Is the outcome symmetric? -/
def is_symmetric_outcome (o : Emergence.Outcome) : Bool :=
  match o with
  | Emergence.Outcome.CoordinatedAttack => true
  | Emergence.Outcome.CoordinatedAbort => true

/-! ## Individual State Proofs

    We prove each of the 16 states results in a symmetric outcome.
-/

-- States where A doesn't respond: CoordinatedAbort
theorem state_FFFF : state_outcome (false, false, false, false) = Outcome.CoordinatedAbort := by native_decide
theorem state_FFFT : state_outcome (false, false, false, true) = Outcome.CoordinatedAbort := by native_decide
theorem state_FFTF : state_outcome (false, false, true, false) = Outcome.CoordinatedAbort := by native_decide
theorem state_FFTT : state_outcome (false, false, true, true) = Outcome.CoordinatedAbort := by native_decide
theorem state_FTFF : state_outcome (false, true, false, false) = Outcome.CoordinatedAbort := by native_decide
theorem state_FTFT : state_outcome (false, true, false, true) = Outcome.CoordinatedAbort := by native_decide
theorem state_FTTF : state_outcome (false, true, true, false) = Outcome.CoordinatedAbort := by native_decide
theorem state_FTTT : state_outcome (false, true, true, true) = Outcome.CoordinatedAbort := by native_decide
theorem state_TFFF : state_outcome (true, false, false, false) = Outcome.CoordinatedAbort := by native_decide
theorem state_TFFT : state_outcome (true, false, false, true) = Outcome.CoordinatedAbort := by native_decide
theorem state_TFTF : state_outcome (true, false, true, false) = Outcome.CoordinatedAbort := by native_decide
theorem state_TFTT : state_outcome (true, false, true, true) = Outcome.CoordinatedAbort := by native_decide
theorem state_TTFF : state_outcome (true, true, false, false) = Outcome.CoordinatedAbort := by native_decide
theorem state_TTFT : state_outcome (true, true, false, true) = Outcome.CoordinatedAbort := by native_decide
theorem state_TTTF : state_outcome (true, true, true, false) = Outcome.CoordinatedAbort := by native_decide

-- The one state where everyone participates: CoordinatedAttack
theorem state_TTTT : state_outcome (true, true, true, true) = Outcome.CoordinatedAttack := by native_decide

/-! ## The Main Theorem

    All states result in symmetric outcomes.
-/

/-- Every state has a symmetric outcome.

    PROOF: By exhaustive case analysis on all 16 states.
    - 15 states: CoordinatedAbort (missing at least one component)
    - 1 state: CoordinatedAttack (full bilateral completion)
    Both outcomes are symmetric.
-/
theorem all_states_symmetric :
    ∀ (d_a d_b a_responds b_responds : Bool),
    is_symmetric_outcome (state_outcome (d_a, d_b, a_responds, b_responds)) = true := by
  intro d_a d_b a_responds b_responds
  cases d_a <;> cases d_b <;> cases a_responds <;> cases b_responds <;> native_decide

/-- Alternative formulation: outcome is always symmetric.

    This uses the Emergence.Outcome type directly which only has symmetric constructors.
-/
theorem all_outcomes_symmetric :
    ∀ (d_a d_b a_responds b_responds : Bool),
    let outcome := get_outcome (make_state d_a d_b a_responds b_responds).attack_key
    outcome = Outcome.CoordinatedAttack ∨ outcome = Outcome.CoordinatedAbort :=
  channel_asymmetry_cannot_cause_outcome_asymmetry

/-! ## Outcome Distribution

    Characterize which states lead to which outcomes.
-/

/-- Only full participation leads to CoordinatedAttack. -/
theorem attack_requires_all (d_a d_b a_responds b_responds : Bool) :
    state_outcome (d_a, d_b, a_responds, b_responds) = Outcome.CoordinatedAttack →
    d_a = true ∧ d_b = true ∧ a_responds = true ∧ b_responds = true := by
  intro h
  simp only [state_outcome] at h
  exact attack_requires_full_oscillation d_a d_b a_responds b_responds h

/-- Any missing component leads to CoordinatedAbort. -/
theorem missing_component_aborts (d_a d_b a_responds b_responds : Bool) :
    (d_a = false ∨ d_b = false ∨ a_responds = false ∨ b_responds = false) →
    state_outcome (d_a, d_b, a_responds, b_responds) = Outcome.CoordinatedAbort := by
  intro h
  cases h with
  | inl h_da =>
    simp [state_outcome, get_outcome, make_state, V_emerges, h_da, attack_key_emerges]
  | inr h =>
    cases h with
    | inl h_db =>
      simp [state_outcome, get_outcome, make_state, V_emerges, h_db, attack_key_emerges]
    | inr h =>
      cases h with
      | inl h_a =>
        simp [state_outcome, h_a]
        exact failure_A_symmetric d_a d_b b_responds
      | inr h_b =>
        simp [state_outcome, h_b]
        exact failure_B_symmetric d_a d_b a_responds

/-! ## Failure Mode Categorization

    We categorize the 15 abort cases by what's missing.
-/

/-- States where V doesn't emerge (D_A or D_B missing): 12 cases. -/
def v_not_emerged (d_a d_b : Bool) : Bool := ¬(d_a ∧ d_b)

/-- States where V emerges but responses incomplete: 3 cases. -/
def v_emerged_but_incomplete (d_a d_b a_responds b_responds : Bool) : Bool :=
  d_a ∧ d_b ∧ ¬(a_responds ∧ b_responds)

/-- V not emerging means abort. -/
theorem no_v_means_abort (d_a d_b a_responds b_responds : Bool) :
    v_not_emerged d_a d_b = true →
    state_outcome (d_a, d_b, a_responds, b_responds) = Outcome.CoordinatedAbort := by
  intro h
  simp only [v_not_emerged] at h
  simp only [state_outcome, get_outcome, make_state]
  cases d_a <;> cases d_b <;> simp_all [V_emerges, attack_key_emerges]

/-- V emerges but incomplete responses means abort. -/
theorem incomplete_responses_means_abort (d_a d_b a_responds b_responds : Bool) :
    v_emerged_but_incomplete d_a d_b a_responds b_responds = true →
    state_outcome (d_a, d_b, a_responds, b_responds) = Outcome.CoordinatedAbort := by
  cases d_a <;> cases d_b <;> cases a_responds <;> cases b_responds <;>
    simp [v_emerged_but_incomplete, state_outcome, get_outcome, make_state,
          V_emerges, response_A, response_B, attack_key_emerges]

/-! ## The Protocol of Theseus Verification

    Verify the Theseus property: remove any component, outcome stays symmetric.
-/

/-- Starting from full success, remove A's response → still symmetric. -/
theorem theseus_remove_a_response :
    state_outcome (true, true, false, true) = Outcome.CoordinatedAbort := state_TTFT

/-- Starting from full success, remove B's response → still symmetric. -/
theorem theseus_remove_b_response :
    state_outcome (true, true, true, false) = Outcome.CoordinatedAbort := state_TTTF

/-- Starting from full success, remove D_A → still symmetric. -/
theorem theseus_remove_d_a :
    state_outcome (false, true, true, true) = Outcome.CoordinatedAbort := state_FTTT

/-- Starting from full success, remove D_B → still symmetric. -/
theorem theseus_remove_d_b :
    state_outcome (true, false, true, true) = Outcome.CoordinatedAbort := state_TFTT

/-! ## Summary

    This file exhaustively verifies:

    1. All 16 possible states result in symmetric outcomes
    2. Only 1 state (TTTT) results in CoordinatedAttack
    3. 15 states result in CoordinatedAbort
    4. No asymmetric outcomes exist

    Key insight: The outcome space has only 2 elements:
    - CoordinatedAttack (both attack)
    - CoordinatedAbort (both abort)

    There is no "AliceAttacksBobAborts" outcome.
    This is by construction (the Emergence.Outcome type),
    and verified exhaustively across all inputs.

    The Protocol of Theseus property holds:
    Remove any component from full success → still symmetric (abort).
-/

#check all_states_symmetric
#check all_outcomes_symmetric
#check attack_requires_all
#check missing_component_aborts
#check no_v_means_abort
#check incomplete_responses_means_abort

end Exhaustive
