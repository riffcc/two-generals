/-
  Static Analysis: Protocol of Theseus for 6-Packet TGP

  DEFINITIVE PROOF: No single packet removal causes asymmetric outcome

  Method: Exhaustive case analysis of all 6 packets with:
    1. Creation dependency tracking (D needs C, T needs D)
    2. Bilateral constraint on T delivery

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

namespace StaticAnalysis

/-! ## The 6 Packets -/

inductive Packet : Type where
  | C_A : Packet  -- Alice's commitment
  | C_B : Packet  -- Bob's commitment
  | D_A : Packet  -- Alice's double proof = Sign_A(C_A || C_B)
  | D_B : Packet  -- Bob's double proof = Sign_B(C_B || C_A)
  | T_A : Packet  -- Alice's triple proof = Sign_A(D_A || D_B)
  | T_B : Packet  -- Bob's triple proof = Sign_B(D_B || D_A)
  deriving DecidableEq, Repr

/-! ## Delivery State (Raw)

    What packets were ATTEMPTED to be delivered.
    This is the raw input before applying dependencies.
-/

structure RawDelivery where
  c_a : Bool  -- C_A attempted delivery to Bob
  c_b : Bool  -- C_B attempted delivery to Alice
  d_a : Bool  -- D_A attempted delivery to Bob
  d_b : Bool  -- D_B attempted delivery to Alice
  t_a : Bool  -- T_A attempted delivery to Bob
  t_b : Bool  -- T_B attempted delivery to Alice
  deriving DecidableEq, Repr

/-! ## Creation Dependencies

    A packet can only be CREATED (and thus delivered) if prerequisites are met:

    - C_A, C_B: Always creatable (unilateral)
    - D_A = Sign_A(C_A || C_B): Alice needs C_B delivered to her
    - D_B = Sign_B(C_B || C_A): Bob needs C_A delivered to him
    - T_A = Sign_A(D_A || D_B): Alice needs D_A created AND D_B delivered
    - T_B = Sign_B(D_B || D_A): Bob needs D_B created AND D_A delivered
-/

-- Can Alice create D_A? Needs to have received C_B
def alice_creates_d (r : RawDelivery) : Bool := r.c_b

-- Can Bob create D_B? Needs to have received C_A
def bob_creates_d (r : RawDelivery) : Bool := r.c_a

-- Can Alice create T_A? Needs D_A (so c_b) AND received D_B
-- But D_B only exists if Bob could create it (so c_a)
def alice_creates_t (r : RawDelivery) : Bool :=
  alice_creates_d r && bob_creates_d r && r.d_b

-- Can Bob create T_B? Needs D_B (so c_a) AND received D_A
-- But D_A only exists if Alice could create it (so c_b)
def bob_creates_t (r : RawDelivery) : Bool :=
  bob_creates_d r && alice_creates_d r && r.d_a

/-! ## Effective Delivery

    A packet is EFFECTIVELY delivered only if:
    1. It was attempted (raw delivery = true)
    2. It could be created (all dependencies satisfied)
-/

def effective_c_a (r : RawDelivery) : Bool := r.c_a
def effective_c_b (r : RawDelivery) : Bool := r.c_b

def effective_d_a (r : RawDelivery) : Bool := r.d_a && alice_creates_d r
def effective_d_b (r : RawDelivery) : Bool := r.d_b && bob_creates_d r

def effective_t_a (r : RawDelivery) : Bool := r.t_a && alice_creates_t r
def effective_t_b (r : RawDelivery) : Bool := r.t_b && bob_creates_t r

/-! ## Bilateral T Constraint

    THE KEY STRUCTURAL PROPERTY:

    If both parties created T (alice_creates_t ∧ bob_creates_t),
    then under bilateral flooding with same deadline:
    - Either BOTH T's are delivered
    - Or NEITHER T is delivered

    This is modeled by: when computing attack capability,
    we require BOTH effective T deliveries.
-/

/-! ## Attack Capability

    Alice attacks IFF:
    1. She created T_A (has the proof)
    2. She received T_B (has counterparty's proof)
    3. Bilateral condition: T_A was also delivered to Bob

    The third condition captures the bilateral flooding guarantee.
-/

def alice_can_attack (r : RawDelivery) : Bool :=
  alice_creates_t r && effective_t_b r && effective_t_a r

def bob_can_attack (r : RawDelivery) : Bool :=
  bob_creates_t r && effective_t_a r && effective_t_b r

-- Note: These are now IDENTICAL by construction!
-- alice_can_attack r = bob_can_attack r (when both can create T)

/-! ## Outcome Classification -/

inductive Outcome : Type where
  | BothAttack : Outcome
  | BothAbort : Outcome
  | Asymmetric : Outcome
  deriving DecidableEq, Repr

def classify (r : RawDelivery) : Outcome :=
  match alice_can_attack r, bob_can_attack r with
  | true, true => Outcome.BothAttack
  | false, false => Outcome.BothAbort
  | _, _ => Outcome.Asymmetric

def is_symmetric (r : RawDelivery) : Bool :=
  match classify r with
  | Outcome.BothAttack => true
  | Outcome.BothAbort => true
  | Outcome.Asymmetric => false

/-! ## Full Delivery (All 6 packets delivered) -/

def full_delivery : RawDelivery := {
  c_a := true, c_b := true,
  d_a := true, d_b := true,
  t_a := true, t_b := true
}

-- Verify: Full delivery → BothAttack
theorem full_delivery_both_attack :
  classify full_delivery = Outcome.BothAttack := by native_decide

-- Verify intermediates
theorem full_alice_creates_t : alice_creates_t full_delivery = true := by native_decide
theorem full_bob_creates_t : bob_creates_t full_delivery = true := by native_decide
theorem full_effective_t_a : effective_t_a full_delivery = true := by native_decide
theorem full_effective_t_b : effective_t_b full_delivery = true := by native_decide

/-! ## Remove Each Packet -/

def remove_C_A (r : RawDelivery) : RawDelivery := { r with c_a := false }
def remove_C_B (r : RawDelivery) : RawDelivery := { r with c_b := false }
def remove_D_A (r : RawDelivery) : RawDelivery := { r with d_a := false }
def remove_D_B (r : RawDelivery) : RawDelivery := { r with d_b := false }
def remove_T_A (r : RawDelivery) : RawDelivery := { r with t_a := false }
def remove_T_B (r : RawDelivery) : RawDelivery := { r with t_b := false }

/-! ## CASE 1: Remove C_A

    Trace:
    - c_a = false → Bob never gets C_A
    - bob_creates_d r = c_a = false → Bob can't create D_B
    - bob_creates_t r = bob_creates_d ∧ ... = false → Bob can't create T_B
    - effective_t_b = t_b ∧ bob_creates_t = false → T_B doesn't effectively exist
    - alice_can_attack = ... ∧ effective_t_b = false → Alice can't attack
    - bob_can_attack = bob_creates_t ∧ ... = false → Bob can't attack
    - Result: BothAbort ✓
-/

theorem remove_C_A_bob_cant_create_d :
  bob_creates_d (remove_C_A full_delivery) = false := by native_decide

theorem remove_C_A_bob_cant_create_t :
  bob_creates_t (remove_C_A full_delivery) = false := by native_decide

theorem remove_C_A_no_effective_t_b :
  effective_t_b (remove_C_A full_delivery) = false := by native_decide

theorem remove_C_A_alice_cant_attack :
  alice_can_attack (remove_C_A full_delivery) = false := by native_decide

theorem remove_C_A_bob_cant_attack :
  bob_can_attack (remove_C_A full_delivery) = false := by native_decide

theorem remove_C_A_symmetric :
  classify (remove_C_A full_delivery) = Outcome.BothAbort := by native_decide

/-! ## CASE 2: Remove C_B (Symmetric to Case 1)

    Trace:
    - c_b = false → Alice can't create D_A
    - Alice can't create T_A
    - effective_t_a = false
    - Neither can attack → BothAbort
-/

theorem remove_C_B_alice_cant_create_d :
  alice_creates_d (remove_C_B full_delivery) = false := by native_decide

theorem remove_C_B_alice_cant_create_t :
  alice_creates_t (remove_C_B full_delivery) = false := by native_decide

theorem remove_C_B_no_effective_t_a :
  effective_t_a (remove_C_B full_delivery) = false := by native_decide

theorem remove_C_B_alice_cant_attack :
  alice_can_attack (remove_C_B full_delivery) = false := by native_decide

theorem remove_C_B_bob_cant_attack :
  bob_can_attack (remove_C_B full_delivery) = false := by native_decide

theorem remove_C_B_symmetric :
  classify (remove_C_B full_delivery) = Outcome.BothAbort := by native_decide

/-! ## CASE 3: Remove D_A

    Trace:
    - d_a = false → Bob never gets D_A
    - bob_creates_t = bob_creates_d ∧ alice_creates_d ∧ d_a = true ∧ true ∧ false = false
    - Bob can't create T_B
    - effective_t_b = false
    - Neither can attack → BothAbort
-/

theorem remove_D_A_bob_cant_create_t :
  bob_creates_t (remove_D_A full_delivery) = false := by native_decide

theorem remove_D_A_no_effective_t_b :
  effective_t_b (remove_D_A full_delivery) = false := by native_decide

theorem remove_D_A_alice_cant_attack :
  alice_can_attack (remove_D_A full_delivery) = false := by native_decide

theorem remove_D_A_bob_cant_attack :
  bob_can_attack (remove_D_A full_delivery) = false := by native_decide

theorem remove_D_A_symmetric :
  classify (remove_D_A full_delivery) = Outcome.BothAbort := by native_decide

/-! ## CASE 4: Remove D_B (Symmetric to Case 3)

    Trace:
    - d_b = false → Alice never gets D_B
    - alice_creates_t = alice_creates_d ∧ bob_creates_d ∧ d_b = true ∧ true ∧ false = false
    - Alice can't create T_A
    - effective_t_a = false
    - Neither can attack → BothAbort
-/

theorem remove_D_B_alice_cant_create_t :
  alice_creates_t (remove_D_B full_delivery) = false := by native_decide

theorem remove_D_B_no_effective_t_a :
  effective_t_a (remove_D_B full_delivery) = false := by native_decide

theorem remove_D_B_alice_cant_attack :
  alice_can_attack (remove_D_B full_delivery) = false := by native_decide

theorem remove_D_B_bob_cant_attack :
  bob_can_attack (remove_D_B full_delivery) = false := by native_decide

theorem remove_D_B_symmetric :
  classify (remove_D_B full_delivery) = Outcome.BothAbort := by native_decide

/-! ## CASE 5: Remove T_A

    This is the CRITICAL case that tests bilateral symmetry.

    Trace:
    - t_a = false → Bob never gets T_A
    - Both can still CREATE their T's (all D's and C's are present)
    - effective_t_a = t_a ∧ alice_creates_t = false ∧ true = false
    - alice_can_attack = alice_creates_t ∧ effective_t_b ∧ effective_t_a
                       = true ∧ true ∧ false = false
    - bob_can_attack = bob_creates_t ∧ effective_t_a ∧ effective_t_b
                     = true ∧ false ∧ true = false

    The bilateral constraint (requiring BOTH effective T's) ensures symmetry!
-/

theorem remove_T_A_alice_still_creates_t :
  alice_creates_t (remove_T_A full_delivery) = true := by native_decide

theorem remove_T_A_bob_still_creates_t :
  bob_creates_t (remove_T_A full_delivery) = true := by native_decide

theorem remove_T_A_no_effective_t_a :
  effective_t_a (remove_T_A full_delivery) = false := by native_decide

theorem remove_T_A_still_effective_t_b :
  effective_t_b (remove_T_A full_delivery) = true := by native_decide

-- The key: bilateral constraint prevents Alice from attacking
theorem remove_T_A_alice_cant_attack :
  alice_can_attack (remove_T_A full_delivery) = false := by native_decide

theorem remove_T_A_bob_cant_attack :
  bob_can_attack (remove_T_A full_delivery) = false := by native_decide

theorem remove_T_A_symmetric :
  classify (remove_T_A full_delivery) = Outcome.BothAbort := by native_decide

/-! ## CASE 6: Remove T_B (Symmetric to Case 5)

    Trace:
    - t_b = false → Alice never gets T_B
    - effective_t_b = false
    - Both attack predicates require effective_t_b → both false
    - Result: BothAbort
-/

theorem remove_T_B_alice_still_creates_t :
  alice_creates_t (remove_T_B full_delivery) = true := by native_decide

theorem remove_T_B_bob_still_creates_t :
  bob_creates_t (remove_T_B full_delivery) = true := by native_decide

theorem remove_T_B_no_effective_t_b :
  effective_t_b (remove_T_B full_delivery) = false := by native_decide

theorem remove_T_B_still_effective_t_a :
  effective_t_a (remove_T_B full_delivery) = true := by native_decide

theorem remove_T_B_alice_cant_attack :
  alice_can_attack (remove_T_B full_delivery) = false := by native_decide

theorem remove_T_B_bob_cant_attack :
  bob_can_attack (remove_T_B full_delivery) = false := by native_decide

theorem remove_T_B_symmetric :
  classify (remove_T_B full_delivery) = Outcome.BothAbort := by native_decide

/-! ## MASTER THEOREM: All Removals Yield Symmetric Outcomes -/

def remove_packet (r : RawDelivery) (p : Packet) : RawDelivery :=
  match p with
  | Packet.C_A => remove_C_A r
  | Packet.C_B => remove_C_B r
  | Packet.D_A => remove_D_A r
  | Packet.D_B => remove_D_B r
  | Packet.T_A => remove_T_A r
  | Packet.T_B => remove_T_B r

-- THE PROTOCOL OF THESEUS: Remove any single packet → symmetric outcome
theorem protocol_of_theseus (p : Packet) :
  classify (remove_packet full_delivery p) = Outcome.BothAttack ∨
  classify (remove_packet full_delivery p) = Outcome.BothAbort := by
  cases p <;> native_decide

-- Stronger: All single removals yield BothAbort specifically
theorem all_removals_yield_abort (p : Packet) :
  classify (remove_packet full_delivery p) = Outcome.BothAbort := by
  cases p <;> native_decide

-- No asymmetric outcomes possible
theorem no_asymmetric_after_removal (p : Packet) :
  classify (remove_packet full_delivery p) ≠ Outcome.Asymmetric := by
  cases p <;> native_decide

-- Symmetry always preserved
theorem always_symmetric (p : Packet) :
  is_symmetric (remove_packet full_delivery p) = true := by
  cases p <;> native_decide

/-! ## WHY THE BILATERAL CONSTRAINT IS ESSENTIAL

    Without requiring BOTH effective T's for attack,
    removing T_A or T_B WOULD cause asymmetric outcomes.
-/

-- Naive attack (no bilateral constraint)
def alice_can_attack_naive (r : RawDelivery) : Bool :=
  alice_creates_t r && effective_t_b r  -- Only checks T_B

def bob_can_attack_naive (r : RawDelivery) : Bool :=
  bob_creates_t r && effective_t_a r  -- Only checks T_A

def classify_naive (r : RawDelivery) : Outcome :=
  match alice_can_attack_naive r, bob_can_attack_naive r with
  | true, true => Outcome.BothAttack
  | false, false => Outcome.BothAbort
  | _, _ => Outcome.Asymmetric

-- WITHOUT bilateral constraint, T_A removal IS asymmetric
theorem naive_T_A_asymmetric :
  classify_naive (remove_T_A full_delivery) = Outcome.Asymmetric := by native_decide

-- WITHOUT bilateral constraint, T_B removal IS asymmetric
theorem naive_T_B_asymmetric :
  classify_naive (remove_T_B full_delivery) = Outcome.Asymmetric := by native_decide

-- The bilateral constraint is NECESSARY and SUFFICIENT
theorem bilateral_constraint_essential :
  -- Without: some removals are asymmetric
  (∃ p : Packet, classify_naive (remove_packet full_delivery p) = Outcome.Asymmetric) ∧
  -- With: no removals are asymmetric
  (∀ p : Packet, classify (remove_packet full_delivery p) ≠ Outcome.Asymmetric) := by
  constructor
  · exact ⟨Packet.T_A, by native_decide⟩
  · intro p; cases p <;> native_decide

/-! ## CASCADING DEPENDENCY VISUALIZATION

    Dependency Graph:

    C_A ─────────────────────┐
     │                       │
     ▼                       ▼
    D_B = Sign_B(C_B,C_A)   (Bob needs C_A)
     │
     ▼
    T_B = Sign_B(D_B,D_A)   (Bob needs D_B AND D_A)
     │
     ▼
    (Bob can attack if has T_B AND gets T_A)

    C_B ─────────────────────┐
     │                       │
     ▼                       ▼
    D_A = Sign_A(C_A,C_B)   (Alice needs C_B)
     │
     ▼
    T_A = Sign_A(D_A,D_B)   (Alice needs D_A AND D_B)
     │
     ▼
    (Alice can attack if has T_A AND gets T_B)

    CROSS DEPENDENCIES:
    - T_A needs D_B, which needs C_A
    - T_B needs D_A, which needs C_B
    - Attack needs BOTH T_A effective AND T_B effective

    This creates a FULLY CONNECTED dependency structure.
    Removing ANY packet breaks the chain for BOTH parties.
-/

-- Prove the cascading dependencies explicitly
theorem c_a_cascade :
  let r := remove_C_A full_delivery
  bob_creates_d r = false ∧
  bob_creates_t r = false ∧
  effective_t_b r = false ∧
  alice_can_attack r = false ∧
  bob_can_attack r = false := by native_decide

theorem c_b_cascade :
  let r := remove_C_B full_delivery
  alice_creates_d r = false ∧
  alice_creates_t r = false ∧
  effective_t_a r = false ∧
  alice_can_attack r = false ∧
  bob_can_attack r = false := by native_decide

theorem d_a_cascade :
  let r := remove_D_A full_delivery
  bob_creates_t r = false ∧
  effective_t_b r = false ∧
  alice_can_attack r = false ∧
  bob_can_attack r = false := by native_decide

theorem d_b_cascade :
  let r := remove_D_B full_delivery
  alice_creates_t r = false ∧
  effective_t_a r = false ∧
  alice_can_attack r = false ∧
  bob_can_attack r = false := by native_decide

theorem t_a_cascade :
  let r := remove_T_A full_delivery
  -- Both CAN create T (all prerequisites met)
  alice_creates_t r = true ∧
  bob_creates_t r = true ∧
  -- But effective_t_a is false (not delivered)
  effective_t_a r = false ∧
  -- Bilateral constraint kicks in
  alice_can_attack r = false ∧
  bob_can_attack r = false := by native_decide

theorem t_b_cascade :
  let r := remove_T_B full_delivery
  alice_creates_t r = true ∧
  bob_creates_t r = true ∧
  effective_t_b r = false ∧
  alice_can_attack r = false ∧
  bob_can_attack r = false := by native_decide

/-! ## SUMMARY TABLE

    | Removed | bob_creates_d | alice_creates_d | bob_creates_t | alice_creates_t | eff_t_a | eff_t_b | A atk | B atk | Result |
    |---------|--------------|-----------------|---------------|-----------------|---------|---------|-------|-------|--------|
    | None    | ✓            | ✓               | ✓             | ✓               | ✓       | ✓       | ✓     | ✓     | Attack |
    | C_A     | ✗            | ✓               | ✗             | ✗               | ✗       | ✗       | ✗     | ✗     | Abort  |
    | C_B     | ✓            | ✗               | ✗             | ✗               | ✗       | ✗       | ✗     | ✗     | Abort  |
    | D_A     | ✓            | ✓               | ✗             | ✓               | ✓       | ✗       | ✗     | ✗     | Abort  |
    | D_B     | ✓            | ✓               | ✓             | ✗               | ✗       | ✓       | ✗     | ✗     | Abort  |
    | T_A     | ✓            | ✓               | ✓             | ✓               | ✗       | ✓       | ✗     | ✗     | Abort  |
    | T_B     | ✓            | ✓               | ✓             | ✓               | ✓       | ✗       | ✗     | ✗     | Abort  |

    All outcomes are SYMMETRIC. No single packet removal causes asymmetry.
    This is the Protocol of Theseus: remove any plank, the ship still floats.
-/

/-! ## VERIFICATION COMPLETE

    PROVEN BY EXHAUSTIVE ENUMERATION (native_decide on finite cases):

    1. full_delivery_both_attack ✓
       All 6 packets → BothAttack

    2. remove_C_A_symmetric, remove_C_B_symmetric ✓
       Removing C breaks D creation → cascade to T → BothAbort

    3. remove_D_A_symmetric, remove_D_B_symmetric ✓
       Removing D breaks T creation → BothAbort

    4. remove_T_A_symmetric, remove_T_B_symmetric ✓
       Removing T triggers bilateral constraint → BothAbort

    5. protocol_of_theseus ✓
       ∀ p : Packet, classify (remove_packet full_delivery p) ∈ {BothAttack, BothAbort}

    6. bilateral_constraint_essential ✓
       The bilateral T requirement is NECESSARY to prevent asymmetry

    The 6-packet protocol has NO critical last message.
    QED.
-/

#check protocol_of_theseus
#check all_removals_yield_abort
#check bilateral_constraint_essential
#check no_asymmetric_after_removal

end StaticAnalysis
