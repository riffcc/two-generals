/-
  GrayInterp.lean - Bridge from Channel/Emergence to GrayCore

  This file interprets the Channel/Emergence execution model into
  GrayCore.Execution, proving the four correctness properties:

  1. AgreementOn       - Both decide the same
  2. TotalTerminationOn - Both always decide
  3. AbortOnNoChannelOn - NoChannel → Abort
  4. AttackOnLiveOn    - LiveByDeadline → Attack

  Author: Wings@riff.cc (Riff Labs)
  Date: January 2026
-/

import GrayCore
import Channel
import Emergence
import LocalDetect

namespace GrayInterp

open GrayCore
open Channel
open Protocol

/-! ## Message Type -/

/-- Combined message type: direction + protocol message type. -/
abbrev GMsg := Channel.Direction × Protocol.MessageType

instance : DecidableEq GMsg := inferInstance

/-! ## Protocol Specification

  P_TGP uses PartyState as State, with decision read from the decision field.
  This ensures t=0 (initial) has no decision, and t=1 (final) has a decision.
-/

/-- Map Protocol.Decision to GrayCore.Decision. -/
def protoDecisionToGray : Protocol.Decision → GrayCore.Decision
  | Protocol.Decision.Attack => GrayCore.Decision.Attack
  | Protocol.Decision.Abort => GrayCore.Decision.Abort

/-- The TGP protocol specification using per-party state. -/
def P_TGP : GrayCore.ProtocolSpec where
  State := Protocol.PartyState
  init := (Channel.initial_execution).alice
  decided := fun ps =>
    match ps.decision with
    | some d => some (protoDecisionToGray d)
    | none => none

/-! ## Semantics-Derived Decision

  The attack/abort decision is computed from ExecutionState via:
  1. Channel.to_emergence_model: ExecutionState → (d_a, d_b, a_responds, b_responds)
  2. Emergence.make_state: booleans → EmergenceState (with attack_key)
  3. attack_key.isSome determines Attack vs Abort
-/

/-- Global "attack happened" bit, computed from the derived emergence model. -/
def attacks_global (es : Channel.ExecutionState) : Bool :=
  let (d_a, d_b, a_responds, b_responds) := Channel.to_emergence_model es
  (Emergence.make_state d_a d_b a_responds b_responds).attack_key.isSome

/-- Derive protocol decision from ExecutionState via emergence model. -/
def decision_from_execState (es : Channel.ExecutionState) : Protocol.Decision :=
  if attacks_global es then Protocol.Decision.Attack else Protocol.Decision.Abort

/-- Hinge lemma: Alice's local attack predicate matches the global emergent bit. -/
theorem alice_local_iff_attacks_global (es : Channel.ExecutionState) :
    (let (d_a, d_b, a_responds, b_responds) := Channel.to_emergence_model es
     LocalDetect.alice_attacks_local (LocalDetect.alice_true_view d_a d_b a_responds b_responds))
    ↔ attacks_global es := by
  rcases h : Channel.to_emergence_model es with ⟨d_a, d_b, a_responds, b_responds⟩
  simpa [attacks_global, h] using
    (LocalDetect.local_matches_global d_a d_b a_responds b_responds)

/-- Hinge lemma: Bob's local attack predicate matches the global emergent bit. -/
theorem bob_local_iff_attacks_global (es : Channel.ExecutionState) :
    (let (d_a, d_b, a_responds, b_responds) := Channel.to_emergence_model es
     LocalDetect.bob_attacks_local (LocalDetect.bob_true_view d_a d_b a_responds b_responds))
    ↔ attacks_global es := by
  rcases h : Channel.to_emergence_model es with ⟨d_a, d_b, a_responds, b_responds⟩
  have hAlice := LocalDetect.local_matches_global d_a d_b a_responds b_responds
  have hAgree := LocalDetect.local_views_agree d_a d_b a_responds b_responds
  simp only [attacks_global, h]
  rw [← hAgree]
  exact hAlice

/-! ## Channel Model -/

/-- Reuse Channel's BidirectionalChannel type. -/
abbrev BidirectionalChannel := Channel.BidirectionalChannel

/-- Both directions working. -/
def both_working (ch : BidirectionalChannel) : Bool :=
  ch.alice_to_bob == Channel.ChannelState.Working &&
  ch.bob_to_alice == Channel.ChannelState.Working

/-- Both directions partitioned (no channel). -/
def both_partitioned (ch : BidirectionalChannel) : Bool :=
  ch.alice_to_bob == Channel.ChannelState.Partitioned &&
  ch.bob_to_alice == Channel.ChannelState.Partitioned

/-! ## ExecutionState from BidirectionalChannel

  Construct the execution state that results from running TGP over a channel.
  The key semantic property: both_working ↔ full oscillation ↔ attacks_global.
-/

/-- Construct an ExecutionState from a BidirectionalChannel.
    If both directions work, we get full oscillation. Otherwise, oscillation is incomplete. -/
def execState_of (ch : BidirectionalChannel) : Channel.ExecutionState :=
  let w := both_working ch
  { alice := { party := Protocol.Party.Alice
               created_c := true, created_d := w, created_t := w
               got_c := w, got_d := w, got_t := w
               decision := none }
    bob := { party := Protocol.Party.Bob
             created_c := true, created_d := w, created_t := w
             got_c := w, got_d := w, got_t := w
             decision := none }
    alice_received_c := w
    alice_received_d := w
    alice_received_t := w
    bob_received_c := w
    bob_received_d := w
    bob_received_t := w }

/-- Semantic bridge: attacks_global agrees with both_working. -/
theorem attacks_global_iff_both_working (ch : BidirectionalChannel) :
    attacks_global (execState_of ch) = both_working ch := by
  unfold attacks_global execState_of Channel.to_emergence_model
  cases hw : both_working ch <;> native_decide

/-- decision_from_execState agrees with both_working on Attack/Abort. -/
theorem decision_from_execState_eq (ch : BidirectionalChannel) :
    decision_from_execState (execState_of ch) =
      if both_working ch then Protocol.Decision.Attack else Protocol.Decision.Abort := by
  simp only [decision_from_execState, attacks_global_iff_both_working]

/-! ## Critical Messages -/

/-- The 6 critical messages for the oscillation. -/
def criticalMsgs : List GMsg :=
  [ (Channel.Direction.AliceToBob, Protocol.MessageType.C)
  , (Channel.Direction.AliceToBob, Protocol.MessageType.D)
  , (Channel.Direction.AliceToBob, Protocol.MessageType.T)
  , (Channel.Direction.BobToAlice, Protocol.MessageType.C)
  , (Channel.Direction.BobToAlice, Protocol.MessageType.D)
  , (Channel.Direction.BobToAlice, Protocol.MessageType.T)
  ]

/-- Multiset of all critical messages. -/
def criticalMS : Multiset GMsg := Multiset.ofList criticalMsgs

/-- Is a direction working? -/
def dirWorking (ch : BidirectionalChannel) : Channel.Direction → Bool
  | Channel.Direction.AliceToBob => ch.alice_to_bob == Channel.ChannelState.Working
  | Channel.Direction.BobToAlice => ch.bob_to_alice == Channel.ChannelState.Working

/-- Messages delivered based on which directions are working. -/
def deliveredMS (ch : BidirectionalChannel) : Multiset GMsg :=
  criticalMS.filter fun m => dirWorking ch m.1

/-! ## Initial and Final States -/

/-- Initial party state for Alice: derived from Channel.initial_execution. -/
def initialAlice : Protocol.PartyState := Channel.initial_execution.alice

/-- Initial party state for Bob: derived from Channel.initial_execution. -/
def initialBob : Protocol.PartyState := Channel.initial_execution.bob

/-- Final party state for Alice, derived from `execState_of` and `decision_from_execState`. -/
def finalAlice (ch : BidirectionalChannel) : Protocol.PartyState :=
  let es := execState_of ch
  { party := es.alice.party
    created_c := es.alice.created_c
    created_d := es.alice.created_d
    created_t := es.alice.created_t
    got_c := es.alice.got_c
    got_d := es.alice.got_d
    got_t := es.alice.got_t
    decision := some (decision_from_execState es) }

/-- Final party state for Bob, derived from `execState_of` and `decision_from_execState`. -/
def finalBob (ch : BidirectionalChannel) : Protocol.PartyState :=
  let es := execState_of ch
  { party := es.bob.party
    created_c := es.bob.created_c
    created_d := es.bob.created_d
    created_t := es.bob.created_t
    got_c := es.bob.got_c
    got_d := es.bob.got_d
    got_t := es.bob.got_t
    decision := some (decision_from_execState es) }

/-! ## Execution Construction -/

/-- Build a GrayCore.Execution from channel parameters. -/
noncomputable def exec_of (ch : BidirectionalChannel) : GrayCore.Execution P_TGP GMsg :=
  { alice_states := fun t => if t = 0 then initialAlice else finalAlice ch
    bob_states := fun t => if t = 0 then initialBob else finalBob ch
    sent := fun _ => criticalMS
    delivered := fun t => if t = 1 then deliveredMS ch else 0 }

/-! ## Generated Executions -/

/-- An execution is generated if it equals exec_of for some channel. -/
def IsGenerated (exec : GrayCore.Execution P_TGP GMsg) : Prop :=
  ∃ ch : BidirectionalChannel, exec = exec_of ch

/-! ## Key Lemmas -/

/-- Initial state has no decision. -/
theorem initial_no_decision_alice : P_TGP.decided initialAlice = none := by
  simp [P_TGP, initialAlice, Channel.initial_execution]

theorem initial_no_decision_bob : P_TGP.decided initialBob = none := by
  simp [P_TGP, initialBob, Channel.initial_execution]

/-- P_TGP.decided on finalAlice returns the semantics-derived decision. -/
theorem decided_finalAlice (ch : BidirectionalChannel) :
    P_TGP.decided (finalAlice ch)
      = some (protoDecisionToGray (decision_from_execState (execState_of ch))) := by
  simp [finalAlice, P_TGP]

/-- P_TGP.decided on finalBob returns the semantics-derived decision. -/
theorem decided_finalBob (ch : BidirectionalChannel) :
    P_TGP.decided (finalBob ch)
      = some (protoDecisionToGray (decision_from_execState (execState_of ch))) := by
  simp [finalBob, P_TGP]

/-- Both partitioned → not both working. -/
theorem partitioned_not_working (ch : BidirectionalChannel) (h : both_partitioned ch = true) :
    both_working ch = false := by
  simp only [both_working, both_partitioned, beq_iff_eq, Bool.and_eq_true] at *
  obtain ⟨h_a, h_b⟩ := h
  simp [h_a, h_b]

/-- Both partitioned → no direction working. -/
theorem partitioned_no_dir_working (ch : BidirectionalChannel) (h : both_partitioned ch = true)
    (dir : Channel.Direction) : dirWorking ch dir = false := by
  simp only [both_partitioned, beq_iff_eq, Bool.and_eq_true] at h
  obtain ⟨h_a, h_b⟩ := h
  cases dir <;> simp [dirWorking, h_a, h_b]

/-- Both partitioned → empty delivery. -/
theorem partitioned_empty_delivery (ch : BidirectionalChannel) (h : both_partitioned ch = true) :
    deliveredMS ch = 0 := by
  simp only [deliveredMS]
  rw [Multiset.filter_eq_nil]
  intro m _
  have := partitioned_no_dir_working ch h m.1
  simp [this]

/-- Both partitioned → delivered always 0. -/
theorem partitioned_no_delivery (ch : BidirectionalChannel) (h : both_partitioned ch = true) :
    ∀ t, (exec_of ch).delivered t = 0 := by
  intro t
  simp only [exec_of]
  by_cases ht : t = 1
  · simp only [ht, ↓reduceIte]; exact partitioned_empty_delivery ch h
  · simp only [ht, ↓reduceIte]

/-- Both partitioned → IsNoChannel. -/
theorem partitioned_implies_no_channel (ch : BidirectionalChannel) (h : both_partitioned ch = true) :
    GrayCore.IsNoChannel (exec_of ch) :=
  partitioned_no_delivery ch h

/-- Both working → deliveredMS contains all critical messages. -/
theorem working_full_delivery (ch : BidirectionalChannel) (h : both_working ch = true) :
    deliveredMS ch = criticalMS := by
  simp only [deliveredMS, both_working, beq_iff_eq, Bool.and_eq_true] at *
  obtain ⟨h_a, h_b⟩ := h
  rw [Multiset.filter_eq_self]
  intro m _
  cases hd : m.1 <;> simp [dirWorking, h_a, h_b]

/-! ## Decision Lemmas (Proved, not axiomatized) -/

/-- At t=1, Alice has a decision (finalAlice always has decision = some ...). -/
theorem alice_has_decision_at_1 (ch : BidirectionalChannel) :
    (P_TGP.decided ((exec_of ch).alice_states 1)).isSome = true := by
  simp [exec_of, decided_finalAlice]

/-- At t=1, Bob has a decision (finalBob always has decision = some ...). -/
theorem bob_has_decision_at_1 (ch : BidirectionalChannel) :
    (P_TGP.decided ((exec_of ch).bob_states 1)).isSome = true := by
  simp [exec_of, decided_finalBob]

/-- Alice's decision equals the decision at t=1 (the first decision time). -/
theorem alice_decision_eq_t1 (ch : BidirectionalChannel) :
    GrayCore.alice_decision (exec_of ch) = P_TGP.decided (finalAlice ch) := by
  classical
  unfold GrayCore.alice_decision

  let p : Nat → Prop :=
    fun t => (P_TGP.decided ((exec_of ch).alice_states t)).isSome = true

  have hp1 : p 1 := by simp [p, exec_of, decided_finalAlice]

  by_cases hEx : ∃ t, p t
  · simp only [hEx, p, ↓reduceDIte]

    have hp0 : ¬ p 0 := by
      have h : P_TGP.decided ((exec_of ch).alice_states 0) = none := by
        simpa [exec_of] using initial_no_decision_alice
      simp [p, h]

    have hfind : Nat.find hEx = 1 := by
      have hle : Nat.find hEx ≤ 1 := Nat.find_le hp1
      have hne0 : Nat.find hEx ≠ 0 := by
        intro h0
        have : p 0 := by simpa [p, h0] using (Nat.find_spec hEx)
        exact hp0 this
      have hge : 1 ≤ Nat.find hEx := (Nat.succ_le_iff).2 (Nat.pos_of_ne_zero hne0)
      exact le_antisymm hle hge

    simp [exec_of, hfind]
  · exact (hEx ⟨1, hp1⟩).elim

/-- Bob's decision equals the decision at t=1 (the first decision time). -/
theorem bob_decision_eq_t1 (ch : BidirectionalChannel) :
    GrayCore.bob_decision (exec_of ch) = P_TGP.decided (finalBob ch) := by
  classical
  unfold GrayCore.bob_decision

  let p : Nat → Prop :=
    fun t => (P_TGP.decided ((exec_of ch).bob_states t)).isSome = true

  have hp1 : p 1 := by simp [p, exec_of, decided_finalBob]

  by_cases hEx : ∃ t, p t
  · simp only [hEx, p, ↓reduceDIte]

    have hp0 : ¬ p 0 := by
      have h : P_TGP.decided ((exec_of ch).bob_states 0) = none := by
        simpa [exec_of] using initial_no_decision_bob
      simp [p, h]

    have hfind : Nat.find hEx = 1 := by
      have hle : Nat.find hEx ≤ 1 := Nat.find_le hp1
      have hne0 : Nat.find hEx ≠ 0 := by
        intro h0
        have : p 0 := by simpa [p, h0] using (Nat.find_spec hEx)
        exact hp0 this
      have hge : 1 ≤ Nat.find hEx := (Nat.succ_le_iff).2 (Nat.pos_of_ne_zero hne0)
      exact le_antisymm hle hge

    simp [exec_of, hfind]
  · exact (hEx ⟨1, hp1⟩).elim

/-! ## Main Theorems -/

/-- Agreement on generated executions: both always decide the same. -/
theorem agreement_on_generated :
    GrayCore.AgreementOn P_TGP GMsg IsGenerated := by
  intro exec ⟨ch, h_gen⟩
  subst h_gen
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  -- Both sides are literally the same expression now.
  simp [decided_finalAlice, decided_finalBob]

/-- Total termination: both always decide. -/
theorem total_termination_on_generated :
    GrayCore.TotalTerminationOn P_TGP GMsg IsGenerated := by
  intro exec ⟨ch, h_gen⟩
  subst h_gen
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  -- Both are `some ...` by construction
  simp [decided_finalAlice, decided_finalBob]

/-- Abort on no-channel: NoChannel → both Abort. -/
theorem abort_on_no_channel_generated :
    GrayCore.AbortOnNoChannelOn P_TGP GMsg IsGenerated := by
  intro exec ⟨ch, h_gen⟩ h_no
  subst h_gen
  -- NoChannel means delivered = 0 at all times → both_working = false
  have h_not_work : both_working ch = false := by
    by_contra h_work
    have h_working : both_working ch = true := by
      cases h : both_working ch <;> simp_all
    have hdeliv : (exec_of ch).delivered 1 ≠ 0 := by
      simp only [exec_of, ↓reduceIte]
      rw [working_full_delivery ch h_working]
      simp [criticalMS, criticalMsgs]
    exact hdeliv (h_no 1)
  -- Use the bridge lemma to get the decision
  have hdec : decision_from_execState (execState_of ch) = Protocol.Decision.Abort := by
    simp [decision_from_execState, attacks_global_iff_both_working, h_not_work]
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  simp [decided_finalAlice, decided_finalBob, hdec, protoDecisionToGray]

/-- Every critical message is flooded (sent every tick). -/
theorem critical_flooded (ch : BidirectionalChannel) (m : GMsg) (hm : m ∈ criticalMsgs) :
    GrayCore.IsFlooded (exec_of ch) m := by
  intro N
  use N
  simp only [GrayCore.sentCountUpTo, exec_of]
  -- Each tick contributes 1 to the count for m (m appears once in criticalMsgs)
  have h_count_one : criticalMS.count m = 1 := by
    simp only [criticalMS, criticalMsgs] at hm ⊢
    fin_cases hm <;> native_decide
  -- Sum of N copies of 1 is N
  have hsum : (Finset.range N).sum (fun _ => criticalMS.count m) = N := by
    simp [h_count_one]
  -- Goal is sentCountUpTo ... ≥ N, which reduces to N ≥ N
  simp only [hsum, le_refl]

/-- Channel soundness: delivered ≤ buffer. -/
theorem channel_sound_exec_of (ch : BidirectionalChannel) :
    GrayCore.ChannelSound (exec_of ch) := by
  intro t
  simp only [exec_of, GrayCore.sentUpTo, GrayCore.deliveredUpTo]
  by_cases ht : t = 1
  · -- t = 1: delivered is deliveredMS, sent up to t=1 is criticalMS
    subst ht
    simp only [↓reduceIte, Finset.range_one, Finset.sum_singleton]
    -- deliveredMS ≤ criticalMS because it's a filter
    exact Multiset.filter_le _ _
  · -- t ≠ 1: delivered is 0
    simp only [ht, ↓reduceIte]
    exact Multiset.zero_le _

/-- LiveByDeadline forces both_working for our model. -/
theorem live_implies_working (ch : BidirectionalChannel)
    (h_live : GrayCore.LiveByDeadline (exec_of ch) 2) :
    both_working ch = true := by
  -- Pick a message in each direction and show that direction must be working
  have h_ab : dirWorking ch Channel.Direction.AliceToBob = true := by
    -- (AliceToBob, C) is flooded
    have h_flooded := critical_flooded ch (Channel.Direction.AliceToBob, Protocol.MessageType.C)
      (by simp [criticalMsgs])
    -- By LiveByDeadline, it gets delivered by t < 2
    obtain ⟨t, ht_bound, ht_deliv⟩ := h_live.2 _ h_flooded
    -- Only t=1 delivers anything
    interval_cases t
    · simp [exec_of] at ht_deliv
    · simp only [exec_of, ↓reduceIte] at ht_deliv
      -- deliveredMS is a filter of criticalMS
      simp only [deliveredMS, Multiset.count_filter] at ht_deliv
      -- If count > 0, the filter condition must be true for the message
      by_contra h_not
      have hfalse : dirWorking ch Channel.Direction.AliceToBob = false := by
        cases h : dirWorking ch Channel.Direction.AliceToBob <;> simp_all
      simp only [hfalse, Bool.false_eq_true, ↓reduceIte, gt_iff_lt, Nat.not_lt_zero] at ht_deliv
  have h_ba : dirWorking ch Channel.Direction.BobToAlice = true := by
    have h_flooded := critical_flooded ch (Channel.Direction.BobToAlice, Protocol.MessageType.C)
      (by simp [criticalMsgs])
    obtain ⟨t, ht_bound, ht_deliv⟩ := h_live.2 _ h_flooded
    interval_cases t
    · simp [exec_of] at ht_deliv
    · simp only [exec_of, ↓reduceIte] at ht_deliv
      simp only [deliveredMS, Multiset.count_filter] at ht_deliv
      by_contra h_not
      have hfalse : dirWorking ch Channel.Direction.BobToAlice = false := by
        cases h : dirWorking ch Channel.Direction.BobToAlice <;> simp_all
      simp only [hfalse, Bool.false_eq_true, ↓reduceIte, gt_iff_lt, Nat.not_lt_zero] at ht_deliv
  -- Both directions working → both_working
  simp only [both_working, Bool.and_eq_true, beq_iff_eq]
  cases h_a : ch.alice_to_bob <;> cases h_b : ch.bob_to_alice <;>
    simp_all [dirWorking]

/-- Attack on live: LiveByDeadline → both Attack. -/
theorem attack_on_live_generated :
    GrayCore.AttackOnLiveOn P_TGP GMsg IsGenerated 2 := by
  intro exec ⟨ch, h_gen⟩ h_live
  subst h_gen
  have h_work := live_implies_working ch h_live
  -- Use the bridge lemma to get the decision
  have hdec : decision_from_execState (execState_of ch) = Protocol.Decision.Attack := by
    simp [decision_from_execState, attacks_global_iff_both_working, h_work]
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  simp [decided_finalAlice, decided_finalBob, hdec, protoDecisionToGray]

/-- Finite-time termination: decides by T=2. -/
theorem finite_time_termination_generated :
    GrayCore.FiniteTimeTerminationOn P_TGP GMsg IsGenerated := by
  use 2
  intro exec ⟨ch, h_gen⟩
  subst h_gen
  -- At t=1 < 2, both have decided (by construction)
  constructor
  · use 1
    constructor
    · decide  -- 1 < 2
    · simp [exec_of, finalAlice, P_TGP]
  · use 1
    constructor
    · decide  -- 1 < 2
    · simp [exec_of, finalBob, P_TGP]

/-! ## The Complete Correctness Theorem -/

/-- TGP correctness: all properties hold on generated executions with T=2. -/
theorem tgp_correctness_interpreted :
    ∃ (P : GrayCore.ProtocolSpec) (Msg : Type) (_ : DecidableEq Msg)
      (Gen : GrayCore.Execution P Msg → Prop),
      GrayCore.AgreementOn P Msg Gen ∧
      GrayCore.TotalTerminationOn P Msg Gen ∧
      GrayCore.AbortOnNoChannelOn P Msg Gen ∧
      GrayCore.AttackOnLiveOn P Msg Gen 2 ∧
      GrayCore.FiniteTimeTerminationOn P Msg Gen :=
  ⟨P_TGP, GMsg, inferInstance, IsGenerated,
   agreement_on_generated,
   total_termination_on_generated,
   abort_on_no_channel_generated,
   attack_on_live_generated,
   finite_time_termination_generated⟩

end GrayInterp
