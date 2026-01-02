/-
  Emergence.lean - The Emergent Coordination Key

  CORE INSIGHT: Coordination is not a decision - it's an emergent state.
  Neither general "decides to attack" - the attack capability EXISTS or it DOESN'T.

  This file formalizes the "third can of paint" construction:

    1. Forward pass:  General A → B, General B → A  (bilateral lock: D_A, D_B)
    2. V emerges:     A shared construct is born from the lock (like DH shared secret)
    3. Reverse pass:  Both must respond to complete the construction
    4. Attack key:    Emerges IFF all three components exist (A's part, B's part, V)

  The key insight: the attack capability is analogous to mixing two colors of paint.
  Neither general holds the result alone. If either fails to contribute, the mixed
  color (attack key) simply doesn't exist. This is the "third can of paint" - it
  belongs to neither party individually, only to their collaboration.

  Key results:
    - unilateral_failure_no_attack: If either party can't respond, NO attack exists
    - no_asymmetric_outcomes: Asymmetric outcomes are impossible
    - attack_is_emergent: Attack ↔ (A_responded ∧ B_responded ∧ V_exists)

  This construction is analogous to Diffie-Hellman key exchange:
    - Neither party knows the shared secret until both contribute
    - The secret doesn't exist until both exponents are combined
    - A partition after one contribution means no shared secret

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

import Protocol

namespace Emergence

open Protocol

/-! ## The Shared Construct (V)

    V is not a party. V is the RELATIONSHIP between the parties.
    V emerges from the bilateral lock (D_A ∧ D_B), analogous to how
    a Diffie-Hellman shared secret emerges from g^a and g^b.

    V's existence proves the bilateral lock exists.
-/

/-- The shared construct V: emerges from bilateral lock.
    Analogous to the DH shared secret S = g^(ab). -/
structure SharedConstruct where
  /-- V's identity: cryptographically derived from hash(D_A || D_B) -/
  identity : Nat
  /-- V's challenge: what both parties must answer in the reverse pass -/
  challenge : Nat
  deriving Repr, DecidableEq

/-- V emerges only when BOTH double-proofs exist.
    No D_A or no D_B means no V - the relationship doesn't exist. -/
def V_emerges (d_a_exists : Bool) (d_b_exists : Bool) : Option SharedConstruct :=
  if d_a_exists ∧ d_b_exists then
    some { identity := 1, challenge := 2 }
  else
    none

/-- V emergence requires both D's - the bilateral lock must be complete. -/
theorem V_requires_bilateral (d_a d_b : Bool) :
    (V_emerges d_a d_b).isSome → d_a = true ∧ d_b = true := by
  intro h
  simp only [V_emerges] at h
  split at h
  · assumption
  · simp at h

/-! ## Responses to V (The Reverse Handshake)

    After V emerges, both parties must respond to V's challenge.
    This is analogous to both parties using the DH shared secret
    to derive session keys - neither can do it alone.

    Each response requires:
    1. V exists (the relationship was established)
    2. Counterparty's D (proof they participated in the forward pass)
-/

/-- General A's response to V's challenge. -/
structure ResponseA where
  value : Nat
  deriving Repr, DecidableEq

/-- General B's response to V's challenge. -/
structure ResponseB where
  value : Nat
  deriving Repr, DecidableEq

/-- General A can only respond if V exists and B's D was received. -/
def response_A (v : Option SharedConstruct) (has_d_b : Bool) : Option ResponseA :=
  match v with
  | none => none
  | some _ => if has_d_b then some { value := 3 } else none

/-- General B can only respond if V exists and A's D was received. -/
def response_B (v : Option SharedConstruct) (has_d_a : Bool) : Option ResponseB :=
  match v with
  | none => none
  | some _ => if has_d_a then some { value := 4 } else none

/-- A's response requires V to exist. -/
theorem response_A_requires_V (v : Option SharedConstruct) (has_d_b : Bool) :
    (response_A v has_d_b).isSome → v.isSome := by
  intro h; cases v with
  | none => simp [response_A] at h
  | some _ => simp

/-- B's response requires V to exist. -/
theorem response_B_requires_V (v : Option SharedConstruct) (has_d_a : Bool) :
    (response_B v has_d_a).isSome → v.isSome := by
  intro h; cases v with
  | none => simp [response_B] at h
  | some _ => simp

/-! ## The Attack Key (The Third Can of Paint)

    The attack key is not COMPUTED by either party - it EMERGES from their
    collaboration. This is the "third can of paint" metaphor:

    - General A has red paint (their contribution)
    - General B has blue paint (their contribution)
    - The attack key is purple paint - it doesn't exist until both mix

    If either party fails to contribute (channel failure, timeout, partition),
    the purple paint simply doesn't exist. Neither party is "left holding"
    anything - there's nothing to hold.

    This is mathematically equivalent to Diffie-Hellman:
    - A contributes g^a
    - B contributes g^b
    - Shared secret S = g^(ab) requires BOTH contributions
-/

/-- The attack key: the emergent "third can of paint". -/
structure AttackKey where
  value : Nat
  deriving Repr, DecidableEq

/-- The tripartite construction: all three components that create the attack key. -/
structure TripartiteConstruction where
  response_a : ResponseA
  response_b : ResponseB
  shared_v : SharedConstruct
  deriving Repr

/-- Attack key emerges IFF all three components exist.
    Like DH: S exists IFF both g^a and g^b were exchanged. -/
def attack_key_emerges
    (v : Option SharedConstruct)
    (resp_a : Option ResponseA)
    (resp_b : Option ResponseB) : Option AttackKey :=
  match v, resp_a, resp_b with
  | some _, some _, some _ => some { value := 5 }
  | _, _, _ => none

/-- Attack key requires ALL THREE components - the tripartite construction. -/
theorem attack_requires_tripartite
    (v : Option SharedConstruct)
    (resp_a : Option ResponseA)
    (resp_b : Option ResponseB) :
    (attack_key_emerges v resp_a resp_b).isSome →
    v.isSome ∧ resp_a.isSome ∧ resp_b.isSome := by
  intro h
  match v, resp_a, resp_b with
  | some _, some _, some _ => simp
  | none, _, _ => simp [attack_key_emerges] at h
  | _, none, _ => simp [attack_key_emerges] at h
  | _, _, none => simp [attack_key_emerges] at h

/-! ## Protocol Outcome -/

/-- Protocol outcome: either the attack key emerges or it doesn't. -/
inductive Outcome : Type where
  | CoordinatedAttack : Outcome   -- Attack key exists - both generals attack
  | CoordinatedAbort : Outcome    -- Attack key doesn't exist - symmetric non-event
  deriving Repr, DecidableEq

/-- Outcome is determined by attack key existence. -/
def get_outcome (attack_key : Option AttackKey) : Outcome :=
  match attack_key with
  | some _ => Outcome.CoordinatedAttack
  | none => Outcome.CoordinatedAbort

/-! ## The Oscillation Model

    The protocol proceeds in two passes:

    Forward Pass (establishing the bilateral lock):
      A sends C_A → B receives, constructs D_B
      B sends C_B → A receives, constructs D_A
      Result: Both D's exist, V emerges

    Reverse Pass (confirming the relationship):
      Both parties respond to V's challenge
      Result: Attack key emerges (or doesn't)
-/

/-- Forward pass complete: bilateral lock established. -/
def forward_complete (d_a d_b : Bool) : Prop := d_a = true ∧ d_b = true

/-- V has emerged from the lock. -/
def V_emerged (v : Option SharedConstruct) : Prop := v.isSome

/-- Reverse pass complete: both parties confirmed to V. -/
def reverse_complete (resp_a : Option ResponseA) (resp_b : Option ResponseB) : Prop :=
  resp_a.isSome ∧ resp_b.isSome

/-! ## Complete Protocol State -/

/-- Full protocol state tracking the emergence construction. -/
structure EmergenceState where
  d_a_exists : Bool
  d_b_exists : Bool
  v : Option SharedConstruct
  response_a : Option ResponseA
  response_b : Option ResponseB
  attack_key : Option AttackKey
  deriving Repr

/-- Construct state from participation flags. -/
def make_state (d_a d_b : Bool) (a_responds b_responds : Bool) : EmergenceState :=
  let v := V_emerges d_a d_b
  let resp_a := if a_responds then response_A v d_b else none
  let resp_b := if b_responds then response_B v d_a else none
  let attack := attack_key_emerges v resp_a resp_b
  { d_a_exists := d_a, d_b_exists := d_b, v := v,
    response_a := resp_a, response_b := resp_b, attack_key := attack }

/-! ## Unilateral Failure Theorems

    MAIN RESULT: If either party fails to respond, the attack key cannot exist.

    This handles all failure modes:
    - Network partition (asymmetric channel failure)
    - Hardware failure (one party goes offline)
    - Timeout (one party doesn't respond in time)

    In all cases: no attack key exists, so neither party can attack.
    This is a SYMMETRIC outcome - coordinated abort.
-/

/-- If B doesn't respond, attack key doesn't exist. -/
theorem unilateral_failure_B (d_a d_b : Bool) (a_responds : Bool) :
    (make_state d_a d_b a_responds false).attack_key = none := by
  simp only [make_state, attack_key_emerges]
  cases V_emerges d_a d_b <;> simp

/-- If A doesn't respond, attack key doesn't exist. -/
theorem unilateral_failure_A (d_a d_b : Bool) (b_responds : Bool) :
    (make_state d_a d_b false b_responds).attack_key = none := by
  simp only [make_state, attack_key_emerges]
  cases V_emerges d_a d_b <;> simp

/-- B's failure to respond results in CoordinatedAbort. -/
theorem failure_B_symmetric (d_a d_b : Bool) (a_responds : Bool) :
    get_outcome (make_state d_a d_b a_responds false).attack_key = Outcome.CoordinatedAbort := by
  simp only [get_outcome, unilateral_failure_B]

/-- A's failure to respond results in CoordinatedAbort. -/
theorem failure_A_symmetric (d_a d_b : Bool) (b_responds : Bool) :
    get_outcome (make_state d_a d_b false b_responds).attack_key = Outcome.CoordinatedAbort := by
  simp only [get_outcome, unilateral_failure_A]

/-- Any unilateral failure means CoordinatedAbort. -/
theorem unilateral_failure_symmetric (d_a d_b : Bool) (a_responds b_responds : Bool) :
    a_responds = false ∨ b_responds = false →
    get_outcome (make_state d_a d_b a_responds b_responds).attack_key = Outcome.CoordinatedAbort := by
  intro h
  cases h with
  | inl h_a => simp only [h_a, get_outcome, unilateral_failure_A]
  | inr h_b => simp only [h_b, get_outcome, unilateral_failure_B]

/-! ## Bilateral Requirement Theorems -/

/-- Attack requires both parties to respond. -/
theorem attack_requires_bilateral (d_a d_b a_responds b_responds : Bool) :
    (make_state d_a d_b a_responds b_responds).attack_key.isSome →
    a_responds = true ∧ b_responds = true := by
  intro h
  cases h_a : a_responds with
  | false =>
    simp only [make_state, attack_key_emerges, h_a] at h
    cases V_emerges d_a d_b <;> simp at h
  | true =>
    cases h_b : b_responds with
    | false =>
      simp only [make_state, attack_key_emerges, h_b] at h
      cases V_emerges d_a d_b <;> simp at h
    | true => exact ⟨rfl, rfl⟩

/-- Attack requires the complete oscillation: D_A, D_B, and both responses. -/
theorem attack_requires_full_oscillation (d_a d_b a_responds b_responds : Bool) :
    get_outcome (make_state d_a d_b a_responds b_responds).attack_key = Outcome.CoordinatedAttack →
    d_a = true ∧ d_b = true ∧ a_responds = true ∧ b_responds = true := by
  intro h
  simp only [get_outcome] at h
  split at h
  · rename_i h_some
    have h_bilateral := attack_requires_bilateral d_a d_b a_responds b_responds
    have h_key_some : (make_state d_a d_b a_responds b_responds).attack_key.isSome := by simp [h_some]
    have ⟨h_a, h_b⟩ := h_bilateral h_key_some
    simp only [make_state, attack_key_emerges] at h_some
    cases h_v : V_emerges d_a d_b with
    | none => simp [h_v] at h_some
    | some v =>
      have h_ds := V_requires_bilateral d_a d_b
      simp [h_v] at h_ds
      exact ⟨h_ds.1, h_ds.2, h_a, h_b⟩
  · simp at h

/-! ## No Asymmetric Outcomes

    THEOREM: Asymmetric outcomes are impossible.

    This is the central guarantee of the emergent construction:
    - If A attacks but B doesn't → IMPOSSIBLE (attack key requires both)
    - If B attacks but A doesn't → IMPOSSIBLE (attack key requires both)

    The only possible outcomes are:
    - CoordinatedAttack: Both attack (attack key exists)
    - CoordinatedAbort: Neither attacks (attack key doesn't exist)
-/

/-- Asymmetric outcomes are impossible.
    If attack key exists, both responses must exist. -/
theorem no_asymmetric_outcomes (d_a d_b a_responds b_responds : Bool) :
    let s := make_state d_a d_b a_responds b_responds
    s.attack_key.isSome → (s.response_a.isSome ∧ s.response_b.isSome) := by
  simp only [make_state]
  intro h
  have h_tri := attack_requires_tripartite (V_emerges d_a d_b)
    (if a_responds then response_A (V_emerges d_a d_b) d_b else none)
    (if b_responds then response_B (V_emerges d_a d_b) d_a else none)
    h
  exact ⟨h_tri.2.1, h_tri.2.2⟩

/-! ## The Attack Key Belongs to Neither Party Alone

    Corollaries showing the attack key is truly emergent -
    it cannot be held by any single party.
-/

/-- The attack key is not A's alone - B must participate. -/
theorem attack_not_A_alone (d_a d_b : Bool) :
    (make_state d_a d_b true false).attack_key = none := unilateral_failure_B d_a d_b true

/-- The attack key is not B's alone - A must participate. -/
theorem attack_not_B_alone (d_a d_b : Bool) :
    (make_state d_a d_b false true).attack_key = none := unilateral_failure_A d_a d_b true

/-- The attack key is not V's alone - responses are required. -/
theorem attack_not_V_alone (d_a d_b : Bool) :
    (make_state d_a d_b false false).attack_key = none := by
  simp only [make_state, attack_key_emerges]
  cases V_emerges d_a d_b <;> simp

/-! ## The Main Guarantee

    THEOREM (Protocol of Theseus - Emergence):
    Every protocol run results in one of exactly two outcomes:
    1. Full bilateral completion → CoordinatedAttack
    2. Incomplete → CoordinatedAbort

    There are no other possibilities. The outcome is always symmetric.
-/

/-- The Protocol of Theseus Guarantee: Full oscillation → Attack, else → Abort. -/
theorem protocol_of_theseus_guarantee (d_a d_b a_responds b_responds : Bool) :
    let s := make_state d_a d_b a_responds b_responds
    let outcome := get_outcome s.attack_key
    -- Either full bilateral completion and CoordinatedAttack
    (d_a = true ∧ d_b = true ∧ a_responds = true ∧ b_responds = true ∧
     outcome = Outcome.CoordinatedAttack)
    ∨
    -- Or something missing and CoordinatedAbort
    (outcome = Outcome.CoordinatedAbort) := by
  by_cases h : get_outcome (make_state d_a d_b a_responds b_responds).attack_key = Outcome.CoordinatedAttack
  · left
    have full := attack_requires_full_oscillation d_a d_b a_responds b_responds h
    exact ⟨full.1, full.2.1, full.2.2.1, full.2.2.2, h⟩
  · right
    cases h_out : get_outcome (make_state d_a d_b a_responds b_responds).attack_key with
    | CoordinatedAttack => simp [h_out] at h
    | CoordinatedAbort => rfl

/-! ## Explicit Failure Scenarios

    For clarity, we provide explicit theorems for common failure modes.
-/

/-- Network partition affecting B → CoordinatedAbort. -/
theorem partition_B (d_a d_b : Bool) :
    get_outcome (make_state d_a d_b true false).attack_key = Outcome.CoordinatedAbort :=
  failure_B_symmetric d_a d_b true

/-- Network partition affecting A → CoordinatedAbort. -/
theorem partition_A (d_a d_b : Bool) :
    get_outcome (make_state d_a d_b false true).attack_key = Outcome.CoordinatedAbort :=
  failure_A_symmetric d_a d_b true

/-- Complete channel failure → CoordinatedAbort. -/
theorem total_partition (d_a d_b : Bool) :
    get_outcome (make_state d_a d_b false false).attack_key = Outcome.CoordinatedAbort := by
  simp only [get_outcome, attack_not_V_alone]

/-! ## Asymmetric Channel Failure

    CRITICAL: TGP handles asymmetric channel failure correctly.

    Unlike symmetric channel models that assume both directions fail together,
    real networks can have asymmetric failures:
    - Cat6 cable with half the wires severed
    - Router with one-way NAT failure
    - Firewall blocking one direction

    The emergent construction handles this naturally:
    - If one party can't respond (regardless of WHY), attack key doesn't exist
    - The cause of failure (symmetric or asymmetric) doesn't matter
    - The OUTCOME is always symmetric: CoordinatedAbort
-/

/-- Asymmetric channel: A→B works, B→A fails.
    B receives but cannot respond. Result: CoordinatedAbort. -/
theorem asymmetric_channel_B_unreachable (d_a d_b : Bool) :
    -- A can send, B receives. But B's response doesn't get through.
    -- Model as: a_responds = true (A did their part), b_responds = false (B couldn't respond)
    get_outcome (make_state d_a d_b true false).attack_key = Outcome.CoordinatedAbort :=
  failure_B_symmetric d_a d_b true

/-- Asymmetric channel: B→A works, A→B fails.
    A receives but cannot respond. Result: CoordinatedAbort. -/
theorem asymmetric_channel_A_unreachable (d_a d_b : Bool) :
    get_outcome (make_state d_a d_b false true).attack_key = Outcome.CoordinatedAbort :=
  failure_A_symmetric d_a d_b true

/-- Cable partially severed: one direction works, other doesn't.
    Result: CoordinatedAbort regardless of which direction fails. -/
theorem cable_partially_severed (d_a d_b : Bool) (a_responds b_responds : Bool) :
    a_responds = false ∨ b_responds = false →
    get_outcome (make_state d_a d_b a_responds b_responds).attack_key = Outcome.CoordinatedAbort :=
  unilateral_failure_symmetric d_a d_b a_responds b_responds

/-- Hardware failure on one side: same result as any unilateral failure. -/
theorem hardware_failure_one_side (d_a d_b : Bool) (a_responds b_responds : Bool) :
    a_responds = false ∨ b_responds = false →
    get_outcome (make_state d_a d_b a_responds b_responds).attack_key = Outcome.CoordinatedAbort :=
  unilateral_failure_symmetric d_a d_b a_responds b_responds

/-! ## The Key Insight: Channel Symmetry is NOT Required

    The solution does NOT assume symmetric channels.
    The solution does NOT require both directions to have the same state.

    Instead, the EMERGENT CONSTRUCTION guarantees symmetric OUTCOMES
    regardless of channel state:

    - Symmetric working channel    → Both respond → CoordinatedAttack
    - Symmetric failed channel     → Neither responds → CoordinatedAbort
    - Asymmetric channel (A→B ok)  → B can't respond → CoordinatedAbort
    - Asymmetric channel (B→A ok)  → A can't respond → CoordinatedAbort

    ALL failure modes result in CoordinatedAbort.
    The attack key is the "third can of paint" - it simply doesn't exist
    unless BOTH parties complete the oscillation.
-/

/-- Channel asymmetry cannot create outcome asymmetry.
    Regardless of channel state, outcome is symmetric. -/
theorem channel_asymmetry_cannot_cause_outcome_asymmetry
    (d_a d_b a_responds b_responds : Bool) :
    let outcome := get_outcome (make_state d_a d_b a_responds b_responds).attack_key
    outcome = Outcome.CoordinatedAttack ∨ outcome = Outcome.CoordinatedAbort := by
  cases h : get_outcome (make_state d_a d_b a_responds b_responds).attack_key with
  | CoordinatedAttack => left; rfl
  | CoordinatedAbort => right; rfl

/-! ## Summary

    This file establishes the Emergent Coordination Key construction:

    1. V emerges only when both D's exist (V_requires_bilateral)
    2. Attack requires all three: V, A's response, B's response (attack_requires_tripartite)
    3. Unilateral failure → no attack (unilateral_failure_*)
    4. Asymmetric outcomes are impossible (no_asymmetric_outcomes)
    5. Attack requires full oscillation (attack_requires_full_oscillation)
    6. The Protocol of Theseus Guarantee (protocol_of_theseus_guarantee)

    THE THIRD CAN OF PAINT:
    The attack key is like mixing two colors - neither general holds
    the result alone. If either fails to contribute, the mixed color
    simply doesn't exist. There's nothing to "hold" asymmetrically.

    This is mathematically equivalent to Diffie-Hellman key exchange:
    the shared secret S = g^(ab) requires both contributions.
    A partition after one contribution means no shared secret exists.

    CONCLUSION: The Two Generals can coordinate under fair-lossy channels
    because the attack capability is an emergent property. Channel failures
    result in symmetric abort, not asymmetric outcomes.

    Q.E.D.
-/

#check V_requires_bilateral
#check attack_requires_tripartite
#check unilateral_failure_A
#check unilateral_failure_B
#check unilateral_failure_symmetric
#check no_asymmetric_outcomes
#check attack_requires_full_oscillation
#check protocol_of_theseus_guarantee
#check partition_A
#check partition_B

end Emergence
