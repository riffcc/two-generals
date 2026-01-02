/-
  Dependencies.lean - Creation Rules and Cascade Effects

  This file formalizes the dependency structure of the 6-packet protocol.

  Creation rules (what you need to create each message):
    C_X: Nothing (unilateral)
    D_X: Need counterparty's C (bilateral at C level)
    T_X: Need own D AND counterparty's D (bilateral at D level)

  Cascade effects:
    No C_A delivered → Bob can't create D_B → Bob can't create T_B
    No C_B delivered → Alice can't create D_A → Alice can't create T_A

  These dependencies are STRUCTURAL, not probabilistic.
  They follow from the definition of what each message IS.

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

import Protocol

namespace Dependencies

open Protocol

/-! ## Creation Predicates

    What does a party need to create each message type?
-/

/-- Can a party create their commitment? Always yes - this is unilateral. -/
def can_create_c : Bool := true

/-- Can this party create their double proof?
    Requires: received counterparty's commitment. -/
def can_create_d (s : PartyState) : Bool := s.got_c

/-- Can this party create their triple proof?
    Requires: created own D AND received counterparty's D. -/
def can_create_t (s : PartyState) : Bool := s.created_d ∧ s.got_d

/-! ## Creation Dependencies

    Theorems about what is required for each message type.
-/

/-- C creation is unilateral - no dependencies. -/
theorem c_is_unilateral : can_create_c = true := rfl

/-- D requires counterparty's C. -/
theorem d_needs_c (s : PartyState) : can_create_d s = true → s.got_c = true := by
  intro h
  exact h

/-- T requires own D (which requires counterparty's C). -/
theorem t_needs_own_d (s : PartyState) : can_create_t s = true → s.created_d = true := by
  intro h
  simp [can_create_t] at h
  exact h.1

/-- T requires counterparty's D. -/
theorem t_needs_their_d (s : PartyState) : can_create_t s = true → s.got_d = true := by
  intro h
  simp [can_create_t] at h
  exact h.2

/-! ## Cascade Effects

    If an early message doesn't arrive, later messages can't be created.
    These are the "cascade" dependencies.
-/

/-- State after processing deliveries according to raw delivery pattern. -/
def apply_delivery (r : RawDelivery) : ProtocolState :=
  let alice_state : PartyState := {
    party := Party.Alice
    created_c := true  -- Always create C
    created_d := r.c_b  -- Can create D iff got C_B
    created_t := r.c_b ∧ r.d_b  -- Can create T iff created D and got D_B
    got_c := r.c_b
    got_d := r.d_b
    got_t := r.t_b
    decision := none
  }
  let bob_state : PartyState := {
    party := Party.Bob
    created_c := true
    created_d := r.c_a
    created_t := r.c_a ∧ r.d_a
    got_c := r.c_a
    got_d := r.d_a
    got_t := r.t_a
    decision := none
  }
  { alice := alice_state, bob := bob_state, time := 0 }

/-- If C_A not delivered, Bob cannot create D_B. -/
theorem no_c_a_no_d_b (r : RawDelivery) (h : r.c_a = false) :
    (apply_delivery r).bob.created_d = false := by
  simp [apply_delivery, h]

/-- If C_B not delivered, Alice cannot create D_A. -/
theorem no_c_b_no_d_a (r : RawDelivery) (h : r.c_b = false) :
    (apply_delivery r).alice.created_d = false := by
  simp [apply_delivery, h]

/-- If D_A not delivered, Bob cannot create T_B. -/
theorem no_d_a_no_t_b (r : RawDelivery) (h : r.d_a = false) :
    (apply_delivery r).bob.created_t = false := by
  simp [apply_delivery]
  intro _
  exact h

/-- If D_B not delivered, Alice cannot create T_A. -/
theorem no_d_b_no_t_a (r : RawDelivery) (h : r.d_b = false) :
    (apply_delivery r).alice.created_t = false := by
  simp [apply_delivery]
  intro _
  exact h

/-! ## Full Cascade Theorems

    The complete cascade: no C → no D → no T
-/

/-- Full cascade: No C_A → No D_B → No T_B. -/
theorem cascade_c_a_to_t_b (r : RawDelivery) (h : r.c_a = false) :
    (apply_delivery r).bob.created_t = false := by
  simp [apply_delivery, h]

/-- Full cascade: No C_B → No D_A → No T_A. -/
theorem cascade_c_b_to_t_a (r : RawDelivery) (h : r.c_b = false) :
    (apply_delivery r).alice.created_t = false := by
  simp [apply_delivery, h]

/-! ## Bilateral Creation Property

    The key structural property: T creation is bilateral.
    You can't create T without counterparty's involvement.
-/

/-- T_A requires D_B, which requires C_A.
    So Alice's T requires Bob's D, which requires Alice's C reaching Bob. -/
theorem t_a_needs_bilateral (r : RawDelivery)
    (h : (apply_delivery r).alice.created_t = true) :
    r.c_b = true ∧ r.d_b = true := by
  simp [apply_delivery] at h
  exact h

/-- T_B requires D_A, which requires C_B.
    So Bob's T requires Alice's D, which requires Bob's C reaching Alice. -/
theorem t_b_needs_bilateral (r : RawDelivery)
    (h : (apply_delivery r).bob.created_t = true) :
    r.c_a = true ∧ r.d_a = true := by
  simp [apply_delivery] at h
  exact h

/-! ## Symmetric Dependencies

    The dependency structure is symmetric between Alice and Bob.
    What Alice needs from Bob = What Bob needs from Alice.
-/

/-- Swapping Alice/Bob roles in delivery yields symmetric creation. -/
def swap_delivery (r : RawDelivery) : RawDelivery := {
  c_a := r.c_b
  c_b := r.c_a
  d_a := r.d_b
  d_b := r.d_a
  t_a := r.t_b
  t_b := r.t_a
}

/-- Swap is an involution. -/
theorem swap_swap (r : RawDelivery) : swap_delivery (swap_delivery r) = r := by
  simp [swap_delivery]

/-- Alice's creation in r = Bob's creation in swapped r. -/
theorem symmetric_creation (r : RawDelivery) :
    (apply_delivery r).alice.created_t =
    (apply_delivery (swap_delivery r)).bob.created_t := by
  simp [apply_delivery, swap_delivery]

/-! ## Summary

    The dependency structure establishes:

    1. C is unilateral (no dependencies)
    2. D is bilateral at C level (needs counterparty's C)
    3. T is bilateral at D level (needs counterparty's D)

    The cascade effects show that blocking early messages
    prevents later messages from being created.

    This is STRUCTURAL, not based on timing or probability.
    It follows from the definition of what each message IS.

    Next: ProofStapling.lean (what messages PROVE)
-/

#check can_create_c
#check can_create_d
#check can_create_t
#check apply_delivery
#check cascade_c_a_to_t_b
#check t_a_needs_bilateral

end Dependencies
