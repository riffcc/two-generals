/-
  Protocol.lean - Core 6-Packet Protocol Structure

  This file defines the fundamental types and structures for the
  Two Generals Protocol (TGP) with 6 packets.

  The 6-packet protocol:
    C_A, C_B  - Commitments (unilateral)
    D_A, D_B  - Double proofs (bilateral at C level)
    T_A, T_B  - Triple proofs (bilateral at D level) - THE KNOT

  Message structure (embeddings):
    C_X = Sign_X(commitment)
    D_X = Sign_X(C_X || C_Y)     -- embeds both commitments
    T_X = Sign_X(D_X || D_Y)     -- embeds both double proofs

  The key insight: T_B contains D_A, so T_B PROVES Bob had D_A.

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

namespace Protocol

/-! ## Core Types -/

/-- The two parties in the protocol. -/
inductive Party : Type where
  | Alice : Party
  | Bob : Party
  deriving DecidableEq, Repr

/-- Get the other party. -/
def Party.other : Party → Party
  | Party.Alice => Party.Bob
  | Party.Bob => Party.Alice

@[simp]
theorem Party.other_other (p : Party) : p.other.other = p := by
  cases p <;> rfl

@[simp]
theorem Party.other_ne (p : Party) : p.other ≠ p := by
  cases p <;> simp [Party.other]

/-- The possible decisions a party can make. -/
inductive Decision : Type where
  | Attack : Decision
  | Abort : Decision
  deriving DecidableEq, Repr

/-! ## Message Types -/

/-- The 6 message types in the protocol. -/
inductive MessageType : Type where
  | C : MessageType  -- Commitment
  | D : MessageType  -- Double proof
  | T : MessageType  -- Triple proof (the knot level)
  deriving DecidableEq, Repr

/-- A protocol message. -/
structure Message where
  sender : Party
  level : MessageType
  deriving DecidableEq, Repr

/-- The 6 specific messages. -/
def C_A : Message := ⟨Party.Alice, MessageType.C⟩
def C_B : Message := ⟨Party.Bob, MessageType.C⟩
def D_A : Message := ⟨Party.Alice, MessageType.D⟩
def D_B : Message := ⟨Party.Bob, MessageType.D⟩
def T_A : Message := ⟨Party.Alice, MessageType.T⟩
def T_B : Message := ⟨Party.Bob, MessageType.T⟩

/-! ## Message Embeddings

    The protocol's structural guarantee comes from message embeddings:

    D_X = Sign_X(C_X || C_Y)
    - D_A contains C_A and C_B
    - D_B contains C_B and C_A

    T_X = Sign_X(D_X || D_Y)
    - T_A contains D_A and D_B
    - T_B contains D_B and D_A

    Key insight: T_B contains D_A (embedded and signed by Bob).
    This means: If Alice has T_B, she has PROOF that Bob had D_A.
-/

/-- What is embedded in a message. -/
def embeds : Message → List Message
  | ⟨Party.Alice, MessageType.C⟩ => []
  | ⟨Party.Bob, MessageType.C⟩ => []
  | ⟨Party.Alice, MessageType.D⟩ => [C_A, C_B]
  | ⟨Party.Bob, MessageType.D⟩ => [C_B, C_A]
  | ⟨Party.Alice, MessageType.T⟩ => [D_A, D_B]
  | ⟨Party.Bob, MessageType.T⟩ => [D_B, D_A]

-- T_B embeds D_A
theorem t_b_embeds_d_a : D_A ∈ embeds T_B := by
  simp [embeds, T_B, D_A]

-- T_A embeds D_B
theorem t_a_embeds_d_b : D_B ∈ embeds T_A := by
  simp [embeds, T_A, D_B]

/-! ## Protocol State -/

/-- State of a single party. -/
structure PartyState where
  party : Party
  -- What I've created
  created_c : Bool      -- Created my commitment
  created_d : Bool      -- Created my double proof
  created_t : Bool      -- Created my triple proof
  -- What I've received from counterparty
  got_c : Bool          -- Received their commitment
  got_d : Bool          -- Received their double proof
  got_t : Bool          -- Received their triple proof
  -- My decision (if made)
  decision : Option Decision
  deriving Repr

/-- Initial state for a party (nothing created or received). -/
def PartyState.initial (p : Party) : PartyState := {
  party := p
  created_c := false
  created_d := false
  created_t := false
  got_c := false
  got_d := false
  got_t := false
  decision := none
}

/-- Full protocol state (both parties). -/
structure ProtocolState where
  alice : PartyState
  bob : PartyState
  time : Nat
  deriving Repr

/-- Initial protocol state. -/
def ProtocolState.initial : ProtocolState := {
  alice := PartyState.initial Party.Alice
  bob := PartyState.initial Party.Bob
  time := 0
}

/-! ## Raw Delivery State

    For exhaustive analysis, we track which messages were delivered
    independent of creation dependencies.
-/

/-- Raw delivery state (which messages were delivered). -/
structure RawDelivery where
  c_a : Bool  -- C_A delivered to Bob
  c_b : Bool  -- C_B delivered to Alice
  d_a : Bool  -- D_A delivered to Bob
  d_b : Bool  -- D_B delivered to Alice
  t_a : Bool  -- T_A delivered to Bob
  t_b : Bool  -- T_B delivered to Alice
  deriving DecidableEq, Repr

/-- All messages delivered. -/
def RawDelivery.full : RawDelivery := {
  c_a := true, c_b := true,
  d_a := true, d_b := true,
  t_a := true, t_b := true
}

/-- No messages delivered. -/
def RawDelivery.none : RawDelivery := {
  c_a := false, c_b := false,
  d_a := false, d_b := false,
  t_a := false, t_b := false
}

/-! ## Outcome Classification -/

/-- Possible coordination outcomes. -/
inductive Outcome : Type where
  | BothAttack : Outcome   -- Both parties attack (symmetric, success)
  | BothAbort : Outcome    -- Both parties abort (symmetric, safe)
  | Asymmetric : Outcome   -- One attacks, one aborts (FORBIDDEN)
  deriving DecidableEq, Repr

/-- Is the outcome symmetric? -/
def Outcome.is_symmetric : Outcome → Bool
  | Outcome.BothAttack => true
  | Outcome.BothAbort => true
  | Outcome.Asymmetric => false

/-! ## Summary

    This file defines the core protocol structure:
    - 2 parties (Alice, Bob)
    - 3 message levels (C, D, T)
    - 6 total messages
    - Message embeddings (T contains D contains C)
    - Protocol state tracking

    The key structural property is that T_B contains D_A.
    This is the foundation of proof stapling.

    Next: Dependencies.lean (creation rules)
-/

#check Party
#check Message
#check PartyState
#check ProtocolState
#check RawDelivery
#check Outcome

end Protocol
