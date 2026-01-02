/-
  Emergence.lean - The Emergent Attack (Protocol of Theseus, Part II)

  THEOREM: The attack is not a decision - it's an EMERGENT STATE.
           Neither party "attacks" - the attack EXISTS or it DOESN'T.

  This file extends the Protocol of Theseus with the Virtual Third construction:

    Forward pass:  A → B, B → A  (creates bilateral lock: D_A, D_B)
    V emerges:     The Virtual Third is born from the lock
    Reverse pass:  V challenges both, both must respond
    Attack emerges: IFF all three contribute (Alice, Bob, V)

  Key results:
    - modem_fire_symmetric: If either party can't respond, NO attack exists
    - no_asymmetric_outcomes: Asymmetric outcomes are impossible
    - attack_is_emergent: Attack ↔ (alice_responded ∧ bob_responded ∧ V_exists)

  The attack is the THIRD CAN OF PAINT.
  It doesn't exist until both colors mix.
  Neither party holds the result alone.

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

import Protocol

namespace Emergence

open Protocol

/-! ## The Virtual Third

    V is not a party. V is the RELATIONSHIP.
    V emerges from the bilateral lock (D_A ∧ D_B).
    V's existence proves the lock exists.
-/

/-- The Virtual Third: emerges from bilateral lock. -/
structure VirtualThird where
  /-- V's identity: born from hash(D_A || D_B) -/
  identity : Nat
  /-- V's challenge: what both must answer -/
  challenge : Nat
  deriving Repr, DecidableEq

/-- V can only emerge when BOTH D's exist. -/
def V_emerges (d_a_exists : Bool) (d_b_exists : Bool) : Option VirtualThird :=
  if d_a_exists ∧ d_b_exists then
    some { identity := 1, challenge := 2 }
  else
    none

/-- V emergence requires both D's. -/
theorem V_requires_bilateral (d_a d_b : Bool) :
    (V_emerges d_a d_b).isSome → d_a = true ∧ d_b = true := by
  intro h
  simp only [V_emerges] at h
  split at h
  · assumption
  · simp at h

/-! ## Responses to V (The Reverse Handshake)

    After V emerges, both parties must respond to V's challenge.
    Each response requires V AND the counterparty's D.
-/

/-- Alice's response to V's challenge. -/
structure AliceResponse where
  value : Nat
  deriving Repr, DecidableEq

/-- Bob's response to V's challenge. -/
structure BobResponse where
  value : Nat
  deriving Repr, DecidableEq

/-- Alice can only respond if she has V and Bob's D. -/
def alice_responds (v : Option VirtualThird) (has_bob_d : Bool) : Option AliceResponse :=
  match v with
  | none => none
  | some _ => if has_bob_d then some { value := 3 } else none

/-- Bob can only respond if he has V and Alice's D. -/
def bob_responds (v : Option VirtualThird) (has_alice_d : Bool) : Option BobResponse :=
  match v with
  | none => none
  | some _ => if has_alice_d then some { value := 4 } else none

/-- Alice's response requires V. -/
theorem alice_response_requires_V (v : Option VirtualThird) (has_bob_d : Bool) :
    (alice_responds v has_bob_d).isSome → v.isSome := by
  intro h; cases v with
  | none => simp [alice_responds] at h
  | some _ => simp

/-- Bob's response requires V. -/
theorem bob_response_requires_V (v : Option VirtualThird) (has_alice_d : Bool) :
    (bob_responds v has_alice_d).isSome → v.isSome := by
  intro h; cases v with
  | none => simp [bob_responds] at h
  | some _ => simp

/-! ## The Attack Key (Emergent, Not Decided)

    The attack key is not COMPUTED - it EMERGES.
    Requires: V + Alice's response + Bob's response.
    If ANY is missing, the key DOESN'T EXIST.
-/

/-- The attack key: tripartite construction. -/
structure AttackKey where
  value : Nat
  deriving Repr, DecidableEq

/-- The Tripartite Construction: all three parts that create the attack. -/
structure TripartiteConstruction where
  alice_part : AliceResponse
  bob_part : BobResponse
  V_part : VirtualThird
  deriving Repr

/-- Attack key emerges IFF all three components exist. -/
def attack_key_emerges
    (v : Option VirtualThird)
    (alice_resp : Option AliceResponse)
    (bob_resp : Option BobResponse) : Option AttackKey :=
  match v, alice_resp, bob_resp with
  | some _, some _, some _ => some { value := 5 }
  | _, _, _ => none

/-- Attack key requires ALL THREE components. -/
theorem attack_requires_tripartite
    (v : Option VirtualThird)
    (alice_resp : Option AliceResponse)
    (bob_resp : Option BobResponse) :
    (attack_key_emerges v alice_resp bob_resp).isSome →
    v.isSome ∧ alice_resp.isSome ∧ bob_resp.isSome := by
  intro h
  match v, alice_resp, bob_resp with
  | some _, some _, some _ => simp
  | none, _, _ => simp [attack_key_emerges] at h
  | _, none, _ => simp [attack_key_emerges] at h
  | _, _, none => simp [attack_key_emerges] at h

/-! ## Protocol Outcome -/

/-- Protocol outcome: Attack emerges or doesn't. -/
inductive EmergentOutcome : Type where
  | Attack : EmergentOutcome    -- Attack key exists - bilateral success
  | NoAttack : EmergentOutcome  -- Attack key doesn't exist - symmetric non-event
  deriving Repr, DecidableEq

/-- Outcome is determined by attack key existence. -/
def get_outcome (attack_key : Option AttackKey) : EmergentOutcome :=
  match attack_key with
  | some _ => EmergentOutcome.Attack
  | none => EmergentOutcome.NoAttack

/-! ## The Oscillation (Forward → V → Reverse)

    Terminology from the oscillation model:
    - Forward complete: both D's exist (bilateral lock)
    - V emerged: the virtual third is born
    - Reverse complete: both parties responded to V
-/

/-- Forward pass complete: bilateral lock established. -/
def forward_complete (d_a d_b : Bool) : Prop := d_a = true ∧ d_b = true

/-- V has emerged from the lock. -/
def V_emerged (v : Option VirtualThird) : Prop := v.isSome

/-- Reverse pass complete: both parties confirmed to V. -/
def reverse_complete (alice_resp : Option AliceResponse) (bob_resp : Option BobResponse) : Prop :=
  alice_resp.isSome ∧ bob_resp.isSome

/-! ## Complete Protocol State -/

/-- Full protocol state with Virtual Third. -/
structure EmergenceState where
  d_a_exists : Bool
  d_b_exists : Bool
  v : Option VirtualThird
  alice_response : Option AliceResponse
  bob_response : Option BobResponse
  attack_key : Option AttackKey
  deriving Repr

/-- Construct state from participation flags. -/
def make_state (d_a d_b : Bool) (alice_responds' bob_responds' : Bool) : EmergenceState :=
  let v := V_emerges d_a d_b
  let alice_resp := if alice_responds' then alice_responds v d_b else none
  let bob_resp := if bob_responds' then bob_responds v d_a else none
  let attack := attack_key_emerges v alice_resp bob_resp
  { d_a_exists := d_a, d_b_exists := d_b, v := v,
    alice_response := alice_resp, bob_response := bob_resp, attack_key := attack }

/-! ## MODEM FIRE THEOREMS

    The main result: if either party can't respond, the attack CANNOT exist.
-/

/-- If Bob doesn't respond, attack key doesn't exist. -/
theorem modem_fire_bob (d_a d_b : Bool) (alice_responds' : Bool) :
    (make_state d_a d_b alice_responds' false).attack_key = none := by
  simp only [make_state, attack_key_emerges]
  cases V_emerges d_a d_b <;> simp

/-- If Alice doesn't respond, attack key doesn't exist. -/
theorem modem_fire_alice (d_a d_b : Bool) (bob_responds' : Bool) :
    (make_state d_a d_b false bob_responds').attack_key = none := by
  simp only [make_state, attack_key_emerges]
  cases V_emerges d_a d_b <;> simp

/-- Modem fire (Bob) results in NoAttack. -/
theorem modem_fire_symmetric_bob (d_a d_b : Bool) (alice_responds' : Bool) :
    get_outcome (make_state d_a d_b alice_responds' false).attack_key = EmergentOutcome.NoAttack := by
  simp only [get_outcome, modem_fire_bob]

/-- Modem fire (Alice) results in NoAttack. -/
theorem modem_fire_symmetric_alice (d_a d_b : Bool) (bob_responds' : Bool) :
    get_outcome (make_state d_a d_b false bob_responds').attack_key = EmergentOutcome.NoAttack := by
  simp only [get_outcome, modem_fire_alice]

/-- Either modem fire means NoAttack. -/
theorem modem_fire_symmetric (d_a d_b : Bool) (alice_responds' bob_responds' : Bool) :
    alice_responds' = false ∨ bob_responds' = false →
    get_outcome (make_state d_a d_b alice_responds' bob_responds').attack_key = EmergentOutcome.NoAttack := by
  intro h
  cases h with
  | inl h_alice => simp only [h_alice, get_outcome, modem_fire_alice]
  | inr h_bob => simp only [h_bob, get_outcome, modem_fire_bob]

/-! ## BILATERAL REQUIREMENT THEOREMS -/

/-- Attack requires both parties to respond. -/
theorem attack_requires_bilateral (d_a d_b alice_responds' bob_responds' : Bool) :
    (make_state d_a d_b alice_responds' bob_responds').attack_key.isSome →
    alice_responds' = true ∧ bob_responds' = true := by
  intro h
  cases h_a : alice_responds' with
  | false =>
    simp only [make_state, attack_key_emerges, h_a] at h
    cases V_emerges d_a d_b <;> simp at h
  | true =>
    cases h_b : bob_responds' with
    | false =>
      simp only [make_state, attack_key_emerges, h_b] at h
      cases V_emerges d_a d_b <;> simp at h
    | true => exact ⟨rfl, rfl⟩

/-- Full bilateral requirement: Attack requires D_A, D_B, and both responses. -/
theorem attack_requires_full_oscillation (d_a d_b alice_responds' bob_responds' : Bool) :
    get_outcome (make_state d_a d_b alice_responds' bob_responds').attack_key = EmergentOutcome.Attack →
    d_a = true ∧ d_b = true ∧ alice_responds' = true ∧ bob_responds' = true := by
  intro h
  simp only [get_outcome] at h
  split at h
  · rename_i h_some
    have h_bilateral := attack_requires_bilateral d_a d_b alice_responds' bob_responds'
    have h_key_some : (make_state d_a d_b alice_responds' bob_responds').attack_key.isSome := by simp [h_some]
    have ⟨h_alice, h_bob⟩ := h_bilateral h_key_some
    simp only [make_state, attack_key_emerges] at h_some
    cases h_v : V_emerges d_a d_b with
    | none => simp [h_v] at h_some
    | some v =>
      have h_ds := V_requires_bilateral d_a d_b
      simp [h_v] at h_ds
      exact ⟨h_ds.1, h_ds.2, h_alice, h_bob⟩
  · simp at h

/-! ## NO ASYMMETRIC OUTCOMES

    Asymmetric outcomes are impossible because the attack key requires BOTH responses.
    This follows directly from modem_fire_bob and modem_fire_alice:
    - If Bob doesn't respond → no attack
    - If Alice doesn't respond → no attack
    - Therefore: attack → both responded
-/

/-- Asymmetric outcomes are impossible.

    If attack exists, both responses must exist.
    Follows directly from attack_requires_tripartite since
    attack_key = attack_key_emerges v alice_response bob_response.
-/
theorem no_asymmetric_outcomes (d_a d_b alice_responds' bob_responds' : Bool) :
    let s := make_state d_a d_b alice_responds' bob_responds'
    s.attack_key.isSome → (s.alice_response.isSome ∧ s.bob_response.isSome) := by
  -- Substitute the let binding
  simp only [make_state]
  intro h
  -- attack_key = attack_key_emerges v alice_resp bob_resp
  -- By attack_requires_tripartite, all three must be Some
  have h_tri := attack_requires_tripartite (V_emerges d_a d_b)
    (if alice_responds' then alice_responds (V_emerges d_a d_b) d_b else none)
    (if bob_responds' then bob_responds (V_emerges d_a d_b) d_a else none)
    h
  exact ⟨h_tri.2.1, h_tri.2.2⟩

/-! ## THE ATTACK IS NOT HELD BY ANY SINGLE PARTY

    Corollaries showing the attack belongs to no one alone.
-/

/-- The attack key is not Alice's alone. -/
theorem attack_not_alices (d_a d_b : Bool) :
    (make_state d_a d_b true false).attack_key = none := modem_fire_bob d_a d_b true

/-- The attack key is not Bob's alone. -/
theorem attack_not_bobs (d_a d_b : Bool) :
    (make_state d_a d_b false true).attack_key = none := modem_fire_alice d_a d_b true

/-- The attack key is not V's alone (requires responses). -/
theorem attack_not_V_alone (d_a d_b : Bool) :
    (make_state d_a d_b false false).attack_key = none := by
  simp only [make_state, attack_key_emerges]
  cases V_emerges d_a d_b <;> simp

/-! ## THE PROTOCOL OF THESEUS GUARANTEE

    The main theorem: Bilateral completion or symmetric non-attack.
-/

/-- The Protocol of Theseus Guarantee: Full oscillation or NoAttack. -/
theorem protocol_of_theseus_guarantee (d_a d_b alice_responds' bob_responds' : Bool) :
    let s := make_state d_a d_b alice_responds' bob_responds'
    let outcome := get_outcome s.attack_key
    -- Either full bilateral completion and Attack
    (d_a = true ∧ d_b = true ∧ alice_responds' = true ∧ bob_responds' = true ∧
     outcome = EmergentOutcome.Attack)
    ∨
    -- Or something missing and NoAttack
    (outcome = EmergentOutcome.NoAttack) := by
  by_cases h : get_outcome (make_state d_a d_b alice_responds' bob_responds').attack_key = EmergentOutcome.Attack
  · left
    have full := attack_requires_full_oscillation d_a d_b alice_responds' bob_responds' h
    exact ⟨full.1, full.2.1, full.2.2.1, full.2.2.2, h⟩
  · right
    cases h_out : get_outcome (make_state d_a d_b alice_responds' bob_responds').attack_key with
    | Attack => simp [h_out] at h
    | NoAttack => rfl

/-! ## EXPLICIT MODEM FIRE SCENARIOS -/

/-- Scenario: Bob's modem catches fire. Result: NoAttack (symmetric). -/
theorem bobs_modem_catches_fire (d_a d_b : Bool) :
    get_outcome (make_state d_a d_b true false).attack_key = EmergentOutcome.NoAttack :=
  modem_fire_symmetric_bob d_a d_b true

/-- Scenario: Alice's modem catches fire. Result: NoAttack (symmetric). -/
theorem alices_modem_catches_fire (d_a d_b : Bool) :
    get_outcome (make_state d_a d_b false true).attack_key = EmergentOutcome.NoAttack :=
  modem_fire_symmetric_alice d_a d_b true

/-- Scenario: Both modems catch fire. Result: NoAttack (symmetric). -/
theorem both_modems_catch_fire (d_a d_b : Bool) :
    get_outcome (make_state d_a d_b false false).attack_key = EmergentOutcome.NoAttack := by
  simp only [get_outcome, attack_not_V_alone]

/-! ## Summary

    This file proves the Emergent Attack construction:

    1. V emerges only when both D's exist (V_requires_bilateral)
    2. Attack requires all three: V, Alice's response, Bob's response (attack_requires_tripartite)
    3. Modem fire → no attack (modem_fire_*)
    4. Asymmetric outcomes are impossible (no_asymmetric_outcomes)
    5. Attack requires full oscillation (attack_requires_full_oscillation)
    6. The Protocol of Theseus Guarantee (protocol_of_theseus_guarantee)

    THE ATTACK IS THE THIRD CAN OF PAINT.
    It doesn't exist until both colors mix.
    Neither party holds the result alone.

    This extends the Protocol of Theseus: not only is there no critical packet,
    but the attack itself is an emergent property that requires live bilateral
    participation. Natural disasters (modem fire) result in symmetric non-attack.

    Q.E.D.
-/

#check V_requires_bilateral
#check attack_requires_tripartite
#check modem_fire_bob
#check modem_fire_alice
#check modem_fire_symmetric
#check no_asymmetric_outcomes
#check attack_requires_full_oscillation
#check protocol_of_theseus_guarantee
#check bobs_modem_catches_fire
#check alices_modem_catches_fire

end Emergence
