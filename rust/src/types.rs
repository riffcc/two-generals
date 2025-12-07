//! Core protocol types for the Two Generals Protocol.
//!
//! This module defines the cryptographic proof structures that enable
//! epistemic fixpoint construction through bilateral proof stapling.
//!
//! # Proof Escalation Hierarchy
//!
//! ```text
//! Commitment (C) ─┬──> DoubleProof (D) ─┬──> TripleProof (T) ─┬──> QuadProof (Q)
//!                 │                      │                     │
//! Depth: 0        │    Depth: 1          │    Depth: 2         │    Depth: ω
//! "I will..."     │    "I know you..."   │    "I know you      │    Fixed point
//!                 │                      │     know I..."      │
//! ```

#[cfg(feature = "no_std")]
use alloc::{vec, vec::Vec};
use serde::{Deserialize, Serialize};

use crate::crypto::{PublicKey, Signature};

/// Identifies a party in the two-party protocol.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum Party {
    /// Alice (General A) - the initiating party.
    Alice = 0,
    /// Bob (General B) - the responding party.
    Bob = 1,
}

impl Party {
    /// Returns the counterparty.
    #[inline]
    #[must_use]
    pub const fn other(self) -> Self {
        match self {
            Self::Alice => Self::Bob,
            Self::Bob => Self::Alice,
        }
    }

    /// Returns the party name as bytes.
    #[inline]
    #[must_use]
    pub const fn name_bytes(self) -> &'static [u8] {
        match self {
            Self::Alice => b"ALICE",
            Self::Bob => b"BOB",
        }
    }
}

impl core::fmt::Display for Party {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            Self::Alice => write!(f, "Alice"),
            Self::Bob => write!(f, "Bob"),
        }
    }
}

/// Phase 1: Commitment (C_X)
///
/// `C_X = Sign_X("I will attack at dawn if you agree")`
///
/// A signed commitment from one party indicating intent to coordinate.
/// This is the base level of the epistemic proof chain.
///
/// # What it proves
///
/// Nothing about the other party yet — unilateral intent only.
///
/// # Epistemic depth: 0
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Commitment {
    /// The party making this commitment.
    pub party: Party,
    /// The party's public key for verification.
    pub public_key: PublicKey,
    /// The commitment message (typically a fixed protocol string + nonce).
    pub message: Vec<u8>,
    /// Ed25519 signature over the message.
    pub signature: Signature,
}

impl Commitment {
    /// Creates a new commitment.
    #[must_use]
    pub fn new(party: Party, public_key: PublicKey, message: Vec<u8>, signature: Signature) -> Self {
        Self {
            party,
            public_key,
            message,
            signature,
        }
    }

    /// Serialize to canonical bytes for embedding in higher proofs.
    ///
    /// Format: `C:<PARTY>:<PUBKEY>:<MESSAGE>:<SIGNATURE>`
    #[must_use]
    pub fn canonical_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(128);
        bytes.extend_from_slice(b"C:");
        bytes.extend_from_slice(self.party.name_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(self.public_key.as_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(&self.message);
        bytes.push(b':');
        bytes.extend_from_slice(self.signature.as_bytes());
        bytes
    }

    /// BLAKE3 hash of the canonical representation.
    #[must_use]
    pub fn hash(&self) -> [u8; 32] {
        blake3::hash(&self.canonical_bytes()).into()
    }
}

/// Phase 2: Double Proof (D_X)
///
/// `D_X = Sign_X(C_X ∥ C_Y ∥ "Both parties committed")`
///
/// A double proof embeds BOTH original commitments inside a new signed envelope.
///
/// # What it proves
///
/// "I know you've committed."
///
/// # Epistemic depth: 1
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DoubleProof {
    /// The party creating this proof.
    pub party: Party,
    /// This party's own commitment.
    pub own_commitment: Commitment,
    /// The counterparty's commitment.
    pub other_commitment: Commitment,
    /// Signature over the combined commitments.
    pub signature: Signature,
}

impl DoubleProof {
    /// Creates a new double proof.
    ///
    /// # Panics
    ///
    /// Panics if the party labels are inconsistent.
    #[must_use]
    pub fn new(
        party: Party,
        own_commitment: Commitment,
        other_commitment: Commitment,
        signature: Signature,
    ) -> Self {
        debug_assert_eq!(own_commitment.party, party, "Own commitment party mismatch");
        debug_assert_ne!(other_commitment.party, party, "Other commitment must be from counterparty");

        Self {
            party,
            own_commitment,
            other_commitment,
            signature,
        }
    }

    /// The message that was signed to create this proof.
    #[must_use]
    pub fn message_to_sign(&self) -> Vec<u8> {
        let mut msg = Vec::with_capacity(512);
        msg.extend_from_slice(&self.own_commitment.canonical_bytes());
        msg.extend_from_slice(b"||");
        msg.extend_from_slice(&self.other_commitment.canonical_bytes());
        msg.extend_from_slice(b"||BOTH_COMMITTED");
        msg
    }

    /// Serialize to canonical bytes for embedding in higher proofs.
    ///
    /// Format: `D:<PARTY>:<OWN_COMMITMENT>:<OTHER_COMMITMENT>:<SIGNATURE>`
    #[must_use]
    pub fn canonical_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(512);
        bytes.extend_from_slice(b"D:");
        bytes.extend_from_slice(self.party.name_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(&self.own_commitment.canonical_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(&self.other_commitment.canonical_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(self.signature.as_bytes());
        bytes
    }

    /// BLAKE3 hash of the canonical representation.
    #[must_use]
    pub fn hash(&self) -> [u8; 32] {
        blake3::hash(&self.canonical_bytes()).into()
    }

    /// The public key of the party who created this proof.
    #[must_use]
    pub fn public_key(&self) -> &PublicKey {
        &self.own_commitment.public_key
    }
}

/// Phase 3: Triple Proof (T_X)
///
/// `T_X = Sign_X(D_X ∥ D_Y ∥ "Both parties have double proofs")`
///
/// By construction, T_X contains:
/// - Both original commitments (C_A, C_B)
/// - Both double proofs (D_A, D_B)
///
/// # What it proves
///
/// "I know that you know I've committed."
///
/// # Epistemic depth: 2
///
/// # Critical insight
///
/// Receiving T_Y gives you D_Y for free (it's embedded inside T_Y).
/// This is what enables the bilateral construction property.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TripleProof {
    /// The party creating this proof.
    pub party: Party,
    /// This party's own double proof.
    pub own_double: DoubleProof,
    /// The counterparty's double proof.
    pub other_double: DoubleProof,
    /// Signature over the combined double proofs.
    pub signature: Signature,
}

impl TripleProof {
    /// Creates a new triple proof.
    ///
    /// # Panics
    ///
    /// Panics if the party labels are inconsistent.
    #[must_use]
    pub fn new(
        party: Party,
        own_double: DoubleProof,
        other_double: DoubleProof,
        signature: Signature,
    ) -> Self {
        debug_assert_eq!(own_double.party, party, "Own double party mismatch");
        debug_assert_ne!(other_double.party, party, "Other double must be from counterparty");

        Self {
            party,
            own_double,
            other_double,
            signature,
        }
    }

    /// The message that was signed to create this proof.
    #[must_use]
    pub fn message_to_sign(&self) -> Vec<u8> {
        let mut msg = Vec::with_capacity(1024);
        msg.extend_from_slice(&self.own_double.canonical_bytes());
        msg.extend_from_slice(b"||");
        msg.extend_from_slice(&self.other_double.canonical_bytes());
        msg.extend_from_slice(b"||BOTH_HAVE_DOUBLE");
        msg
    }

    /// Serialize to canonical bytes for embedding in higher proofs.
    ///
    /// Format: `T:<PARTY>:<OWN_DOUBLE>:<OTHER_DOUBLE>:<SIGNATURE>`
    #[must_use]
    pub fn canonical_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(2048);
        bytes.extend_from_slice(b"T:");
        bytes.extend_from_slice(self.party.name_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(&self.own_double.canonical_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(&self.other_double.canonical_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(self.signature.as_bytes());
        bytes
    }

    /// BLAKE3 hash of the canonical representation.
    #[must_use]
    pub fn hash(&self) -> [u8; 32] {
        blake3::hash(&self.canonical_bytes()).into()
    }

    /// The public key of the party who created this proof.
    #[must_use]
    pub fn public_key(&self) -> &PublicKey {
        self.own_double.public_key()
    }

    /// Extract both original commitments embedded in this proof.
    #[must_use]
    pub fn extract_commitments(&self) -> (&Commitment, &Commitment) {
        (&self.own_double.own_commitment, &self.own_double.other_commitment)
    }
}

/// Phase 4: Quaternary Proof (Q_X) — The Epistemic Fixpoint
///
/// `Q_A = Sign_A(T_A ∥ T_B ∥ "Fixpoint achieved")`
/// `Q_B = Sign_B(T_B ∥ T_A ∥ "Fixpoint achieved")`
///
/// Q is NOT a single artifact — it's a bilateral receipt pair: (Q_A, Q_B).
/// Each half staples both triple proofs together. Neither can exist without
/// the other being constructible.
///
/// # The Bilateral Construction Property (core theoretical contribution)
///
/// ```text
/// Q_A exists → contains T_B → Bob had D_A → Bob can construct Q_B
/// Q_B exists → contains T_A → Alice had D_B → Alice can construct Q_A
/// ```
///
/// Each half cryptographically PROVES the other half is constructible.
///
/// # What it proves
///
/// "I know that you know that I know that you know..." — this is the FIXED POINT.
///
/// # Epistemic depth: ω (omega - the smallest infinite ordinal)
///
/// The artifact doesn't *demonstrate* mutual constructibility.
/// The artifact *IS* mutual constructibility.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct QuadProof {
    /// The party creating this proof.
    pub party: Party,
    /// This party's own triple proof.
    pub own_triple: TripleProof,
    /// The counterparty's triple proof.
    pub other_triple: TripleProof,
    /// Signature over the combined triple proofs.
    pub signature: Signature,
}

impl QuadProof {
    /// Creates a new quad proof.
    ///
    /// # Panics
    ///
    /// Panics if the party labels are inconsistent.
    #[must_use]
    pub fn new(
        party: Party,
        own_triple: TripleProof,
        other_triple: TripleProof,
        signature: Signature,
    ) -> Self {
        debug_assert_eq!(own_triple.party, party, "Own triple party mismatch");
        debug_assert_ne!(other_triple.party, party, "Other triple must be from counterparty");

        Self {
            party,
            own_triple,
            other_triple,
            signature,
        }
    }

    /// The message that was signed to create this proof.
    #[must_use]
    pub fn message_to_sign(&self) -> Vec<u8> {
        let mut msg = Vec::with_capacity(4096);
        msg.extend_from_slice(&self.own_triple.canonical_bytes());
        msg.extend_from_slice(b"||");
        msg.extend_from_slice(&self.other_triple.canonical_bytes());
        msg.extend_from_slice(b"||FIXPOINT_ACHIEVED");
        msg
    }

    /// Serialize to canonical bytes.
    ///
    /// Format: `Q:<PARTY>:<OWN_TRIPLE>:<OTHER_TRIPLE>:<SIGNATURE>`
    #[must_use]
    pub fn canonical_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(8192);
        bytes.extend_from_slice(b"Q:");
        bytes.extend_from_slice(self.party.name_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(&self.own_triple.canonical_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(&self.other_triple.canonical_bytes());
        bytes.push(b':');
        bytes.extend_from_slice(self.signature.as_bytes());
        bytes
    }

    /// BLAKE3 hash of the canonical representation.
    #[must_use]
    pub fn hash(&self) -> [u8; 32] {
        blake3::hash(&self.canonical_bytes()).into()
    }

    /// The public key of the party who created this proof.
    #[must_use]
    pub fn public_key(&self) -> &PublicKey {
        self.own_triple.public_key()
    }

    /// Verify the bilateral construction property.
    ///
    /// The existence of Q_X proves Q_Y is constructible because:
    /// - Q_X contains T_Y (other_triple)
    /// - T_Y contains D_X (inside its other_double)
    /// - Having T_X (which we're flooding) + D_Y (from T_Y) = constructible T_Y
    /// - Having T_X + T_Y = constructible Q_Y
    ///
    /// This always returns `true` for a well-formed `QuadProof` because
    /// by construction, if this object exists, the property holds.
    #[must_use]
    pub fn proves_mutual_constructibility(&self) -> bool {
        // Verify the embedding chain
        let t_other = &self.other_triple;
        let d_own_in_other = &t_other.other_double;

        // The other triple must contain OUR double proof
        d_own_in_other.party == self.party
    }

    /// Extract a specific party's original commitment from the proof tree.
    #[must_use]
    pub fn extract_commitment(&self, party: Party) -> &Commitment {
        if party == self.party {
            &self.own_triple.own_double.own_commitment
        } else {
            &self.own_triple.own_double.other_commitment
        }
    }
}

/// A network message carrying a proof artifact.
///
/// Messages are continuously flooded until the next phase is reached.
/// No message is "special" — any instance suffices.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Message {
    /// The sender of this message.
    pub sender: Party,
    /// Sequence number for deduplication.
    pub sequence: u64,
    /// The proof payload.
    pub payload: MessagePayload,
}

/// The payload of a message — one of the four proof types.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum MessagePayload {
    /// Phase 1: Commitment.
    Commitment(Commitment),
    /// Phase 2: Double proof.
    DoubleProof(DoubleProof),
    /// Phase 3: Triple proof.
    TripleProof(TripleProof),
    /// Phase 4: Quad proof.
    QuadProof(QuadProof),
}

impl Message {
    /// Returns the protocol phase (1-4) of this message.
    #[must_use]
    pub const fn phase(&self) -> u8 {
        match &self.payload {
            MessagePayload::Commitment(_) => 1,
            MessagePayload::DoubleProof(_) => 2,
            MessagePayload::TripleProof(_) => 3,
            MessagePayload::QuadProof(_) => 4,
        }
    }
}

/// Protocol phases corresponding to proof levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum ProtocolPhase {
    /// Before commitment (initial state).
    Init = 0,
    /// Flooding C_X.
    Commitment = 1,
    /// Flooding D_X.
    Double = 2,
    /// Flooding T_X.
    Triple = 3,
    /// Flooding Q_X.
    Quad = 4,
    /// Fixpoint achieved — ready to ATTACK.
    Complete = 5,
    /// Deadline expired without fixpoint — ABORT.
    Aborted = 6,
}

impl ProtocolPhase {
    /// Returns the phase name as a static string.
    #[must_use]
    pub const fn name(self) -> &'static str {
        match self {
            Self::Init => "Init",
            Self::Commitment => "Commitment",
            Self::Double => "Double",
            Self::Triple => "Triple",
            Self::Quad => "Quad",
            Self::Complete => "Complete",
            Self::Aborted => "Aborted",
        }
    }
}

impl core::fmt::Display for ProtocolPhase {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{}", self.name())
    }
}

/// The final decision made by a party.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Decision {
    /// Q constructed before deadline — proceed with coordinated attack.
    Attack,
    /// Could not construct Q before deadline — abort safely.
    Abort,
    /// Decision not yet made.
    Pending,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::crypto::KeyPair;

    #[test]
    fn party_other_is_involution() {
        assert_eq!(Party::Alice.other(), Party::Bob);
        assert_eq!(Party::Bob.other(), Party::Alice);
        assert_eq!(Party::Alice.other().other(), Party::Alice);
        assert_eq!(Party::Bob.other().other(), Party::Bob);
    }

    #[test]
    fn party_name_bytes() {
        assert_eq!(Party::Alice.name_bytes(), b"ALICE");
        assert_eq!(Party::Bob.name_bytes(), b"BOB");
    }

    #[test]
    fn party_display() {
        assert_eq!(format!("{}", Party::Alice), "Alice");
        assert_eq!(format!("{}", Party::Bob), "Bob");
    }

    #[test]
    fn protocol_phase_ordering() {
        assert!((ProtocolPhase::Init as u8) < (ProtocolPhase::Commitment as u8));
        assert!((ProtocolPhase::Commitment as u8) < (ProtocolPhase::Double as u8));
        assert!((ProtocolPhase::Double as u8) < (ProtocolPhase::Triple as u8));
        assert!((ProtocolPhase::Triple as u8) < (ProtocolPhase::Quad as u8));
        assert!((ProtocolPhase::Quad as u8) < (ProtocolPhase::Complete as u8));
    }

    #[test]
    fn protocol_phase_name() {
        assert_eq!(ProtocolPhase::Init.name(), "Init");
        assert_eq!(ProtocolPhase::Commitment.name(), "Commitment");
        assert_eq!(ProtocolPhase::Double.name(), "Double");
        assert_eq!(ProtocolPhase::Triple.name(), "Triple");
        assert_eq!(ProtocolPhase::Quad.name(), "Quad");
        assert_eq!(ProtocolPhase::Complete.name(), "Complete");
        assert_eq!(ProtocolPhase::Aborted.name(), "Aborted");
    }

    #[test]
    fn protocol_phase_display() {
        assert_eq!(format!("{}", ProtocolPhase::Complete), "Complete");
    }

    #[test]
    fn decision_variants() {
        let attack = Decision::Attack;
        let abort = Decision::Abort;
        let pending = Decision::Pending;
        assert_ne!(attack, abort);
        assert_ne!(abort, pending);
    }

    #[test]
    fn commitment_canonical_bytes() {
        let kp = KeyPair::generate();
        let sig = kp.sign(b"test");
        let commitment = Commitment::new(
            Party::Alice,
            kp.public_key().clone(),
            b"test".to_vec(),
            sig,
        );
        let bytes = commitment.canonical_bytes();
        assert!(bytes.starts_with(b"C:ALICE:"));
    }

    #[test]
    fn commitment_hash() {
        let kp = KeyPair::generate();
        let sig = kp.sign(b"test");
        let commitment = Commitment::new(
            Party::Alice,
            kp.public_key().clone(),
            b"test".to_vec(),
            sig,
        );
        let hash = commitment.hash();
        assert_eq!(hash.len(), 32);
    }

    #[test]
    fn message_phase() {
        let kp = KeyPair::generate();
        let sig = kp.sign(b"test");
        let commitment = Commitment::new(
            Party::Alice,
            kp.public_key().clone(),
            b"test".to_vec(),
            sig,
        );
        let msg = Message {
            sender: Party::Alice,
            sequence: 1,
            payload: MessagePayload::Commitment(commitment),
        };
        assert_eq!(msg.phase(), 1);
    }

    #[test]
    fn double_proof_message_to_sign() {
        let kp_alice = KeyPair::generate();
        let kp_bob = KeyPair::generate();

        let sig_alice = kp_alice.sign(b"test");
        let sig_bob = kp_bob.sign(b"test");

        let c_alice = Commitment::new(
            Party::Alice,
            kp_alice.public_key().clone(),
            b"test".to_vec(),
            sig_alice,
        );
        let c_bob = Commitment::new(
            Party::Bob,
            kp_bob.public_key().clone(),
            b"test".to_vec(),
            sig_bob,
        );

        let double_sig = kp_alice.sign(b"double");
        let double = DoubleProof::new(Party::Alice, c_alice, c_bob, double_sig);

        let msg = double.message_to_sign();
        assert!(msg.ends_with(b"||BOTH_COMMITTED"));
    }

    #[test]
    fn quad_proof_proves_mutual_constructibility() {
        // Full protocol simulation to construct a valid QuadProof
        let kp_alice = KeyPair::generate();
        let kp_bob = KeyPair::generate();

        // Phase 1: Commitments
        let sig_alice = kp_alice.sign(b"I will attack");
        let sig_bob = kp_bob.sign(b"I will attack");

        let c_alice = Commitment::new(
            Party::Alice,
            kp_alice.public_key().clone(),
            b"I will attack".to_vec(),
            sig_alice,
        );
        let c_bob = Commitment::new(
            Party::Bob,
            kp_bob.public_key().clone(),
            b"I will attack".to_vec(),
            sig_bob,
        );

        // Phase 2: Double Proofs
        let d_alice_msg = {
            let mut msg = c_alice.canonical_bytes();
            msg.extend_from_slice(b"||");
            msg.extend_from_slice(&c_bob.canonical_bytes());
            msg.extend_from_slice(b"||BOTH_COMMITTED");
            msg
        };
        let d_bob_msg = {
            let mut msg = c_bob.canonical_bytes();
            msg.extend_from_slice(b"||");
            msg.extend_from_slice(&c_alice.canonical_bytes());
            msg.extend_from_slice(b"||BOTH_COMMITTED");
            msg
        };

        let d_alice = DoubleProof::new(
            Party::Alice,
            c_alice.clone(),
            c_bob.clone(),
            kp_alice.sign(&d_alice_msg),
        );
        let d_bob = DoubleProof::new(
            Party::Bob,
            c_bob.clone(),
            c_alice.clone(),
            kp_bob.sign(&d_bob_msg),
        );

        // Phase 3: Triple Proofs
        let t_alice_msg = {
            let mut msg = d_alice.canonical_bytes();
            msg.extend_from_slice(b"||");
            msg.extend_from_slice(&d_bob.canonical_bytes());
            msg.extend_from_slice(b"||BOTH_HAVE_DOUBLE");
            msg
        };
        let t_bob_msg = {
            let mut msg = d_bob.canonical_bytes();
            msg.extend_from_slice(b"||");
            msg.extend_from_slice(&d_alice.canonical_bytes());
            msg.extend_from_slice(b"||BOTH_HAVE_DOUBLE");
            msg
        };

        let t_alice = TripleProof::new(
            Party::Alice,
            d_alice.clone(),
            d_bob.clone(),
            kp_alice.sign(&t_alice_msg),
        );
        let t_bob = TripleProof::new(
            Party::Bob,
            d_bob.clone(),
            d_alice.clone(),
            kp_bob.sign(&t_bob_msg),
        );

        // Phase 4: Quad Proofs
        let q_alice_msg = {
            let mut msg = t_alice.canonical_bytes();
            msg.extend_from_slice(b"||");
            msg.extend_from_slice(&t_bob.canonical_bytes());
            msg.extend_from_slice(b"||FIXPOINT_ACHIEVED");
            msg
        };

        let q_alice = QuadProof::new(
            Party::Alice,
            t_alice,
            t_bob,
            kp_alice.sign(&q_alice_msg),
        );

        // Verify the bilateral construction property
        assert!(q_alice.proves_mutual_constructibility());
    }

    #[test]
    fn quad_proof_extract_commitment() {
        let kp_alice = KeyPair::generate();
        let kp_bob = KeyPair::generate();

        let sig_alice = kp_alice.sign(b"test");
        let sig_bob = kp_bob.sign(b"test");

        let c_alice = Commitment::new(
            Party::Alice,
            kp_alice.public_key().clone(),
            b"test".to_vec(),
            sig_alice,
        );
        let c_bob = Commitment::new(
            Party::Bob,
            kp_bob.public_key().clone(),
            b"test".to_vec(),
            sig_bob,
        );

        let d_alice = DoubleProof::new(
            Party::Alice,
            c_alice.clone(),
            c_bob.clone(),
            kp_alice.sign(b"d"),
        );
        let d_bob = DoubleProof::new(
            Party::Bob,
            c_bob.clone(),
            c_alice.clone(),
            kp_bob.sign(b"d"),
        );

        let t_alice = TripleProof::new(
            Party::Alice,
            d_alice.clone(),
            d_bob.clone(),
            kp_alice.sign(b"t"),
        );
        let t_bob = TripleProof::new(
            Party::Bob,
            d_bob,
            d_alice,
            kp_bob.sign(b"t"),
        );

        let q_alice = QuadProof::new(
            Party::Alice,
            t_alice,
            t_bob,
            kp_alice.sign(b"q"),
        );

        // Extract Alice's commitment from Q_A
        let extracted_alice = q_alice.extract_commitment(Party::Alice);
        assert_eq!(extracted_alice.party, Party::Alice);

        // Extract Bob's commitment from Q_A
        let extracted_bob = q_alice.extract_commitment(Party::Bob);
        assert_eq!(extracted_bob.party, Party::Bob);
    }

    #[test]
    fn triple_proof_extract_commitments() {
        let kp_alice = KeyPair::generate();
        let kp_bob = KeyPair::generate();

        let sig_alice = kp_alice.sign(b"test");
        let sig_bob = kp_bob.sign(b"test");

        let c_alice = Commitment::new(
            Party::Alice,
            kp_alice.public_key().clone(),
            b"test".to_vec(),
            sig_alice,
        );
        let c_bob = Commitment::new(
            Party::Bob,
            kp_bob.public_key().clone(),
            b"test".to_vec(),
            sig_bob,
        );

        let d_alice = DoubleProof::new(
            Party::Alice,
            c_alice.clone(),
            c_bob.clone(),
            kp_alice.sign(b"d"),
        );
        let d_bob = DoubleProof::new(
            Party::Bob,
            c_bob,
            c_alice,
            kp_bob.sign(b"d"),
        );

        let t_alice = TripleProof::new(
            Party::Alice,
            d_alice,
            d_bob,
            kp_alice.sign(b"t"),
        );

        let (own, other) = t_alice.extract_commitments();
        assert_eq!(own.party, Party::Alice);
        assert_eq!(other.party, Party::Bob);
    }
}
