/-
  Epistemic.lean - Formal Epistemic Semantics for TGP

  This file proves that TGP achieves COMMON KNOWLEDGE of the attack capability
  in the formal sense of distributed epistemic logic.

  BACKGROUND:
  Common knowledge of event E is defined as the greatest fixed point:
    CK(E) = E ∧ K_A(E) ∧ K_B(E) ∧ K_A(K_B(E)) ∧ K_B(K_A(E)) ∧ ...

  Or equivalently:
    CK(E) = E ∧ K_A(CK(E)) ∧ K_B(CK(E))

  KEY INSIGHT:
  In TGP, the attack key is EMERGENT and IDENTICAL for both parties.
  If Alice has the attack key, she KNOWS Bob has it too (and vice versa)
  because the key cannot exist without both parties completing.

  This gives us:
    attack_key.isSome ↔ Alice has key ↔ Bob has key

  Combined with the theorem "attack_key.isSome → both responded",
  which is known to both parties (it's part of the protocol spec),
  we get common knowledge in S5-style semantics.

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

import Emergence

namespace Epistemic

open Emergence

/-! ## Possible Worlds

    A possible world is a complete protocol state.
    We use EmergenceState as our world type.
-/

/-- A possible world in the epistemic model. -/
abbrev World := EmergenceState

/-! ## Local State (What Each Party Can Observe)

    Each party's local state determines what they can distinguish.
    Two worlds are indistinguishable to a party if their local state is the same.
-/

/-- Alice's local state: what she can observe.
    - Her own D creation status (d_a_exists)
    - Whether she received Bob's D (d_b_exists)
    - Her own response status (response_a.isSome)
    - The attack key (if it exists, she has it)

    NOTE: Alice does NOT directly observe Bob's response status.
    She can only infer it from the attack key via the bilateral theorem. -/
structure AliceLocalState where
  has_d_a : Bool           -- Did she create D_A?
  received_d_b : Bool      -- Did she receive D_B?
  has_response_a : Bool    -- Did she respond?
  has_attack_key : Bool    -- Does she have the attack key?
  deriving DecidableEq, Repr

/-- Bob's local state: symmetric to Alice's.
    NOTE: Bob does NOT directly observe Alice's response status. -/
structure BobLocalState where
  has_d_b : Bool
  received_d_a : Bool
  has_response_b : Bool
  has_attack_key : Bool
  deriving DecidableEq, Repr

/-- Extract Alice's local state from a world. -/
def alice_local (w : World) : AliceLocalState := {
  has_d_a := w.d_a_exists
  received_d_b := w.d_b_exists
  has_response_a := w.response_a.isSome
  has_attack_key := w.attack_key.isSome
}

/-- Extract Bob's local state from a world. -/
def bob_local (w : World) : BobLocalState := {
  has_d_b := w.d_b_exists
  received_d_a := w.d_a_exists
  has_response_b := w.response_b.isSome
  has_attack_key := w.attack_key.isSome
}

/-! ## Accessibility Relations

    w' is accessible from w to Alice iff Alice's local state is the same.
    This captures: Alice cannot distinguish worlds that look the same to her.
-/

/-- Alice's accessibility relation: w' accessible from w iff same local state. -/
def alice_accessible (w w' : World) : Prop :=
  alice_local w = alice_local w'

/-- Bob's accessibility relation. -/
def bob_accessible (w w' : World) : Prop :=
  bob_local w = bob_local w'

/-! ## Knowledge Operators

    K_A(P) at world w means: P holds in all worlds accessible to A from w.
    K_B(P) at world w means: P holds in all worlds accessible to B from w.
-/

/-- A proposition about worlds. -/
abbrev WorldProp := World → Prop

/-- Knowledge operator for Alice: K_A(P) holds at w iff P holds in all w' accessible to A. -/
def K_A (P : WorldProp) : WorldProp :=
  fun w => ∀ w', alice_accessible w w' → P w'

/-- Knowledge operator for Bob. -/
def K_B (P : WorldProp) : WorldProp :=
  fun w => ∀ w', bob_accessible w w' → P w'

/-- Mutual knowledge: both know P. -/
def E (P : WorldProp) : WorldProp :=
  fun w => K_A P w ∧ K_B P w

/-! ## Common Knowledge

    Common knowledge is the greatest fixed point:
    CK(P) = P ∧ E(CK(P))

    We define it as: P holds and everyone knows P to arbitrary depth.
-/

/-- Knowledge to depth n. -/
def K_depth (n : Nat) (P : WorldProp) : WorldProp :=
  match n with
  | 0 => P
  | n + 1 => fun w => K_depth n P w ∧ E (K_depth n P) w

/-- Common knowledge: P holds to all depths.
    CK(P) = ∀n, K_depth n P -/
def CK (P : WorldProp) : WorldProp :=
  fun w => ∀ n, K_depth n P w

/-! ## The Attack Key Proposition

    E := "attack key exists"
-/

/-- The proposition: attack key exists. -/
def attack_key_exists : WorldProp :=
  fun w => w.attack_key.isSome

/-! ## Key Lemma: Attack Key is Locally Observable

    If the attack key exists, BOTH parties can observe it locally.
    This is because the attack key is the same emergent artifact.
-/

/-- If attack key exists, Alice observes it. -/
theorem alice_observes_attack_key (w : World) :
    attack_key_exists w → (alice_local w).has_attack_key = true := by
  intro h
  simp [alice_local, attack_key_exists] at *
  exact h

/-- If attack key exists, Bob observes it. -/
theorem bob_observes_attack_key (w : World) :
    attack_key_exists w → (bob_local w).has_attack_key = true := by
  intro h
  simp [bob_local, attack_key_exists] at *
  exact h

/-! ## Key Lemma: Attack Key Implies Both Responded

    This is the crucial theorem that enables common knowledge.
    If the attack key exists, both parties must have responded.
-/

/-- Well-formed worlds: attack_key is computed from attack_key_emerges.
    This is always true for states constructed via make_state. -/
def well_formed (w : World) : Prop :=
  w.attack_key = attack_key_emerges w.v w.response_a w.response_b

/-- States from make_state are well-formed. -/
theorem make_state_well_formed (d_a d_b a_responds b_responds : Bool) :
    well_formed (make_state d_a d_b a_responds b_responds) := by
  simp only [well_formed, make_state]

/-- From attack key existence in well-formed world, both responses exist. -/
theorem attack_key_implies_both_responded (w : World) (h_wf : well_formed w) :
    attack_key_exists w → w.response_a.isSome ∧ w.response_b.isSome := by
  intro h
  simp only [attack_key_exists, well_formed] at h h_wf
  rw [h_wf] at h
  have h_tri := attack_requires_tripartite w.v w.response_a w.response_b h
  exact ⟨h_tri.2.1, h_tri.2.2⟩

/-! ## The Core Insight: Indistinguishable Worlds Have Same Attack Key Status

    If Alice observes the attack key, then in ALL worlds she can't distinguish
    (same local state), the attack key exists.

    Why? Because her local state INCLUDES has_attack_key.
-/

/-- Accessibility preserves attack key status for Alice. -/
theorem alice_accessible_preserves_attack_key (w w' : World) :
    alice_accessible w w' →
    (alice_local w).has_attack_key = (alice_local w').has_attack_key := by
  intro h
  simp [alice_accessible] at h
  rw [h]

/-- Accessibility preserves attack key status for Bob. -/
theorem bob_accessible_preserves_attack_key (w w' : World) :
    bob_accessible w w' →
    (bob_local w).has_attack_key = (bob_local w').has_attack_key := by
  intro h
  simp [bob_accessible] at h
  rw [h]

/-! ## Alice Knows Attack Key Exists

    If attack key exists at w, Alice knows it exists at w.
    Because: in all accessible worlds w', Alice's local state is the same,
    including has_attack_key = true.
-/

/-- If attack key exists, Alice knows it exists. -/
theorem alice_knows_attack_key (w : World) :
    attack_key_exists w → K_A attack_key_exists w := by
  intro h
  intro w' h_acc
  -- w' accessible means alice_local w = alice_local w'
  have h_same := alice_accessible_preserves_attack_key w w' h_acc
  -- Alice observes attack key at w
  have h_obs := alice_observes_attack_key w h
  -- So alice_local w'.has_attack_key = true
  simp only [alice_local] at h_same h_obs
  simp only [attack_key_exists]
  rw [← h_same, h_obs]

/-- If attack key exists, Bob knows it exists. -/
theorem bob_knows_attack_key (w : World) :
    attack_key_exists w → K_B attack_key_exists w := by
  intro h
  intro w' h_acc
  have h_same := bob_accessible_preserves_attack_key w w' h_acc
  have h_obs := bob_observes_attack_key w h
  simp only [bob_local] at h_same h_obs
  simp only [attack_key_exists]
  rw [← h_same, h_obs]

/-! ## Mutual Knowledge of Attack Key

    If attack key exists, both Alice and Bob know it.
-/

/-- If attack key exists, E(attack_key_exists) holds. -/
theorem mutual_knowledge_attack_key (w : World) :
    attack_key_exists w → E attack_key_exists w := by
  intro h
  constructor
  · exact alice_knows_attack_key w h
  · exact bob_knows_attack_key w h

/-! ## Higher-Order Knowledge

    The key insight: knowledge of attack key existence is ALSO locally observable.
    If Alice knows the attack key exists (K_A(E)), this is determined by her local state.
    So in any accessible world, she still knows it.
-/

/-- K_A preserves attack key knowledge across accessible worlds. -/
theorem alice_knows_preserves (w w' : World) :
    alice_accessible w w' →
    K_A attack_key_exists w → K_A attack_key_exists w' := by
  intro h_acc h_knows
  intro w'' h_acc'
  -- Transitivity: if w' acc from w, and w'' acc from w', then w'' acc from w
  have h_trans : alice_accessible w w'' := by
    simp only [alice_accessible] at *
    exact h_acc.trans h_acc'
  exact h_knows w'' h_trans

/-- Bob's knowledge preserves similarly. -/
theorem bob_knows_preserves (w w' : World) :
    bob_accessible w w' →
    K_B attack_key_exists w → K_B attack_key_exists w' := by
  intro h_acc h_knows
  intro w'' h_acc'
  have h_trans : bob_accessible w w'' := by
    simp only [bob_accessible] at *
    exact h_acc.trans h_acc'
  exact h_knows w'' h_trans

/-! ## Common Knowledge Theorem

    MAIN RESULT: If attack key exists, we have common knowledge of its existence.
-/

/-- Attack key existence implies K_depth n for all n. -/
theorem attack_key_implies_k_depth (w : World) (n : Nat) :
    attack_key_exists w → K_depth n attack_key_exists w := by
  intro h
  induction n generalizing w with
  | zero =>
    simp only [K_depth]
    exact h
  | succ k ih =>
    simp only [K_depth]
    constructor
    · exact ih w h
    · constructor
      · -- Alice knows K_depth k
        intro w' h_acc
        have h_same := alice_accessible_preserves_attack_key w w' h_acc
        have h_obs := alice_observes_attack_key w h
        simp only [alice_local] at h_same h_obs
        have h' : attack_key_exists w' := by
          simp only [attack_key_exists]
          rw [← h_same, h_obs]
        exact ih w' h'
      · -- Bob knows K_depth k
        intro w' h_acc
        have h_same := bob_accessible_preserves_attack_key w w' h_acc
        have h_obs := bob_observes_attack_key w h
        simp only [bob_local] at h_same h_obs
        have h' : attack_key_exists w' := by
          simp only [attack_key_exists]
          rw [← h_same, h_obs]
        exact ih w' h'

/-- MAIN THEOREM: Attack key existence implies common knowledge of attack key existence.

    CK("attack key exists") holds whenever the attack key exists.

    PROOF: The attack key is part of each party's local state.
    Accessibility preserves local state.
    Therefore, in any accessible world, the attack key status is preserved.
    This gives us knowledge at all depths → common knowledge.
-/
theorem attack_key_implies_common_knowledge (w : World) :
    attack_key_exists w → CK attack_key_exists w := by
  intro h
  intro n
  exact attack_key_implies_k_depth w n h

/-! ## The Non-Observable Proposition: Both Responded

    The key proposition we want common knowledge of is "both parties responded."
    This is NOT directly observable by either party:
    - Alice knows her own response status (in local state)
    - Alice does NOT directly observe Bob's response status
    - Alice CAN infer Bob responded from attack key existence + bilateral theorem

    This is what makes the epistemic result non-trivial.
-/

/-- Both parties responded. This is NOT directly in either party's local state. -/
def both_responded : WorldProp :=
  fun w => w.response_a.isSome ∧ w.response_b.isSome

/-! ## The Bilateral Construction Theorem (Proven, Not Axiom)

    In well-formed worlds, attack key existence implies both responded.
    This follows from Emergence.attack_requires_tripartite.
-/

/-- THE BILATERAL CONSTRUCTION THEOREM: In well-formed worlds,
    attack key existence implies both parties responded.

    This is proven from Emergence.attack_requires_tripartite, not assumed. -/
theorem bilateral_construction (w : World) (h_wf : well_formed w) :
    attack_key_exists w → both_responded w := by
  intro h_key
  simp only [attack_key_exists, well_formed, both_responded] at *
  rw [h_wf] at h_key
  have h_tri := attack_requires_tripartite w.v w.response_a w.response_b h_key
  exact ⟨h_tri.2.1, h_tri.2.2⟩

/-! ## Well-Formed Worlds as a Subtype

    Protocol-possible worlds are exactly the well-formed worlds.
    We define WFWorld as a subtype to eliminate "well_formed w →" plumbing.
-/

/-- Well-formed world: a world where attack_key is computed correctly.
    This is the domain of "protocol-possible" worlds. -/
def WFWorld := { w : World // well_formed w }

/-- Proposition over well-formed worlds. -/
abbrev WFWorldProp := WFWorld → Prop

/-- Lift a WorldProp to WFWorldProp. -/
def liftProp (P : WorldProp) : WFWorldProp := fun w => P w.val

/-- Alice's local state from a well-formed world. -/
def wf_alice_local (w : WFWorld) : AliceLocalState := alice_local w.val

/-- Bob's local state from a well-formed world. -/
def wf_bob_local (w : WFWorld) : BobLocalState := bob_local w.val

/-- Alice's accessibility on well-formed worlds. -/
def wf_alice_accessible (w w' : WFWorld) : Prop :=
  wf_alice_local w = wf_alice_local w'

/-- Bob's accessibility on well-formed worlds. -/
def wf_bob_accessible (w w' : WFWorld) : Prop :=
  wf_bob_local w = wf_bob_local w'

/-- Knowledge operator for Alice on well-formed worlds. -/
def WF_K_A (P : WFWorldProp) : WFWorldProp :=
  fun w => ∀ w', wf_alice_accessible w w' → P w'

/-- Knowledge operator for Bob on well-formed worlds. -/
def WF_K_B (P : WFWorldProp) : WFWorldProp :=
  fun w => ∀ w', wf_bob_accessible w w' → P w'

/-- Mutual knowledge on well-formed worlds. -/
def WF_E (P : WFWorldProp) : WFWorldProp :=
  fun w => WF_K_A P w ∧ WF_K_B P w

/-- Knowledge to depth n on well-formed worlds. -/
def WF_K_depth (n : Nat) (P : WFWorldProp) : WFWorldProp :=
  match n with
  | 0 => P
  | n + 1 => fun w => WF_K_depth n P w ∧ WF_E (WF_K_depth n P) w

/-- Common knowledge on well-formed worlds: P holds at all depths. -/
def WF_CK (P : WFWorldProp) : WFWorldProp :=
  fun w => ∀ n, WF_K_depth n P w

/-! ## Fixed-Point Characterization of Common Knowledge

    CK(P) is the greatest fixed point of: X ↦ P ∧ E(X)
    We prove: CK(P)(w) ↔ P(w) ∧ K_A(CK(P))(w) ∧ K_B(CK(P))(w)
-/

/-- CK implies P (depth 0). -/
theorem WF_CK_implies_P (P : WFWorldProp) (w : WFWorld) :
    WF_CK P w → P w := by
  intro h
  exact h 0

/-- CK implies K_A(CK(P)). -/
theorem WF_CK_implies_K_A_CK (P : WFWorldProp) (w : WFWorld) :
    WF_CK P w → WF_K_A (WF_CK P) w := by
  intro h_ck w' h_acc
  intro n
  -- CK at w means all depths at w
  -- Accessibility preserves local state, so K_depth propagates
  have h_succ := h_ck (n + 1)
  simp only [WF_K_depth] at h_succ
  exact h_succ.2.1 w' h_acc

/-- CK implies K_B(CK(P)). -/
theorem WF_CK_implies_K_B_CK (P : WFWorldProp) (w : WFWorld) :
    WF_CK P w → WF_K_B (WF_CK P) w := by
  intro h_ck w' h_acc
  intro n
  have h_succ := h_ck (n + 1)
  simp only [WF_K_depth] at h_succ
  exact h_succ.2.2 w' h_acc

/-- P ∧ E(CK(P)) implies CK(P). -/
theorem WF_P_and_E_CK_implies_CK (P : WFWorldProp) (w : WFWorld) :
    P w → WF_E (WF_CK P) w → WF_CK P w := by
  intro h_p h_e
  intro n
  induction n with
  | zero => exact h_p
  | succ k ih =>
    simp only [WF_K_depth]
    constructor
    · exact ih
    · constructor
      · intro w' h_acc
        exact h_e.1 w' h_acc k
      · intro w' h_acc
        exact h_e.2 w' h_acc k

/-- THE FIXED-POINT EQUATION: CK(P)(w) ↔ P(w) ∧ K_A(CK(P))(w) ∧ K_B(CK(P))(w)

    This shows CK(P) is a fixed point of the operator X ↦ P ∧ E(X). -/
theorem WF_CK_fixed_point (P : WFWorldProp) (w : WFWorld) :
    WF_CK P w ↔ (P w ∧ WF_K_A (WF_CK P) w ∧ WF_K_B (WF_CK P) w) := by
  constructor
  · intro h
    exact ⟨WF_CK_implies_P P w h,
           WF_CK_implies_K_A_CK P w h,
           WF_CK_implies_K_B_CK P w h⟩
  · intro ⟨h_p, h_ka, h_kb⟩
    exact WF_P_and_E_CK_implies_CK P w h_p ⟨h_ka, h_kb⟩

/-- THE GREATEST FIXED POINT PROPERTY (Knaster-Tarski):
    If X is a pre-fixed-point of F(X) = P ∧ E(X), then X ⊆ CK(P).

    ∀X, (∀w, X(w) → P(w) ∧ E(X)(w)) → (∀w, X(w) → CK(P)(w))

    This proves CK is the GREATEST fixed point, not just any fixed point. -/
theorem WF_CK_greatest (P X : WFWorldProp)
    (h_pre : ∀ w, X w → P w ∧ WF_E X w) :
    ∀ w, X w → WF_CK P w := by
  intro w h_x
  intro n
  induction n generalizing w with
  | zero =>
    simp only [WF_K_depth]
    exact (h_pre w h_x).1
  | succ k ih =>
    simp only [WF_K_depth]
    have ⟨h_p, h_e⟩ := h_pre w h_x
    constructor
    · exact ih w h_x
    · constructor
      · intro w' h_acc
        exact ih w' (h_e.1 w' h_acc)
      · intro w' h_acc
        exact ih w' (h_e.2 w' h_acc)

/-! ## Lifted Propositions on Well-Formed Worlds -/

/-- Attack key exists (lifted to WFWorld). -/
def wf_attack_key_exists : WFWorldProp := liftProp attack_key_exists

/-- Both responded (lifted to WFWorld). -/
def wf_both_responded : WFWorldProp := liftProp both_responded

/-! ## Common Knowledge of Both Responded

    THE KEY THEOREM: In well-formed worlds, attack key existence implies
    common knowledge of both_responded.

    This is non-trivial because:
    1. both_responded is NOT in Alice's local state (she doesn't see Bob's response)
    2. The proof USES the bilateral construction theorem
    3. The bilateral theorem bridges observable (attack_key) to non-observable (both_responded)
-/

/-- Accessibility preserves attack key status on WFWorld. -/
theorem wf_alice_accessible_preserves_attack_key (w w' : WFWorld) :
    wf_alice_accessible w w' → w.val.attack_key.isSome = w'.val.attack_key.isSome := by
  intro h
  simp only [wf_alice_accessible, wf_alice_local] at h
  have h_eq : alice_local w.val = alice_local w'.val := h
  have : (alice_local w.val).has_attack_key = (alice_local w'.val).has_attack_key := by
    rw [h_eq]
  simp only [alice_local] at this
  exact this

/-- Accessibility preserves attack key status on WFWorld (Bob). -/
theorem wf_bob_accessible_preserves_attack_key (w w' : WFWorld) :
    wf_bob_accessible w w' → w.val.attack_key.isSome = w'.val.attack_key.isSome := by
  intro h
  simp only [wf_bob_accessible, wf_bob_local] at h
  have h_eq : bob_local w.val = bob_local w'.val := h
  have : (bob_local w.val).has_attack_key = (bob_local w'.val).has_attack_key := by
    rw [h_eq]
  simp only [bob_local] at this
  exact this

/-- Alice knows both_responded when attack key exists. -/
theorem wf_alice_knows_both_responded (w : WFWorld) :
    wf_attack_key_exists w → WF_K_A wf_both_responded w := by
  intro h_key w' h_acc
  have h_same := wf_alice_accessible_preserves_attack_key w w' h_acc
  simp only [wf_attack_key_exists, liftProp, attack_key_exists] at h_key
  have h_key' : attack_key_exists w'.val := by
    simp only [attack_key_exists]
    rw [← h_same, h_key]
  simp only [wf_both_responded, liftProp]
  exact bilateral_construction w'.val w'.property h_key'

/-- Bob knows both_responded when attack key exists. -/
theorem wf_bob_knows_both_responded (w : WFWorld) :
    wf_attack_key_exists w → WF_K_B wf_both_responded w := by
  intro h_key w' h_acc
  have h_same := wf_bob_accessible_preserves_attack_key w w' h_acc
  simp only [wf_attack_key_exists, liftProp, attack_key_exists] at h_key
  have h_key' : attack_key_exists w'.val := by
    simp only [attack_key_exists]
    rw [← h_same, h_key]
  simp only [wf_both_responded, liftProp]
  exact bilateral_construction w'.val w'.property h_key'

/-- Mutual knowledge of both_responded. -/
theorem wf_mutual_knowledge_both_responded (w : WFWorld) :
    wf_attack_key_exists w → WF_E wf_both_responded w := by
  intro h_key
  exact ⟨wf_alice_knows_both_responded w h_key, wf_bob_knows_both_responded w h_key⟩

/-! ## MAIN RESULT: CK(both_responded)

    The crowning theorem: when attack key exists in a well-formed world,
    we have common knowledge of both_responded.

    This uses the bilateral construction theorem to bridge from
    the observable (attack_key_exists) to the non-observable (both_responded).
-/

/-- Attack key implies WF_K_depth n both_responded. -/
theorem wf_attack_key_implies_k_depth_both_responded (w : WFWorld) (n : Nat) :
    wf_attack_key_exists w → WF_K_depth n wf_both_responded w := by
  intro h_key
  induction n generalizing w with
  | zero =>
    simp only [WF_K_depth, wf_both_responded, liftProp]
    exact bilateral_construction w.val w.property (h_key)
  | succ k ih =>
    simp only [WF_K_depth]
    constructor
    · exact ih w h_key
    · constructor
      · -- Alice knows WF_K_depth k
        intro w' h_acc
        have h_same := wf_alice_accessible_preserves_attack_key w w' h_acc
        simp only [wf_attack_key_exists, liftProp, attack_key_exists] at h_key
        have h_key' : wf_attack_key_exists w' := by
          simp only [wf_attack_key_exists, liftProp, attack_key_exists]
          rw [← h_same, h_key]
        exact ih w' h_key'
      · -- Bob knows WF_K_depth k
        intro w' h_acc
        have h_same := wf_bob_accessible_preserves_attack_key w w' h_acc
        simp only [wf_attack_key_exists, liftProp, attack_key_exists] at h_key
        have h_key' : wf_attack_key_exists w' := by
          simp only [wf_attack_key_exists, liftProp, attack_key_exists]
          rw [← h_same, h_key]
        exact ih w' h_key'

/-- MAIN THEOREM: Attack key existence implies common knowledge of both_responded.

    This is the non-trivial epistemic result:
    - both_responded is NOT directly observable by either party
    - The bilateral construction theorem bridges observable to non-observable
    - No "well_formed w →" plumbing: WFWorld is the domain by construction -/
theorem wf_attack_key_implies_CK_both_responded (w : WFWorld) :
    wf_attack_key_exists w → WF_CK wf_both_responded w := by
  intro h_key n
  exact wf_attack_key_implies_k_depth_both_responded w n h_key

/-! ## States from make_state are Well-Formed Worlds -/

/-- Construct a WFWorld from make_state parameters. -/
def mkWFWorld (d_a d_b a_responds b_responds : Bool) : WFWorld :=
  ⟨make_state d_a d_b a_responds b_responds, make_state_well_formed d_a d_b a_responds b_responds⟩

/-- States constructed via make_state satisfy our epistemic properties. -/
theorem make_state_CK_both_responded (d_a d_b a_responds b_responds : Bool) :
    let w := mkWFWorld d_a d_b a_responds b_responds
    wf_attack_key_exists w → WF_CK wf_both_responded w :=
  wf_attack_key_implies_CK_both_responded (mkWFWorld d_a d_b a_responds b_responds)

/-! ## Summary

    This file establishes formal epistemic semantics for TGP:

    1. EPISTEMIC MODEL:
       - WFWorld: protocol-consistent worlds (satisfying the construction invariant)
       - States from make_state are well-formed (proven: make_state_well_formed)
       - Accessibility: equality of local state
       - Knowledge operators: WF_K_A, WF_K_B on WFWorld

    2. LOCAL STATE:
       - Alice observes: her D, received D_B, her response, attack key
       - Alice does NOT observe: Bob's response status
       - Symmetric for Bob

    3. BILATERAL CONSTRUCTION THEOREM (PROVEN):
       attack_key_exists → both_responded
       Derived from Emergence.attack_requires_tripartite

    4. COMMON KNOWLEDGE:
       - WF_CK defined as knowledge at all finite depths
       - FIXED-POINT EQUATION: CK(P) ↔ P ∧ K_A(CK(P)) ∧ K_B(CK(P))
       - GREATEST FIXED POINT: ∀X, (X → P ∧ E(X)) → (X → CK(P))

    5. MAIN THEOREM:
       wf_attack_key_exists w → WF_CK wf_both_responded w

    WHY THIS IS NON-TRIVIAL:
    - both_responded is NOT in either party's local state
    - Alice cannot directly see Bob's response status
    - The bilateral construction theorem is the ESSENTIAL BRIDGE
    - Knowledge of attack_key (observable) + bilateral theorem → knowledge of both_responded

    This answers Gray's objection: TGP achieves common knowledge of bilateral
    commitment because the emergent attack key, combined with the publicly-known
    bilateral construction theorem, allows each party to infer non-observable
    facts about the other's state.

    PROOF STATUS:
    - All theorems derived from Emergence.attack_requires_tripartite
    - Fixed-point equation and greatest fixed point property proven
    - No unproven assumptions in this file

    Q.E.D.
-/

#check bilateral_construction
#check WF_CK_fixed_point
#check WF_CK_greatest
#check wf_alice_knows_both_responded
#check wf_bob_knows_both_responded
#check wf_attack_key_implies_CK_both_responded
#check make_state_CK_both_responded

end Epistemic
