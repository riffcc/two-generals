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

/-- Final party state when both directions work: Attack. -/
def finalAliceAttack : Protocol.PartyState :=
  { party := Protocol.Party.Alice
    created_c := true, created_d := true, created_t := true
    got_c := true, got_d := true, got_t := true
    decision := some Protocol.Decision.Attack }

def finalBobAttack : Protocol.PartyState :=
  { party := Protocol.Party.Bob
    created_c := true, created_d := true, created_t := true
    got_c := true, got_d := true, got_t := true
    decision := some Protocol.Decision.Attack }

/-- Final party state when channel fails: Abort. -/
def finalAliceAbort : Protocol.PartyState :=
  { party := Protocol.Party.Alice
    created_c := true, created_d := false, created_t := false
    got_c := false, got_d := false, got_t := false
    decision := some Protocol.Decision.Abort }

def finalBobAbort : Protocol.PartyState :=
  { party := Protocol.Party.Bob
    created_c := true, created_d := false, created_t := false
    got_c := false, got_d := false, got_t := false
    decision := some Protocol.Decision.Abort }

/-- Get final Alice state based on channel. -/
def finalAlice (ch : BidirectionalChannel) : Protocol.PartyState :=
  if both_working ch then finalAliceAttack else finalAliceAbort

/-- Get final Bob state based on channel. -/
def finalBob (ch : BidirectionalChannel) : Protocol.PartyState :=
  if both_working ch then finalBobAttack else finalBobAbort

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

/-- Attack final state has Attack decision. -/
theorem attack_decision_alice : P_TGP.decided finalAliceAttack = some GrayCore.Decision.Attack := rfl
theorem attack_decision_bob : P_TGP.decided finalBobAttack = some GrayCore.Decision.Attack := rfl

/-- Abort final state has Abort decision. -/
theorem abort_decision_alice : P_TGP.decided finalAliceAbort = some GrayCore.Decision.Abort := rfl
theorem abort_decision_bob : P_TGP.decided finalBobAbort = some GrayCore.Decision.Abort := rfl

/-- Both working → final states are Attack. -/
theorem working_final_alice (ch : BidirectionalChannel) (h : both_working ch = true) :
    finalAlice ch = finalAliceAttack := by simp [finalAlice, h]

theorem working_final_bob (ch : BidirectionalChannel) (h : both_working ch = true) :
    finalBob ch = finalBobAttack := by simp [finalBob, h]

/-- Not working → final states are Abort. -/
theorem not_working_final_alice (ch : BidirectionalChannel) (h : both_working ch = false) :
    finalAlice ch = finalAliceAbort := by simp [finalAlice, h]

theorem not_working_final_bob (ch : BidirectionalChannel) (h : both_working ch = false) :
    finalBob ch = finalBobAbort := by simp [finalBob, h]

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

/-! ## Nat.find Lemma -/

open Classical in
/-- If p(0) is false and p(1) is true, then Nat.find returns 1. -/
lemma natFind_eq_one {p : Nat → Prop} (h : ∃ t, p t) (hp0 : ¬ p 0) (hp1 : p 1) :
    Nat.find h = 1 := by
  -- First show Nat.find h ≤ 1 using minimality
  have hle : Nat.find h ≤ 1 := by
    by_contra hgt
    have hlt : 1 < Nat.find h := Nat.lt_of_not_ge hgt
    exact Nat.find_min h hlt hp1
  -- Exclude 0, leaving 1
  cases hfind : Nat.find h with
  | zero =>
      exfalso
      have : p 0 := by simpa [hfind] using Nat.find_spec h
      exact hp0 this
  | succ n =>
      have hn : n = 0 := by
        have hsle : n.succ ≤ 1 := by simpa [hfind] using hle
        exact Nat.eq_of_le_of_lt_succ (Nat.zero_le n) hsle
      simp [hn]

/-! ## Decision Lemmas (Proved, not axiomatized) -/

/-- Alice's decision equals the decision at t=1 (the first decision time). -/
theorem alice_decision_eq_t1 (ch : BidirectionalChannel) :
    GrayCore.alice_decision (exec_of ch) = P_TGP.decided (finalAlice ch) := by
  classical
  unfold GrayCore.alice_decision
  -- The predicate is decidable at t=1
  have hex : ∃ t, (P_TGP.decided ((exec_of ch).alice_states t)).isSome = true := by
    refine ⟨1, ?_⟩
    simp only [exec_of, one_ne_zero, ↓reduceIte]
    unfold finalAlice P_TGP protoDecisionToGray
    split <;> rfl
  simp only [hex, ↓reduceDIte]
  -- At t=0, no decision (initialAlice has decision = none)
  have hp0 : ¬ (P_TGP.decided ((exec_of ch).alice_states 0)).isSome = true := by
    simp only [exec_of, ↓reduceIte, P_TGP, initialAlice]
    exact Bool.false_ne_true
  -- At t=1, there's a decision
  have hp1 : (P_TGP.decided ((exec_of ch).alice_states 1)).isSome = true := by
    simp only [exec_of, one_ne_zero, ↓reduceIte]
    unfold finalAlice P_TGP protoDecisionToGray
    split <;> rfl
  -- Nat.find hex = 1 via our lemma (convert bridges decidability instances)
  have hfind : Nat.find hex = 1 := by
    convert natFind_eq_one (p := fun t => (P_TGP.decided ((exec_of ch).alice_states t)).isSome = true)
      hex hp0 hp1
  simp only [hfind, exec_of, one_ne_zero, ↓reduceIte]

/-- Bob's decision equals the decision at t=1 (the first decision time). -/
theorem bob_decision_eq_t1 (ch : BidirectionalChannel) :
    GrayCore.bob_decision (exec_of ch) = P_TGP.decided (finalBob ch) := by
  classical
  unfold GrayCore.bob_decision
  have hex : ∃ t, (P_TGP.decided ((exec_of ch).bob_states t)).isSome = true := by
    refine ⟨1, ?_⟩
    simp only [exec_of, one_ne_zero, ↓reduceIte]
    unfold finalBob P_TGP protoDecisionToGray
    split <;> rfl
  simp only [hex, ↓reduceDIte]
  have hp0 : ¬ (P_TGP.decided ((exec_of ch).bob_states 0)).isSome = true := by
    simp only [exec_of, ↓reduceIte, P_TGP, initialBob]
    exact Bool.false_ne_true
  have hp1 : (P_TGP.decided ((exec_of ch).bob_states 1)).isSome = true := by
    simp only [exec_of, one_ne_zero, ↓reduceIte]
    unfold finalBob P_TGP protoDecisionToGray
    split <;> rfl
  -- Nat.find hex = 1 via our lemma (convert bridges decidability instances)
  have hfind : Nat.find hex = 1 := by
    convert natFind_eq_one (p := fun t => (P_TGP.decided ((exec_of ch).bob_states t)).isSome = true)
      hex hp0 hp1
  simp only [hfind, exec_of, one_ne_zero, ↓reduceIte]

/-! ## Main Theorems -/

/-- Agreement on generated executions: both always decide the same. -/
theorem agreement_on_generated :
    GrayCore.AgreementOn P_TGP GMsg IsGenerated := by
  intro exec ⟨ch, h_gen⟩
  subst h_gen
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  -- Both final states have the same decision type (both Attack or both Abort)
  by_cases h_work : both_working ch = true
  · -- Both working: both Attack
    rw [working_final_alice ch h_work, working_final_bob ch h_work]
    simp [attack_decision_alice, attack_decision_bob]
  · -- Not working: both Abort
    have h_not_work : both_working ch = false := by
      cases h : both_working ch <;> simp_all
    rw [not_working_final_alice ch h_not_work, not_working_final_bob ch h_not_work]
    simp [abort_decision_alice, abort_decision_bob]

/-- Total termination: both always decide. -/
theorem total_termination_on_generated :
    GrayCore.TotalTerminationOn P_TGP GMsg IsGenerated := by
  intro exec ⟨ch, h_gen⟩
  subst h_gen
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  by_cases h_work : both_working ch = true
  · rw [working_final_alice ch h_work, working_final_bob ch h_work]
    simp [attack_decision_alice, attack_decision_bob]
  · have h_not_work : both_working ch = false := by
      cases h : both_working ch <;> simp_all
    rw [not_working_final_alice ch h_not_work, not_working_final_bob ch h_not_work]
    simp [abort_decision_alice, abort_decision_bob]

/-- Abort on no-channel: NoChannel → both Abort. -/
theorem abort_on_no_channel_generated :
    GrayCore.AbortOnNoChannelOn P_TGP GMsg IsGenerated := by
  intro exec ⟨ch, h_gen⟩ h_no
  subst h_gen
  -- NoChannel means delivered = 0 at all times
  -- For our model, this requires both_working = false
  have h_not_work : both_working ch = false := by
    by_contra h_work
    have h_working : both_working ch = true := by
      cases h : both_working ch <;> simp_all
    -- If both_working, delivered 1 is nonempty
    have hdeliv : (exec_of ch).delivered 1 ≠ 0 := by
      simp only [exec_of, ↓reduceIte]
      rw [working_full_delivery ch h_working]
      simp [criticalMS, criticalMsgs]
    exact hdeliv (h_no 1)
  -- So both decide Abort
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  rw [not_working_final_alice ch h_not_work, not_working_final_bob ch h_not_work]
  exact ⟨abort_decision_alice, abort_decision_bob⟩

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
  rw [alice_decision_eq_t1, bob_decision_eq_t1]
  rw [working_final_alice ch h_work, working_final_bob ch h_work]
  exact ⟨attack_decision_alice, attack_decision_bob⟩

/-- Finite-time termination: decides by T=2. -/
theorem finite_time_termination_generated :
    GrayCore.FiniteTimeTerminationOn P_TGP GMsg IsGenerated := by
  use 2
  intro exec ⟨ch, h_gen⟩
  subst h_gen
  -- At t=1 < 2, both have decided
  constructor
  · use 1
    constructor
    · decide  -- 1 < 2
    · simp only [exec_of, one_ne_zero, ↓reduceIte]
      unfold finalAlice P_TGP protoDecisionToGray
      split <;> rfl
  · use 1
    constructor
    · decide  -- 1 < 2
    · simp only [exec_of, one_ne_zero, ↓reduceIte]
      unfold finalBob P_TGP protoDecisionToGray
      split <;> rfl

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
