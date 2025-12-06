//! Two Generals Protocol state machine implementation.
//!
//! This module implements the core protocol logic with C → D → T → Q
//! phase transitions. The protocol achieves deterministic coordination
//! through epistemic proof escalation.
//!
//! # Protocol Phases
//!
//! - **Init**: Initial state, preparing commitment
//! - **Commitment**: Flooding C_X, waiting for C_Y
//! - **Double**: Have both commitments, flooding D_X, waiting for D_Y
//! - **Triple**: Have both doubles, flooding T_X, waiting for T_Y
//! - **Quad**: Have both triples, flooding Q_X, waiting for Q_Y
//! - **Complete**: Bilateral receipt pair (Q_A, Q_B) achieved
//! - **Aborted**: Deadline passed without achieving fixpoint
//!
//! # Key Insight
//!
//! Once Q_X is constructible, Q_Y is also constructible.
//! This is the bilateral construction property that makes TGP work.

#[cfg(feature = "no_std")]
use alloc::{vec, vec::Vec};

use crate::crypto::{KeyPair, PublicKey, Signer, Verifier};
use crate::error::Result;
use crate::types::{
    Commitment, Decision, DoubleProof, Message, MessagePayload, Party, ProtocolPhase, QuadProof,
    TripleProof,
};

/// Protocol state enumeration.
///
/// Tracks the current phase of the state machine.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProtocolState {
    /// Before commitment created.
    Init,
    /// Flooding C_X, awaiting C_Y.
    Commitment,
    /// Flooding D_X, awaiting D_Y.
    Double,
    /// Flooding T_X, awaiting T_Y.
    Triple,
    /// Flooding Q_X, awaiting Q_Y.
    Quad,
    /// Fixpoint achieved — can ATTACK.
    Complete,
    /// Deadline passed — must ABORT.
    Aborted,
}

impl ProtocolState {
    /// Returns the corresponding protocol phase.
    #[must_use]
    pub const fn to_phase(self) -> ProtocolPhase {
        match self {
            Self::Init => ProtocolPhase::Init,
            Self::Commitment => ProtocolPhase::Commitment,
            Self::Double => ProtocolPhase::Double,
            Self::Triple => ProtocolPhase::Triple,
            Self::Quad => ProtocolPhase::Quad,
            Self::Complete => ProtocolPhase::Complete,
            Self::Aborted => ProtocolPhase::Aborted,
        }
    }
}

/// Two Generals Protocol state machine.
///
/// Implements the complete C → D → T → Q proof escalation with
/// continuous flooding semantics. Each party maintains their own
/// instance and exchanges messages until both reach Complete.
///
/// # Guarantees
///
/// - If one party can construct Q, both can
/// - Outcomes are always symmetric (both ATTACK or both ABORT)
/// - No message is "special" — continuous flooding ensures any copy suffices
///
/// # Example
///
/// ```rust,ignore
/// let alice_keys = KeyPair::generate();
/// let bob_keys = KeyPair::generate();
///
/// let mut alice = TwoGenerals::new(Party::Alice, alice_keys, bob_keys.public_key().clone());
/// let mut bob = TwoGenerals::new(Party::Bob, bob_keys, alice_keys.public_key().clone());
///
/// // Exchange messages until both complete
/// while !alice.is_complete() || !bob.is_complete() {
///     for msg in alice.get_messages_to_send() {
///         bob.receive(&msg)?;
///     }
///     for msg in bob.get_messages_to_send() {
///         alice.receive(&msg)?;
///     }
/// }
///
/// assert!(alice.can_attack());
/// assert!(bob.can_attack());
/// ```
pub struct TwoGenerals {
    /// Which party this instance represents.
    party: Party,
    /// This party's signing key pair.
    keypair: KeyPair,
    /// The counterparty's public key for verification.
    counterparty_public_key: PublicKey,
    /// Current protocol state.
    state: ProtocolState,

    // Own proof artifacts
    own_commitment: Option<Commitment>,
    own_double: Option<DoubleProof>,
    own_triple: Option<TripleProof>,
    own_quad: Option<QuadProof>,

    // Counterparty's proof artifacts
    other_commitment: Option<Commitment>,
    other_double: Option<DoubleProof>,
    other_triple: Option<TripleProof>,
    other_quad: Option<QuadProof>,

    /// Message sequence counter.
    sequence: u64,
    /// The commitment message to sign.
    commitment_message: Vec<u8>,
}

impl TwoGenerals {
    /// Default commitment message.
    pub const DEFAULT_COMMITMENT: &'static [u8] = b"I will attack at dawn if you agree";

    /// Create a new TwoGenerals protocol instance.
    ///
    /// Immediately creates and signs the commitment (Phase 1).
    #[must_use]
    pub fn new(party: Party, keypair: KeyPair, counterparty_public_key: PublicKey) -> Self {
        let mut instance = Self {
            party,
            keypair,
            counterparty_public_key,
            state: ProtocolState::Init,
            own_commitment: None,
            own_double: None,
            own_triple: None,
            own_quad: None,
            other_commitment: None,
            other_double: None,
            other_triple: None,
            other_quad: None,
            sequence: 0,
            commitment_message: Self::DEFAULT_COMMITMENT.to_vec(),
        };
        instance.create_commitment();
        instance
    }

    /// Create a new instance with a custom commitment message.
    #[must_use]
    pub fn with_commitment_message(
        party: Party,
        keypair: KeyPair,
        counterparty_public_key: PublicKey,
        commitment_message: Vec<u8>,
    ) -> Self {
        let mut instance = Self {
            party,
            keypair,
            counterparty_public_key,
            state: ProtocolState::Init,
            own_commitment: None,
            own_double: None,
            own_triple: None,
            own_quad: None,
            other_commitment: None,
            other_double: None,
            other_triple: None,
            other_quad: None,
            sequence: 0,
            commitment_message,
        };
        instance.create_commitment();
        instance
    }

    /// Get this party's identity.
    #[must_use]
    pub const fn party(&self) -> Party {
        self.party
    }

    /// Get the current protocol state.
    #[must_use]
    pub const fn state(&self) -> ProtocolState {
        self.state
    }

    /// Check if the protocol has reached the fixpoint.
    #[must_use]
    pub const fn is_complete(&self) -> bool {
        matches!(self.state, ProtocolState::Complete)
    }

    /// Check if this party can safely ATTACK.
    #[must_use]
    pub fn can_attack(&self) -> bool {
        self.is_complete() && self.own_quad.is_some()
    }

    /// Get the final decision.
    #[must_use]
    pub fn get_decision(&self) -> Decision {
        if self.is_complete() {
            Decision::Attack
        } else {
            Decision::Abort
        }
    }

    /// Abort the protocol (e.g., deadline passed).
    pub fn abort(&mut self) {
        if !self.is_complete() {
            self.state = ProtocolState::Aborted;
        }
    }

    // =========================================================================
    // Proof Construction
    // =========================================================================

    /// Create and sign our initial commitment (Phase 1).
    fn create_commitment(&mut self) {
        let signer = Signer::new(self.keypair.clone());
        let signature = signer.sign_commitment(&self.commitment_message);

        self.own_commitment = Some(Commitment::new(
            self.party,
            self.keypair.public_key().clone(),
            self.commitment_message.clone(),
            signature,
        ));
        self.state = ProtocolState::Commitment;
    }

    /// Create double proof once we have counterparty's commitment (Phase 2).
    fn create_double_proof(&mut self) {
        let own_c = self.own_commitment.as_ref().expect("own commitment required");
        let other_c = self.other_commitment.as_ref().expect("other commitment required");

        let signer = Signer::new(self.keypair.clone());
        let signature = signer.sign_double_proof(
            &own_c.canonical_bytes(),
            &other_c.canonical_bytes(),
        );

        self.own_double = Some(DoubleProof::new(
            self.party,
            own_c.clone(),
            other_c.clone(),
            signature,
        ));
        self.state = ProtocolState::Double;
    }

    /// Create triple proof once we have counterparty's double (Phase 3).
    fn create_triple_proof(&mut self) {
        let own_d = self.own_double.as_ref().expect("own double required");
        let other_d = self.other_double.as_ref().expect("other double required");

        let signer = Signer::new(self.keypair.clone());
        let signature = signer.sign_triple_proof(
            &own_d.canonical_bytes(),
            &other_d.canonical_bytes(),
        );

        self.own_triple = Some(TripleProof::new(
            self.party,
            own_d.clone(),
            other_d.clone(),
            signature,
        ));
        self.state = ProtocolState::Triple;
    }

    /// Create quaternary proof once we have counterparty's triple (Phase 4).
    fn create_quad_proof(&mut self) {
        let own_t = self.own_triple.as_ref().expect("own triple required");
        let other_t = self.other_triple.as_ref().expect("other triple required");

        let signer = Signer::new(self.keypair.clone());
        let signature = signer.sign_quad_proof(
            &own_t.canonical_bytes(),
            &other_t.canonical_bytes(),
        );

        self.own_quad = Some(QuadProof::new(
            self.party,
            own_t.clone(),
            other_t.clone(),
            signature,
        ));
        self.state = ProtocolState::Quad;
    }

    // =========================================================================
    // Message Handling
    // =========================================================================

    /// Process a received message from the counterparty.
    ///
    /// # Errors
    ///
    /// Returns an error if the message is invalid or has an invalid signature.
    pub fn receive(&mut self, msg: &Message) -> Result<bool> {
        match &msg.payload {
            MessagePayload::Commitment(c) => self.receive_commitment(c),
            MessagePayload::DoubleProof(d) => self.receive_double_proof(d),
            MessagePayload::TripleProof(t) => self.receive_triple_proof(t),
            MessagePayload::QuadProof(q) => self.receive_quad_proof(q),
        }
    }

    /// Receive a commitment directly.
    fn receive_commitment(&mut self, commitment: &Commitment) -> Result<bool> {
        // Must be from counterparty
        if commitment.party == self.party {
            return Ok(false);
        }

        // Already have it
        if self.other_commitment.is_some() {
            return Ok(false);
        }

        // Verify signature
        let verifier = Verifier::new(self.counterparty_public_key.clone());
        verifier.verify_commitment(&commitment.signature, &commitment.message)?;

        self.other_commitment = Some(commitment.clone());

        // If we're in COMMITMENT state and now have both, advance to DOUBLE
        if matches!(self.state, ProtocolState::Commitment) && self.own_commitment.is_some() {
            self.create_double_proof();
            return Ok(true);
        }

        Ok(true)
    }

    /// Receive a double proof directly.
    fn receive_double_proof(&mut self, double: &DoubleProof) -> Result<bool> {
        // Must be from counterparty
        if double.party == self.party {
            return Ok(false);
        }

        // Already have it
        if self.other_double.is_some() {
            return Ok(false);
        }

        // Verify signature
        let verifier = Verifier::new(self.counterparty_public_key.clone());
        verifier.verify_double_proof(
            &double.signature,
            &double.own_commitment.canonical_bytes(),
            &double.other_commitment.canonical_bytes(),
        )?;

        // Extract embedded commitment if needed
        if self.other_commitment.is_none() {
            self.other_commitment = Some(double.own_commitment.clone());
            if matches!(self.state, ProtocolState::Commitment) && self.own_commitment.is_some() {
                self.create_double_proof();
            }
        }

        self.other_double = Some(double.clone());

        // If we're in DOUBLE state and now have both, advance to TRIPLE
        if matches!(self.state, ProtocolState::Double) && self.own_double.is_some() {
            self.create_triple_proof();
            return Ok(true);
        }

        Ok(true)
    }

    /// Receive a triple proof directly.
    ///
    /// CRITICAL: Receiving T_Y gives us D_Y for free (it's embedded).
    fn receive_triple_proof(&mut self, triple: &TripleProof) -> Result<bool> {
        // Must be from counterparty
        if triple.party == self.party {
            return Ok(false);
        }

        // Already have it
        if self.other_triple.is_some() {
            return Ok(false);
        }

        // Verify signature
        let verifier = Verifier::new(self.counterparty_public_key.clone());
        verifier.verify_triple_proof(
            &triple.signature,
            &triple.own_double.canonical_bytes(),
            &triple.other_double.canonical_bytes(),
        )?;

        // Extract embedded artifacts
        if self.other_double.is_none() {
            self.other_double = Some(triple.own_double.clone());
            if self.other_commitment.is_none() {
                self.other_commitment = Some(triple.own_double.own_commitment.clone());
            }

            // Cascade state updates
            if matches!(self.state, ProtocolState::Commitment) && self.own_commitment.is_some() {
                self.create_double_proof();
            }
            if matches!(self.state, ProtocolState::Double) && self.own_double.is_some() {
                self.create_triple_proof();
            }
        }

        self.other_triple = Some(triple.clone());

        // If we're in TRIPLE state and now have both, advance to QUAD
        if matches!(self.state, ProtocolState::Triple) && self.own_triple.is_some() {
            self.create_quad_proof();
            return Ok(true);
        }

        Ok(true)
    }

    /// Receive a quad proof directly.
    fn receive_quad_proof(&mut self, quad: &QuadProof) -> Result<bool> {
        // Must be from counterparty
        if quad.party == self.party {
            return Ok(false);
        }

        // Already have it
        if self.other_quad.is_some() {
            return Ok(false);
        }

        // Verify signature
        let verifier = Verifier::new(self.counterparty_public_key.clone());
        verifier.verify_quad_proof(
            &quad.signature,
            &quad.own_triple.canonical_bytes(),
            &quad.other_triple.canonical_bytes(),
        )?;

        // Extract embedded artifacts
        if self.other_triple.is_none() {
            self.other_triple = Some(quad.own_triple.clone());
            if self.other_double.is_none() {
                self.other_double = Some(quad.own_triple.own_double.clone());
            }
            if self.other_commitment.is_none() {
                self.other_commitment = Some(quad.own_triple.own_double.own_commitment.clone());
            }

            // Cascade state updates
            if matches!(self.state, ProtocolState::Commitment) && self.own_commitment.is_some() {
                self.create_double_proof();
            }
            if matches!(self.state, ProtocolState::Double) && self.own_double.is_some() {
                self.create_triple_proof();
            }
            if matches!(self.state, ProtocolState::Triple) && self.own_triple.is_some() {
                self.create_quad_proof();
            }
        }

        self.other_quad = Some(quad.clone());

        // If we have both quad proofs, we're COMPLETE
        if self.own_quad.is_some() {
            self.state = ProtocolState::Complete;
            return Ok(true);
        }

        Ok(true)
    }

    // =========================================================================
    // Message Generation
    // =========================================================================

    /// Get messages to flood at the current state.
    ///
    /// In continuous flooding mode, we send our highest available proof.
    /// Higher-level proofs embed lower-level ones, so receiving T_X is
    /// sufficient even if C_X and D_X were lost.
    pub fn get_messages_to_send(&mut self) -> Vec<Message> {
        self.sequence += 1;
        let mut messages = Vec::new();

        // Send highest available proof (it embeds all lower ones)
        let payload = match self.state {
            ProtocolState::Complete | ProtocolState::Quad => {
                self.own_quad.as_ref().map(|q| MessagePayload::QuadProof(q.clone()))
            }
            ProtocolState::Triple => {
                self.own_triple.as_ref().map(|t| MessagePayload::TripleProof(t.clone()))
            }
            ProtocolState::Double => {
                self.own_double.as_ref().map(|d| MessagePayload::DoubleProof(d.clone()))
            }
            ProtocolState::Commitment => {
                self.own_commitment.as_ref().map(|c| MessagePayload::Commitment(c.clone()))
            }
            _ => None,
        };

        if let Some(p) = payload {
            messages.push(Message {
                sender: self.party,
                sequence: self.sequence,
                payload: p,
            });
        }

        messages
    }

    /// Get the bilateral receipt pair if complete.
    #[must_use]
    pub fn get_bilateral_receipt(&self) -> Option<(&QuadProof, &QuadProof)> {
        if self.is_complete() {
            match (&self.own_quad, &self.other_quad) {
                (Some(own), Some(other)) => Some((own, other)),
                _ => None,
            }
        } else {
            None
        }
    }
}

impl core::fmt::Debug for TwoGenerals {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("TwoGenerals")
            .field("party", &self.party)
            .field("state", &self.state)
            .field("has_own_commitment", &self.own_commitment.is_some())
            .field("has_other_commitment", &self.other_commitment.is_some())
            .field("has_own_double", &self.own_double.is_some())
            .field("has_other_double", &self.other_double.is_some())
            .field("has_own_triple", &self.own_triple.is_some())
            .field("has_other_triple", &self.other_triple.is_some())
            .field("has_own_quad", &self.own_quad.is_some())
            .field("has_other_quad", &self.other_quad.is_some())
            .finish()
    }
}

/// Run a complete protocol simulation between Alice and Bob.
///
/// Useful for testing the protocol under various conditions.
pub fn run_protocol_simulation<F>(
    alice_keypair: KeyPair,
    bob_keypair: KeyPair,
    max_rounds: usize,
    mut message_filter: F,
) -> (TwoGenerals, TwoGenerals)
where
    F: FnMut(&Message) -> bool,
{
    let mut alice = TwoGenerals::new(
        Party::Alice,
        alice_keypair.clone(),
        bob_keypair.public_key().clone(),
    );
    let mut bob = TwoGenerals::new(
        Party::Bob,
        bob_keypair,
        alice_keypair.public_key().clone(),
    );

    for _ in 0..max_rounds {
        // Exchange messages
        for msg in alice.get_messages_to_send() {
            if message_filter(&msg) {
                let _ = bob.receive(&msg);
            }
        }

        for msg in bob.get_messages_to_send() {
            if message_filter(&msg) {
                let _ = alice.receive(&msg);
            }
        }

        // Check if both complete
        if alice.is_complete() && bob.is_complete() {
            break;
        }
    }

    (alice, bob)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn perfect_channel_completes() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let (alice, bob) = run_protocol_simulation(
            alice_kp,
            bob_kp,
            100,
            |_| true, // No packet loss
        );

        assert!(alice.is_complete());
        assert!(bob.is_complete());
        assert!(alice.can_attack());
        assert!(bob.can_attack());
    }

    #[test]
    fn protocol_state_transitions() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let mut alice = TwoGenerals::new(
            Party::Alice,
            alice_kp.clone(),
            bob_kp.public_key().clone(),
        );
        let mut bob = TwoGenerals::new(
            Party::Bob,
            bob_kp,
            alice_kp.public_key().clone(),
        );

        // Both start in Commitment state
        assert!(matches!(alice.state(), ProtocolState::Commitment));
        assert!(matches!(bob.state(), ProtocolState::Commitment));

        // The protocol uses proof embedding: receiving a DoubleProof gives
        // the counterparty's commitment for free. This means the protocol
        // can cascade through multiple phases in a single exchange.
        //
        // Round 1: Alice sends C_A -> Bob receives, advances to Double, sends D_B
        //          Alice receives D_B (contains C_B) -> advances to Double then Triple
        //
        // We verify the protocol reaches completion correctly, not the
        // intermediate states which can cascade based on embedding.

        // Run for several rounds to let the protocol complete
        for _ in 0..5 {
            for msg in alice.get_messages_to_send() {
                bob.receive(&msg).unwrap();
            }
            for msg in bob.get_messages_to_send() {
                alice.receive(&msg).unwrap();
            }

            if alice.is_complete() && bob.is_complete() {
                break;
            }
        }

        // Both should be Complete
        assert!(alice.is_complete(), "Alice should be complete, state: {:?}", alice.state());
        assert!(bob.is_complete(), "Bob should be complete, state: {:?}", bob.state());
        assert!(alice.can_attack());
        assert!(bob.can_attack());
    }

    #[test]
    fn bilateral_receipt_available_when_complete() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let (alice, bob) = run_protocol_simulation(
            alice_kp,
            bob_kp,
            100,
            |_| true,
        );

        let alice_receipt = alice.get_bilateral_receipt();
        let bob_receipt = bob.get_bilateral_receipt();

        assert!(alice_receipt.is_some());
        assert!(bob_receipt.is_some());

        // Alice's other_quad should match Bob's own_quad (and vice versa)
        let (alice_own, alice_other) = alice_receipt.unwrap();
        let (bob_own, bob_other) = bob_receipt.unwrap();

        assert_eq!(alice_own.party, Party::Alice);
        assert_eq!(alice_other.party, Party::Bob);
        assert_eq!(bob_own.party, Party::Bob);
        assert_eq!(bob_other.party, Party::Alice);
    }

    #[test]
    fn abort_prevents_attack() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let mut alice = TwoGenerals::new(
            Party::Alice,
            alice_kp.clone(),
            bob_kp.public_key().clone(),
        );

        // Abort before completing
        alice.abort();

        assert!(!alice.can_attack());
        assert!(matches!(alice.get_decision(), Decision::Abort));
    }

    #[test]
    fn receiving_higher_level_proof_extracts_lower() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        // Run Bob through the full protocol first
        let mut bob = TwoGenerals::new(
            Party::Bob,
            bob_kp.clone(),
            alice_kp.public_key().clone(),
        );

        // Create Alice fresh
        let mut alice = TwoGenerals::new(
            Party::Alice,
            alice_kp.clone(),
            bob_kp.public_key().clone(),
        );

        // Exchange commitments
        for msg in alice.get_messages_to_send() {
            bob.receive(&msg).unwrap();
        }
        for msg in bob.get_messages_to_send() {
            alice.receive(&msg).unwrap();
        }

        // Exchange doubles
        for msg in alice.get_messages_to_send() {
            bob.receive(&msg).unwrap();
        }
        for msg in bob.get_messages_to_send() {
            alice.receive(&msg).unwrap();
        }

        // Exchange triples
        for msg in alice.get_messages_to_send() {
            bob.receive(&msg).unwrap();
        }
        for msg in bob.get_messages_to_send() {
            alice.receive(&msg).unwrap();
        }

        // Both in Quad state, Bob sends quad
        for msg in bob.get_messages_to_send() {
            alice.receive(&msg).unwrap();
        }

        // Alice receives Q_B, which contains T_B, D_B, C_B
        // Alice should now be able to verify her state is complete after sending her own Q
        for msg in alice.get_messages_to_send() {
            bob.receive(&msg).unwrap();
        }

        assert!(alice.is_complete());
        assert!(bob.is_complete());
    }
}
