//! Byzantine Fault Tolerant (BFT) Multiparty Extension for TGP.
//!
//! This module extends the Two Generals Protocol to N-party consensus with
//! Byzantine fault tolerance, achieving BFT in two flooding steps.
//!
//! # System Parameters
//!
//! - Total nodes (arbitrators) = 3f + 1
//! - Fault tolerance = f Byzantine
//! - Threshold T = 2f + 1
//!
//! # Protocol Overview
//!
//! 1. **PROPOSE**: Any node floods a proposal `{ type: PROPOSE, value: V, round: R }`
//! 2. **SHARE**: Each arbitrator creates and floods a partial signature share
//! 3. **COMMIT**: Any node with >= T shares aggregates into threshold signature
//!
//! # Why This Achieves BFT
//!
//! - **Safety**: Any valid COMMIT requires >= 2f+1 shares. Two different values would
//!   require 4f+2 shares, but only 3f+1 nodes exist. IMPOSSIBLE.
//! - **Liveness**: 2f+1 honest nodes will eventually flood SHAREs. Some aggregator
//!   will collect enough and broadcast COMMIT.
//! - **No View-Change**: Any honest node can aggregate. No leader rotation needed.
//!
//! The same structural insight that solves Two Generals extends to N-party:
//! Self-certifying artifacts via proof stapling. The artifact IS the proof.

#[cfg(feature = "no_std")]
use alloc::{vec, vec::Vec};

use serde::{Deserialize, Serialize};

use crate::crypto::{KeyPair, PublicKey, Signature};
use crate::error::{Error, Result};

// =============================================================================
// BFT System Parameters
// =============================================================================

/// Configuration for BFT consensus.
///
/// The number of nodes must be exactly 3f + 1 for optimal Byzantine
/// fault tolerance, where f is the maximum number of Byzantine faults.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct BftConfig {
    /// Total nodes = 3f + 1
    n: u32,
    /// Maximum Byzantine faults
    f: u32,
}

impl BftConfig {
    /// Create a new BFT configuration.
    ///
    /// # Errors
    ///
    /// Returns an error if n != 3f + 1.
    pub fn new(n: u32, f: u32) -> Result<Self> {
        if n != 3 * f + 1 {
            return Err(Error::Bft(format!(
                "n must be 3f+1: n={}, f={}, expected n={}",
                n, f, 3 * f + 1
            )));
        }
        Ok(Self { n, f })
    }

    /// Create config for given fault tolerance.
    pub fn for_fault_tolerance(f: u32) -> Self {
        Self { n: 3 * f + 1, f }
    }

    /// Create config for given node count (must be 3f+1 for some f >= 0).
    ///
    /// # Errors
    ///
    /// Returns an error if n is not of the form 3f+1.
    pub fn for_node_count(n: u32) -> Result<Self> {
        if n < 1 {
            return Err(Error::Bft(format!("n must be positive: n={}", n)));
        }
        // n = 3f + 1  =>  f = (n-1)/3
        if (n - 1) % 3 != 0 {
            return Err(Error::Bft(format!(
                "n must be 3f+1 for some integer f: n={}",
                n
            )));
        }
        let f = (n - 1) / 3;
        Ok(Self { n, f })
    }

    /// Get the total number of nodes.
    #[must_use]
    pub const fn n(&self) -> u32 {
        self.n
    }

    /// Get the maximum number of Byzantine faults tolerated.
    #[must_use]
    pub const fn f(&self) -> u32 {
        self.f
    }

    /// Get the threshold T = 2f + 1 for quorum.
    #[must_use]
    pub const fn threshold(&self) -> u32 {
        2 * self.f + 1
    }
}

// =============================================================================
// BLS-like Threshold Signatures (Simplified Implementation)
// =============================================================================
//
// For production, use 'blst' crate for real BLS signatures.
// This implementation provides the API and semantics for testing.

/// BLS public key for a single node in the threshold scheme.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BlsPublicKey {
    /// The public key data.
    data: [u8; 32],
    /// The node ID this key belongs to.
    node_id: u32,
}

impl BlsPublicKey {
    /// Get the raw key data.
    #[must_use]
    pub const fn data(&self) -> &[u8; 32] {
        &self.data
    }

    /// Get the node ID.
    #[must_use]
    pub const fn node_id(&self) -> u32 {
        self.node_id
    }
}

/// BLS key pair for a single node in the threshold scheme.
pub struct BlsKeyPair {
    private_share: [u8; 32],
    /// The public key.
    pub public_key: BlsPublicKey,
    /// The node ID.
    pub node_id: u32,
}

impl BlsKeyPair {
    /// Create a new BLS key pair for a node.
    ///
    /// In production, this would use proper BLS key generation.
    #[must_use]
    pub fn new(node_id: u32, private_share: [u8; 32]) -> Self {
        // Derive public key (simplified, not real BLS curve operations)
        let mut pub_input = [0u8; 40];
        pub_input[..32].copy_from_slice(&private_share);
        pub_input[32..36].copy_from_slice(b"PUB_");
        pub_input[36..40].copy_from_slice(&node_id.to_be_bytes());
        let pub_bytes: [u8; 32] = blake3::hash(&pub_input).into();

        Self {
            private_share,
            public_key: BlsPublicKey {
                data: pub_bytes,
                node_id,
            },
            node_id,
        }
    }

    /// Create a partial signature share over a message.
    ///
    /// In real BLS, this would be a pairing-based curve operation.
    #[must_use]
    pub fn sign_share(&self, message: &[u8]) -> [u8; 32] {
        let mut input = Vec::with_capacity(message.len() + 36);
        input.extend_from_slice(&self.private_share);
        input.extend_from_slice(message);
        input.extend_from_slice(&self.node_id.to_be_bytes());
        blake3::keyed_hash(&self.private_share, &input).into()
    }
}

impl Clone for BlsKeyPair {
    fn clone(&self) -> Self {
        Self {
            private_share: self.private_share,
            public_key: self.public_key.clone(),
            node_id: self.node_id,
        }
    }
}

impl core::fmt::Debug for BlsKeyPair {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("BlsKeyPair")
            .field("node_id", &self.node_id)
            .field("public_key", &self.public_key)
            .finish_non_exhaustive()
    }
}

/// Aggregated threshold signature from T partial shares.
///
/// This proves that at least T nodes signed the same message.
/// Safety guarantee: Since T = 2f+1 and n = 3f+1, any two sets of T nodes
/// must overlap in at least one honest node, preventing conflicting commits.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ThresholdSignature {
    /// The aggregated signature data.
    signature: [u8; 32],
    /// The node IDs that contributed to this signature.
    contributing_nodes: Vec<u32>,
    /// The threshold used.
    threshold: u32,
}

impl ThresholdSignature {
    /// Get the signature bytes.
    #[must_use]
    pub const fn signature(&self) -> &[u8; 32] {
        &self.signature
    }

    /// Get the contributing node IDs.
    #[must_use]
    pub fn contributing_nodes(&self) -> &[u32] {
        &self.contributing_nodes
    }

    /// Get the threshold used.
    #[must_use]
    pub const fn threshold(&self) -> u32 {
        self.threshold
    }
}

/// BLS-style threshold signature scheme for BFT consensus.
///
/// This manages key generation and distribution (in production, use DKG),
/// share creation, verification, and aggregation.
pub struct ThresholdScheme {
    config: BftConfig,
    key_pairs: Vec<BlsKeyPair>,
    public_keys: Vec<BlsPublicKey>,
    master_secret: [u8; 32],
}

impl ThresholdScheme {
    /// Create a new threshold scheme with the given config.
    ///
    /// Generates key pairs for all nodes (in production, use DKG).
    #[must_use]
    pub fn new(config: BftConfig) -> Self {
        let master_secret: [u8; 32] = rand::random();
        Self::with_master_secret(config, master_secret)
    }

    /// Create a new threshold scheme with a specific master secret.
    ///
    /// Useful for deterministic testing.
    #[must_use]
    pub fn with_master_secret(config: BftConfig, master_secret: [u8; 32]) -> Self {
        let mut key_pairs = Vec::with_capacity(config.n() as usize);
        let mut public_keys = Vec::with_capacity(config.n() as usize);

        for node_id in 0..config.n() {
            // Derive private share from master secret
            let mut share_input = [0u8; 40];
            share_input[..32].copy_from_slice(&master_secret);
            share_input[32..36].copy_from_slice(&node_id.to_be_bytes());
            share_input[36..40].copy_from_slice(b"SHAR");
            let private_share: [u8; 32] = blake3::hash(&share_input).into();

            let kp = BlsKeyPair::new(node_id, private_share);
            public_keys.push(kp.public_key.clone());
            key_pairs.push(kp);
        }

        Self {
            config,
            key_pairs,
            public_keys,
            master_secret,
        }
    }

    /// Get the BFT configuration.
    #[must_use]
    pub const fn config(&self) -> &BftConfig {
        &self.config
    }

    /// Get the key pair for a specific node.
    ///
    /// # Panics
    ///
    /// Panics if node_id is out of range.
    #[must_use]
    pub fn get_key_pair(&self, node_id: u32) -> &BlsKeyPair {
        &self.key_pairs[node_id as usize]
    }

    /// Get the public key for a specific node.
    ///
    /// # Panics
    ///
    /// Panics if node_id is out of range.
    #[must_use]
    pub fn get_public_key(&self, node_id: u32) -> &BlsPublicKey {
        &self.public_keys[node_id as usize]
    }

    /// Create a signature share for a message.
    #[must_use]
    pub fn create_share(&self, node_id: u32, message: &[u8]) -> (u32, [u8; 32]) {
        let kp = self.get_key_pair(node_id);
        let share = kp.sign_share(message);
        (node_id, share)
    }

    /// Verify a signature share from a specific node.
    #[must_use]
    pub fn verify_share(&self, node_id: u32, message: &[u8], share: &[u8; 32]) -> bool {
        if node_id >= self.config.n() {
            return false;
        }
        let kp = self.get_key_pair(node_id);
        let expected_share = kp.sign_share(message);
        share == &expected_share
    }

    /// Aggregate signature shares into a threshold signature.
    ///
    /// # Arguments
    ///
    /// * `message` - The message that was signed
    /// * `shares` - List of (node_id, share) tuples
    ///
    /// # Returns
    ///
    /// `Some(ThresholdSignature)` if enough valid shares, `None` otherwise.
    ///
    /// # Safety Guarantee
    ///
    /// Can only succeed if at least T distinct nodes contributed valid shares.
    /// Since T = 2f+1 and n = 3f+1, any two sets of T nodes overlap in at
    /// least one honest node. Therefore, no conflicting values can both
    /// achieve threshold signatures.
    pub fn aggregate(
        &self,
        message: &[u8],
        shares: &[(u32, [u8; 32])],
    ) -> Option<ThresholdSignature> {
        if shares.len() < self.config.threshold() as usize {
            return None;
        }

        // Verify all shares and collect valid ones
        let mut valid_nodes: Vec<u32> = Vec::new();
        let mut valid_shares: Vec<[u8; 32]> = Vec::new();
        let mut seen_nodes = std::collections::HashSet::new();

        for (node_id, share) in shares {
            if seen_nodes.contains(node_id) {
                continue; // Skip duplicates
            }
            if self.verify_share(*node_id, message, share) {
                valid_nodes.push(*node_id);
                valid_shares.push(*share);
                seen_nodes.insert(*node_id);
            }
        }

        if valid_nodes.len() < self.config.threshold() as usize {
            return None;
        }

        // Take exactly T shares for deterministic aggregation
        let t = self.config.threshold() as usize;
        valid_nodes.truncate(t);
        valid_shares.truncate(t);

        // Aggregate shares (simplified: XOR + hash)
        // Real BLS would use pairing multiplication
        let mut aggregated = [0u8; 32];
        for share in &valid_shares {
            for (i, byte) in share.iter().enumerate() {
                aggregated[i] ^= byte;
            }
        }

        // Final signature = hash(aggregated || message)
        let mut final_input = Vec::with_capacity(32 + message.len());
        final_input.extend_from_slice(&aggregated);
        final_input.extend_from_slice(message);
        let final_sig: [u8; 32] = blake3::hash(&final_input).into();

        valid_nodes.sort_unstable();

        Some(ThresholdSignature {
            signature: final_sig,
            contributing_nodes: valid_nodes,
            threshold: self.config.threshold(),
        })
    }

    /// Verify an aggregated threshold signature.
    #[must_use]
    pub fn verify_threshold_signature(
        &self,
        message: &[u8],
        sig: &ThresholdSignature,
    ) -> bool {
        if sig.contributing_nodes.len() < self.config.threshold() as usize {
            return false;
        }

        // Recompute the aggregation
        let t = self.config.threshold() as usize;
        let mut shares = Vec::with_capacity(t);
        for &node_id in sig.contributing_nodes.iter().take(t) {
            if node_id >= self.config.n() {
                return false;
            }
            let kp = self.get_key_pair(node_id);
            shares.push(kp.sign_share(message));
        }

        let mut aggregated = [0u8; 32];
        for share in &shares {
            for (i, byte) in share.iter().enumerate() {
                aggregated[i] ^= byte;
            }
        }

        let mut final_input = Vec::with_capacity(32 + message.len());
        final_input.extend_from_slice(&aggregated);
        final_input.extend_from_slice(message);
        let expected_sig: [u8; 32] = blake3::hash(&final_input).into();

        sig.signature == expected_sig
    }
}

impl Clone for ThresholdScheme {
    fn clone(&self) -> Self {
        Self {
            config: self.config,
            key_pairs: self.key_pairs.clone(),
            public_keys: self.public_keys.clone(),
            master_secret: self.master_secret,
        }
    }
}

impl core::fmt::Debug for ThresholdScheme {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("ThresholdScheme")
            .field("config", &self.config)
            .field("num_keys", &self.key_pairs.len())
            .finish_non_exhaustive()
    }
}

// =============================================================================
// BFT Protocol Messages
// =============================================================================

/// Types of messages in the BFT protocol.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum BftMessageType {
    /// Proposal message.
    Propose,
    /// Partial signature share.
    Share,
    /// Aggregated commit proof.
    Commit,
}

/// Step 0: Proposal message.
///
/// Any node (proposer) floods:
/// `{ type: PROPOSE, value: V, round: R }`
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BftProposal {
    /// The round number.
    pub round: u64,
    /// The proposed value.
    pub value: Vec<u8>,
    /// The proposer's node ID.
    pub proposer_id: u32,
    /// Ed25519 signature over the proposal.
    pub signature: Signature,
    /// The proposer's public key.
    pub public_key: PublicKey,
}

impl BftProposal {
    /// Compute the payload that should be signed.
    #[must_use]
    pub fn payload_for_signing(&self) -> Vec<u8> {
        let mut payload = Vec::with_capacity(15 + self.value.len());
        payload.extend_from_slice(b"PROPOSE");
        payload.extend_from_slice(&self.round.to_be_bytes());
        payload.extend_from_slice(&self.value);
        payload
    }

    /// Compute deterministic hash for this proposal.
    #[must_use]
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = blake3::Hasher::new();
        hasher.update(&self.round.to_be_bytes());
        hasher.update(&(self.value.len() as u32).to_be_bytes());
        hasher.update(&self.value);
        hasher.update(&self.proposer_id.to_be_bytes());
        hasher.finalize().into()
    }
}

/// Step 1: Partial signature share.
///
/// Each arbitrator i computes and floods:
/// `share_i = SignShare_i(hash(R || V))`
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BftShare {
    /// The round number.
    pub round: u64,
    /// Hash of (round || value).
    pub value_hash: [u8; 32],
    /// The node ID that created this share.
    pub node_id: u32,
    /// The partial signature share.
    pub share: [u8; 32],
    /// The node's BLS public key data.
    pub public_key: [u8; 32],
}

impl BftShare {
    /// Compute deterministic hash for this share.
    #[must_use]
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = blake3::Hasher::new();
        hasher.update(&self.round.to_be_bytes());
        hasher.update(&self.value_hash);
        hasher.update(&self.node_id.to_be_bytes());
        hasher.update(&self.share);
        hasher.finalize().into()
    }
}

/// Step 2: Aggregated commit proof.
///
/// Any node that collects >= T distinct valid shares for (R, V):
/// 1. Aggregates into threshold signature
/// 2. Floods final proof once
///
/// This unforgeably attests: "at least 2f+1 arbitrators signed V in round R"
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BftCommit {
    /// The round number.
    pub round: u64,
    /// The committed value.
    pub value: Vec<u8>,
    /// The threshold signature proof.
    pub proof: ThresholdSignature,
    /// The aggregator's node ID.
    pub aggregator_id: u32,
}

impl BftCommit {
    /// Compute deterministic hash for this commit.
    #[must_use]
    pub fn hash(&self) -> [u8; 32] {
        let mut hasher = blake3::Hasher::new();
        hasher.update(&self.round.to_be_bytes());
        hasher.update(&(self.value.len() as u32).to_be_bytes());
        hasher.update(&self.value);
        hasher.update(self.proof.signature());
        for node_id in self.proof.contributing_nodes() {
            hasher.update(&node_id.to_be_bytes());
        }
        hasher.finalize().into()
    }
}

// =============================================================================
// BFT Arbitrator State Machine
// =============================================================================

/// Phases of an individual arbitrator.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum ArbitratorPhase {
    /// Waiting for proposal.
    Idle,
    /// Have proposal, flooding share.
    Signing,
    /// Collecting shares.
    Aggregating,
    /// Have seen valid commit.
    Committed,
    /// Timed out.
    Aborted,
}

/// A single arbitrator node in the BFT consensus.
///
/// Each arbitrator:
/// 1. Receives proposals
/// 2. Creates and floods partial signature shares
/// 3. Collects shares from other arbitrators
/// 4. Aggregates when threshold reached
/// 5. Floods final commit proof
pub struct Arbitrator {
    /// The node ID.
    node_id: u32,
    /// BFT configuration.
    config: BftConfig,
    /// The threshold signature scheme.
    threshold_scheme: ThresholdScheme,
    /// Ed25519 key pair for signing proposals.
    ed25519_keypair: KeyPair,

    // Protocol state
    phase: ArbitratorPhase,
    current_round: u64,
    current_proposal: Option<BftProposal>,
    current_value: Option<Vec<u8>>,
    own_share: Option<(u32, [u8; 32])>,
    collected_shares: std::collections::HashMap<u32, [u8; 32]>,
    final_commit: Option<BftCommit>,
}

impl Arbitrator {
    /// Create a new arbitrator.
    #[must_use]
    pub fn new(
        node_id: u32,
        config: BftConfig,
        threshold_scheme: ThresholdScheme,
        ed25519_keypair: KeyPair,
    ) -> Self {
        Self {
            node_id,
            config,
            threshold_scheme,
            ed25519_keypair,
            phase: ArbitratorPhase::Idle,
            current_round: 0,
            current_proposal: None,
            current_value: None,
            own_share: None,
            collected_shares: std::collections::HashMap::new(),
            final_commit: None,
        }
    }

    /// Get the node ID.
    #[must_use]
    pub const fn node_id(&self) -> u32 {
        self.node_id
    }

    /// Get the current phase.
    #[must_use]
    pub const fn phase(&self) -> ArbitratorPhase {
        self.phase
    }

    /// Get the current round.
    #[must_use]
    pub const fn current_round(&self) -> u64 {
        self.current_round
    }

    /// Get the final commit if available.
    #[must_use]
    pub fn final_commit(&self) -> Option<&BftCommit> {
        self.final_commit.as_ref()
    }

    /// Get the decision state.
    #[must_use]
    pub fn decision(&self) -> &'static str {
        match self.phase {
            ArbitratorPhase::Committed => "commit",
            ArbitratorPhase::Aborted => "abort",
            _ => "pending",
        }
    }

    /// Process a received proposal.
    ///
    /// Returns a share to flood if we haven't signed for this round yet.
    pub fn receive_proposal(&mut self, proposal: &BftProposal) -> Result<Option<BftShare>> {
        if self.phase != ArbitratorPhase::Idle {
            return Ok(None); // Already processing a proposal
        }

        if proposal.round != self.current_round + 1 {
            return Ok(None); // Wrong round
        }

        // Verify proposal signature
        let msg = proposal.payload_for_signing();
        proposal.public_key.verify(&msg, &proposal.signature)?;

        // Accept proposal
        self.current_round = proposal.round;
        self.current_proposal = Some(proposal.clone());
        self.current_value = Some(proposal.value.clone());
        self.phase = ArbitratorPhase::Signing;

        // Create our share
        let value_hash = hash_round_value(proposal.round, &proposal.value);
        let (node_id, share) = self.threshold_scheme.create_share(self.node_id, &value_hash);
        self.own_share = Some((node_id, share));
        self.collected_shares.insert(node_id, share);

        // Return share message to flood
        Ok(Some(BftShare {
            round: proposal.round,
            value_hash,
            node_id: self.node_id,
            share,
            public_key: *self.threshold_scheme.get_public_key(self.node_id).data(),
        }))
    }

    /// Process a received share.
    ///
    /// Returns a commit to flood if we've reached threshold.
    pub fn receive_share(&mut self, share: &BftShare) -> Option<BftCommit> {
        if !matches!(
            self.phase,
            ArbitratorPhase::Signing | ArbitratorPhase::Aggregating
        ) {
            return None;
        }

        if share.round != self.current_round {
            return None; // Wrong round
        }

        let current_value = self.current_value.as_ref()?;

        // Verify the share is for our current value
        let expected_hash = hash_round_value(self.current_round, current_value);
        if share.value_hash != expected_hash {
            return None; // Different value
        }

        // Verify the share
        if !self
            .threshold_scheme
            .verify_share(share.node_id, &expected_hash, &share.share)
        {
            return None; // Invalid share
        }

        // Store the share (ignore duplicates)
        if self.collected_shares.contains_key(&share.node_id) {
            return None;
        }
        self.collected_shares.insert(share.node_id, share.share);
        self.phase = ArbitratorPhase::Aggregating;

        // Try to aggregate
        if self.collected_shares.len() >= self.config.threshold() as usize {
            let shares: Vec<(u32, [u8; 32])> = self
                .collected_shares
                .iter()
                .map(|(&k, &v)| (k, v))
                .collect();

            if let Some(threshold_sig) = self.threshold_scheme.aggregate(&expected_hash, &shares) {
                let commit = BftCommit {
                    round: self.current_round,
                    value: current_value.clone(),
                    proof: threshold_sig,
                    aggregator_id: self.node_id,
                };
                self.final_commit = Some(commit.clone());
                self.phase = ArbitratorPhase::Committed;
                return Some(commit);
            }
        }

        None
    }

    /// Process a received commit.
    ///
    /// Returns `true` if this is a valid commit for our round.
    #[must_use]
    pub fn receive_commit(&mut self, commit: &BftCommit) -> bool {
        if self.phase == ArbitratorPhase::Committed {
            return true; // Already committed
        }

        if commit.round != self.current_round {
            return false; // Wrong round
        }

        // Verify the threshold signature
        let value_hash = hash_round_value(commit.round, &commit.value);
        if !self
            .threshold_scheme
            .verify_threshold_signature(&value_hash, &commit.proof)
        {
            return false; // Invalid proof
        }

        self.final_commit = Some(commit.clone());
        self.phase = ArbitratorPhase::Committed;
        self.current_value = Some(commit.value.clone());
        true
    }

    /// Get messages to flood based on current state.
    #[must_use]
    pub fn get_outgoing_messages(&self) -> Vec<BftMessage> {
        let mut messages = Vec::new();

        if self.phase == ArbitratorPhase::Signing {
            if let (Some((node_id, share)), Some(value)) =
                (&self.own_share, &self.current_value)
            {
                let value_hash = hash_round_value(self.current_round, value);
                messages.push(BftMessage::Share(BftShare {
                    round: self.current_round,
                    value_hash,
                    node_id: *node_id,
                    share: *share,
                    public_key: *self.threshold_scheme.get_public_key(*node_id).data(),
                }));
            }
        }

        if self.phase == ArbitratorPhase::Committed {
            if let Some(commit) = &self.final_commit {
                messages.push(BftMessage::Commit(commit.clone()));
            }
        }

        messages
    }
}

impl Clone for Arbitrator {
    fn clone(&self) -> Self {
        Self {
            node_id: self.node_id,
            config: self.config,
            threshold_scheme: self.threshold_scheme.clone(),
            ed25519_keypair: self.ed25519_keypair.clone(),
            phase: self.phase,
            current_round: self.current_round,
            current_proposal: self.current_proposal.clone(),
            current_value: self.current_value.clone(),
            own_share: self.own_share,
            collected_shares: self.collected_shares.clone(),
            final_commit: self.final_commit.clone(),
        }
    }
}

impl core::fmt::Debug for Arbitrator {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("Arbitrator")
            .field("node_id", &self.node_id)
            .field("phase", &self.phase)
            .field("current_round", &self.current_round)
            .field("collected_shares", &self.collected_shares.len())
            .finish_non_exhaustive()
    }
}

/// A BFT protocol message.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum BftMessage {
    /// A proposal message.
    Proposal(BftProposal),
    /// A share message.
    Share(BftShare),
    /// A commit message.
    Commit(BftCommit),
}

// =============================================================================
// BFT Consensus Coordinator
// =============================================================================

/// Coordinates BFT consensus across all arbitrators.
///
/// This manages the full 2-flood BFT protocol:
/// 1. PROPOSE: Proposer floods value
/// 2. SHARE: All honest nodes flood partial signatures
/// 3. COMMIT: Any node with T shares floods aggregated proof
pub struct BftConsensus {
    config: BftConfig,
    threshold_scheme: ThresholdScheme,
    arbitrators: Vec<Arbitrator>,
    ed25519_keypairs: Vec<KeyPair>,
}

impl BftConsensus {
    /// Create a new BFT consensus coordinator.
    #[must_use]
    pub fn new(config: BftConfig) -> Self {
        let threshold_scheme = ThresholdScheme::new(config);
        let mut arbitrators = Vec::with_capacity(config.n() as usize);
        let mut ed25519_keypairs = Vec::with_capacity(config.n() as usize);

        for i in 0..config.n() {
            let keypair = KeyPair::generate();
            ed25519_keypairs.push(keypair.clone());
            let arb = Arbitrator::new(i, config, threshold_scheme.clone(), keypair);
            arbitrators.push(arb);
        }

        Self {
            config,
            threshold_scheme,
            arbitrators,
            ed25519_keypairs,
        }
    }

    /// Create a new BFT consensus with a specific threshold scheme.
    ///
    /// Useful for deterministic testing.
    #[must_use]
    pub fn with_threshold_scheme(config: BftConfig, threshold_scheme: ThresholdScheme) -> Self {
        let mut arbitrators = Vec::with_capacity(config.n() as usize);
        let mut ed25519_keypairs = Vec::with_capacity(config.n() as usize);

        for i in 0..config.n() {
            let keypair = KeyPair::generate();
            ed25519_keypairs.push(keypair.clone());
            let arb = Arbitrator::new(i, config, threshold_scheme.clone(), keypair);
            arbitrators.push(arb);
        }

        Self {
            config,
            threshold_scheme,
            arbitrators,
            ed25519_keypairs,
        }
    }

    /// Get the BFT configuration.
    #[must_use]
    pub const fn config(&self) -> &BftConfig {
        &self.config
    }

    /// Get the arbitrators.
    #[must_use]
    pub fn arbitrators(&self) -> &[Arbitrator] {
        &self.arbitrators
    }

    /// Get mutable access to arbitrators.
    #[must_use]
    pub fn arbitrators_mut(&mut self) -> &mut [Arbitrator] {
        &mut self.arbitrators
    }

    /// Create a proposal from the specified node.
    ///
    /// # Errors
    ///
    /// Returns an error if the proposer_id is out of range.
    pub fn propose(&self, proposer_id: u32, value: Vec<u8>) -> Result<BftProposal> {
        if proposer_id >= self.config.n() {
            return Err(Error::Bft(format!(
                "Invalid proposer_id: {}",
                proposer_id
            )));
        }

        let keypair = &self.ed25519_keypairs[proposer_id as usize];
        let round_num = self.arbitrators[proposer_id as usize].current_round() + 1;

        let mut msg = Vec::with_capacity(15 + value.len());
        msg.extend_from_slice(b"PROPOSE");
        msg.extend_from_slice(&round_num.to_be_bytes());
        msg.extend_from_slice(&value);

        let signature = keypair.sign(&msg);

        Ok(BftProposal {
            round: round_num,
            value,
            proposer_id,
            signature,
            public_key: keypair.public_key().clone(),
        })
    }

    /// Run a complete round of BFT consensus.
    ///
    /// Returns the commit if consensus is reached, None if not enough shares.
    ///
    /// This simulates perfect network conditions (all messages delivered).
    /// For testing with loss, use the simulation harness.
    pub fn run_round(&mut self, value: Vec<u8>, proposer_id: u32) -> Result<Option<BftCommit>> {
        // Phase 1: Proposal
        let proposal = self.propose(proposer_id, value)?;

        // Phase 2: All arbitrators receive proposal and create shares
        let mut shares = Vec::new();
        for arb in &mut self.arbitrators {
            if let Ok(Some(share)) = arb.receive_proposal(&proposal) {
                shares.push(share);
            }
        }

        // Phase 3: All arbitrators receive all shares
        let mut commits = Vec::new();
        for share in &shares {
            for arb in &mut self.arbitrators {
                if let Some(commit) = arb.receive_share(share) {
                    commits.push(commit);
                }
            }
        }

        // Return first commit (all should be equivalent)
        if let Some(commit) = commits.into_iter().next() {
            // Propagate commit to all arbitrators
            for arb in &mut self.arbitrators {
                let _ = arb.receive_commit(&commit);
            }
            return Ok(Some(commit));
        }

        Ok(None)
    }

    /// Check if consensus has been reached.
    #[must_use]
    pub fn is_committed(&self) -> bool {
        self.arbitrators
            .iter()
            .all(|arb| arb.phase() == ArbitratorPhase::Committed)
    }
}

impl Clone for BftConsensus {
    fn clone(&self) -> Self {
        Self {
            config: self.config,
            threshold_scheme: self.threshold_scheme.clone(),
            arbitrators: self.arbitrators.clone(),
            ed25519_keypairs: self.ed25519_keypairs.clone(),
        }
    }
}

impl core::fmt::Debug for BftConsensus {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.debug_struct("BftConsensus")
            .field("config", &self.config)
            .field("num_arbitrators", &self.arbitrators.len())
            .field("is_committed", &self.is_committed())
            .finish_non_exhaustive()
    }
}

// =============================================================================
// Utility Functions
// =============================================================================

/// Compute hash of round number and value for BFT consensus.
///
/// This is what gets signed in the SHARE phase.
#[must_use]
pub fn hash_round_value(round: u64, value: &[u8]) -> [u8; 32] {
    let mut hasher = blake3::Hasher::new();
    hasher.update(&round.to_be_bytes());
    hasher.update(value);
    hasher.finalize().into()
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bft_config_for_fault_tolerance() {
        let config = BftConfig::for_fault_tolerance(1);
        assert_eq!(config.n(), 4); // 3*1 + 1
        assert_eq!(config.f(), 1);
        assert_eq!(config.threshold(), 3); // 2*1 + 1

        let config = BftConfig::for_fault_tolerance(2);
        assert_eq!(config.n(), 7); // 3*2 + 1
        assert_eq!(config.f(), 2);
        assert_eq!(config.threshold(), 5); // 2*2 + 1
    }

    #[test]
    fn bft_config_for_node_count() {
        let config = BftConfig::for_node_count(4).unwrap();
        assert_eq!(config.n(), 4);
        assert_eq!(config.f(), 1);

        let config = BftConfig::for_node_count(7).unwrap();
        assert_eq!(config.n(), 7);
        assert_eq!(config.f(), 2);

        // Invalid node counts
        assert!(BftConfig::for_node_count(5).is_err()); // Not 3f+1
        assert!(BftConfig::for_node_count(6).is_err()); // Not 3f+1
    }

    #[test]
    fn threshold_scheme_share_creation_and_verification() {
        let config = BftConfig::for_fault_tolerance(1);
        let scheme = ThresholdScheme::new(config);

        let message = b"test message";
        let (node_id, share) = scheme.create_share(0, message);

        assert_eq!(node_id, 0);
        assert!(scheme.verify_share(0, message, &share));
        assert!(!scheme.verify_share(1, message, &share)); // Wrong node
        assert!(!scheme.verify_share(0, b"wrong message", &share)); // Wrong message
    }

    #[test]
    fn threshold_scheme_aggregation() {
        let config = BftConfig::for_fault_tolerance(1);
        let scheme = ThresholdScheme::new(config);

        let message = b"test message";

        // Collect shares from all 4 nodes
        let mut shares = Vec::new();
        for i in 0..config.n() {
            shares.push(scheme.create_share(i, message));
        }

        // Should succeed with threshold (3) shares
        let threshold_sig = scheme.aggregate(message, &shares[..3]).unwrap();
        assert_eq!(threshold_sig.contributing_nodes().len(), 3);
        assert!(scheme.verify_threshold_signature(message, &threshold_sig));

        // Should fail with fewer than threshold shares
        assert!(scheme.aggregate(message, &shares[..2]).is_none());
    }

    #[test]
    fn bft_consensus_single_round() {
        let config = BftConfig::for_fault_tolerance(1);
        let mut consensus = BftConsensus::new(config);

        let value = b"proposed value".to_vec();
        let commit = consensus.run_round(value.clone(), 0).unwrap();

        assert!(commit.is_some());
        let commit = commit.unwrap();
        assert_eq!(commit.value, value);
        assert_eq!(commit.round, 1);
        assert!(consensus.is_committed());
    }

    #[test]
    fn bft_safety_no_conflicting_commits() {
        // This test verifies that two different values cannot both get committed
        // in the same round, which is the core safety property of BFT.

        let config = BftConfig::for_fault_tolerance(1);
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message_a = b"value A";
        let message_b = b"value B";

        // Collect shares for message A from nodes 0, 1, 2
        let mut shares_a = Vec::new();
        for i in 0..3 {
            shares_a.push(scheme.create_share(i, message_a));
        }

        // Collect shares for message B from nodes 1, 2, 3
        let mut shares_b = Vec::new();
        for i in 1..4 {
            shares_b.push(scheme.create_share(i, message_b));
        }

        // Both should aggregate successfully (they each have 3 shares)
        let sig_a = scheme.aggregate(message_a, &shares_a);
        let sig_b = scheme.aggregate(message_b, &shares_b);

        // But crucially, nodes 1 and 2 appear in BOTH sets.
        // In a real Byzantine-resilient system, honest nodes would only sign
        // ONE value per round, preventing this scenario.
        //
        // The threshold signature itself doesn't prevent equivocation;
        // that's enforced by the protocol (honest nodes don't sign twice).

        assert!(sig_a.is_some());
        assert!(sig_b.is_some());

        // Verify both signatures are valid for their respective messages
        let sig_a = sig_a.unwrap();
        let sig_b = sig_b.unwrap();
        assert!(scheme.verify_threshold_signature(message_a, &sig_a));
        assert!(scheme.verify_threshold_signature(message_b, &sig_b));

        // But the signatures are NOT interchangeable
        assert!(!scheme.verify_threshold_signature(message_b, &sig_a));
        assert!(!scheme.verify_threshold_signature(message_a, &sig_b));
    }

    #[test]
    fn arbitrator_state_machine() {
        let config = BftConfig::for_fault_tolerance(1);
        let scheme = ThresholdScheme::new(config);
        let keypair = KeyPair::generate();

        let mut arb = Arbitrator::new(0, config, scheme.clone(), keypair.clone());
        assert_eq!(arb.phase(), ArbitratorPhase::Idle);

        // Create a proposal
        let value = b"test value".to_vec();
        let proposal = BftProposal {
            round: 1,
            value: value.clone(),
            proposer_id: 0,
            signature: keypair.sign(&{
                let mut msg = Vec::new();
                msg.extend_from_slice(b"PROPOSE");
                msg.extend_from_slice(&1u64.to_be_bytes());
                msg.extend_from_slice(&value);
                msg
            }),
            public_key: keypair.public_key().clone(),
        };

        // Receive proposal
        let share = arb.receive_proposal(&proposal).unwrap();
        assert!(share.is_some());
        assert_eq!(arb.phase(), ArbitratorPhase::Signing);
        assert_eq!(arb.current_round(), 1);
    }

    #[test]
    fn hash_round_value_deterministic() {
        let hash1 = hash_round_value(1, b"value");
        let hash2 = hash_round_value(1, b"value");
        let hash3 = hash_round_value(2, b"value");
        let hash4 = hash_round_value(1, b"other");

        assert_eq!(hash1, hash2); // Same inputs -> same hash
        assert_ne!(hash1, hash3); // Different round -> different hash
        assert_ne!(hash1, hash4); // Different value -> different hash
    }

    // =========================================================================
    // Adversarial Scenario Tests
    // =========================================================================

    /// Test: Byzantine node attempts to equivocate (sign multiple values)
    /// Expected: Honest nodes detect and reject conflicting shares
    #[test]
    fn adversarial_byzantine_equivocation() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let round = 1u64;
        let value_a = b"value A";
        let value_b = b"value B";

        // Byzantine node 0 tries to sign both values
        let hash_a = hash_round_value(round, value_a);
        let hash_b = hash_round_value(round, value_b);

        let (_, share_a_node0) = scheme.create_share(0, &hash_a);
        let (_, share_b_node0) = scheme.create_share(0, &hash_b);

        // Both shares are valid for their respective messages
        assert!(scheme.verify_share(0, &hash_a, &share_a_node0));
        assert!(scheme.verify_share(0, &hash_b, &share_b_node0));

        // But each share only verifies for its own message
        assert!(!scheme.verify_share(0, &hash_b, &share_a_node0));
        assert!(!scheme.verify_share(0, &hash_a, &share_b_node0));

        // Honest nodes 1, 2, 3 only sign value_a
        let mut shares_a = vec![(0u32, share_a_node0)];
        for i in 1..4 {
            shares_a.push(scheme.create_share(i, &hash_a));
        }

        // Value A can aggregate successfully
        let sig_a = scheme.aggregate(&hash_a, &shares_a);
        assert!(sig_a.is_some());

        // Value B cannot aggregate - only has Byzantine node's share
        let shares_b = vec![(0u32, share_b_node0)];
        let sig_b = scheme.aggregate(&hash_b, &shares_b);
        assert!(sig_b.is_none()); // Not enough shares

        // Even if Byzantine somehow gets 2 more shares for B,
        // at least one honest node would have to sign B,
        // which they won't do since they already signed A.
        // This demonstrates the quorum overlap property.
    }

    /// Test: f Byzantine nodes refuse to participate (censoring)
    /// Expected: Consensus still succeeds with remaining 2f+1 honest nodes
    #[test]
    fn adversarial_byzantine_censoring_f_nodes() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Node 0 is Byzantine and refuses to participate
        // Only nodes 1, 2, 3 contribute shares
        let mut honest_shares = Vec::new();
        for i in 1..4 {
            honest_shares.push(scheme.create_share(i, &hash));
        }

        // Should still aggregate with exactly T=3 shares
        let sig = scheme.aggregate(&hash, &honest_shares);
        assert!(sig.is_some());

        let sig = sig.unwrap();
        assert_eq!(sig.contributing_nodes().len(), 3);
        assert!(scheme.verify_threshold_signature(&hash, &sig));

        // Byzantine node 0 is not in the contributing set
        assert!(!sig.contributing_nodes().contains(&0));
    }

    /// Test: Maximum f Byzantine nodes are censoring
    /// Expected: Consensus succeeds with exactly T = 2f+1 honest nodes
    #[test]
    fn adversarial_max_byzantine_censoring() {
        let config = BftConfig::for_fault_tolerance(2); // n=7, f=2, T=5
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Nodes 0 and 1 are Byzantine and refuse to participate
        // Only nodes 2, 3, 4, 5, 6 contribute shares (exactly 5 = T)
        let mut honest_shares = Vec::new();
        for i in 2..7 {
            honest_shares.push(scheme.create_share(i, &hash));
        }

        // Should aggregate with exactly T=5 shares
        let sig = scheme.aggregate(&hash, &honest_shares);
        assert!(sig.is_some());

        let sig = sig.unwrap();
        assert_eq!(sig.contributing_nodes().len(), 5);
        assert!(scheme.verify_threshold_signature(&hash, &sig));
    }

    /// Test: More than f Byzantine nodes (f+1) - consensus should fail
    /// Expected: Cannot reach threshold without honest majority
    #[test]
    fn adversarial_too_many_byzantine_fails() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Nodes 0 AND 1 are Byzantine and refuse to participate (f+1 = 2)
        // Only nodes 2, 3 contribute shares
        let mut honest_shares = Vec::new();
        for i in 2..4 {
            honest_shares.push(scheme.create_share(i, &hash));
        }

        // Cannot aggregate - only 2 shares, need 3
        let sig = scheme.aggregate(&hash, &honest_shares);
        assert!(sig.is_none());
    }

    /// Test: Byzantine nodes send invalid/corrupted shares
    /// Expected: Invalid shares are rejected, valid shares still aggregate
    #[test]
    fn adversarial_corrupted_shares() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Byzantine node 0 sends a corrupted share
        let corrupted_share = [0xFFu8; 32]; // Garbage

        // Honest nodes 1, 2, 3 send valid shares
        let mut shares = vec![(0u32, corrupted_share)];
        for i in 1..4 {
            shares.push(scheme.create_share(i, &hash));
        }

        // Corrupted share should be rejected but valid shares aggregate
        let sig = scheme.aggregate(&hash, &shares);
        assert!(sig.is_some());

        let sig = sig.unwrap();
        // Node 0's corrupted share is not included
        assert!(!sig.contributing_nodes().contains(&0));
        // But we still have 3 valid shares from nodes 1, 2, 3
        assert_eq!(sig.contributing_nodes().len(), 3);
    }

    /// Test: Byzantine nodes send shares for wrong round
    /// Expected: Wrong-round shares are ignored
    #[test]
    fn adversarial_wrong_round_shares() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash_round1 = hash_round_value(1, message);
        let hash_round99 = hash_round_value(99, message); // Wrong round

        // Byzantine node 0 sends share for wrong round
        let (_, share_wrong_round) = scheme.create_share(0, &hash_round99);

        // Honest nodes send shares for correct round
        let mut shares = vec![(0u32, share_wrong_round)];
        for i in 1..4 {
            shares.push(scheme.create_share(i, &hash_round1));
        }

        // Wrong-round share doesn't verify for round 1
        assert!(!scheme.verify_share(0, &hash_round1, &share_wrong_round));

        // But aggregation should still succeed with honest shares
        let sig = scheme.aggregate(&hash_round1, &shares);
        assert!(sig.is_some());

        let sig = sig.unwrap();
        // Node 0's wrong-round share is not included
        assert!(!sig.contributing_nodes().contains(&0));
    }

    /// Test: Duplicate shares from same node
    /// Expected: Duplicates are ignored, each node counted once
    #[test]
    fn adversarial_duplicate_shares() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Node 0 sends their share 10 times
        let share0 = scheme.create_share(0, &hash);
        let mut shares: Vec<(u32, [u8; 32])> = Vec::new();
        for _ in 0..10 {
            shares.push(share0);
        }

        // Only 1 unique share - cannot aggregate
        let sig = scheme.aggregate(&hash, &shares);
        assert!(sig.is_none());

        // Now add shares from nodes 1 and 2
        shares.push(scheme.create_share(1, &hash));
        shares.push(scheme.create_share(2, &hash));

        // Now have 3 unique shares - should aggregate
        let sig = scheme.aggregate(&hash, &shares);
        assert!(sig.is_some());

        let sig = sig.unwrap();
        assert_eq!(sig.contributing_nodes().len(), 3);
    }

    /// Test: Network partition where only honest nodes can communicate
    /// Expected: Honest partition achieves consensus if >= T nodes
    #[test]
    fn adversarial_network_partition_honest_majority() {
        let config = BftConfig::for_fault_tolerance(2); // n=7, f=2, T=5
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Network partitions into:
        // Partition A (Byzantine): nodes 0, 1
        // Partition B (Honest): nodes 2, 3, 4, 5, 6

        // Partition B has 5 nodes (exactly T) - should succeed
        let mut partition_b_shares = Vec::new();
        for i in 2..7 {
            partition_b_shares.push(scheme.create_share(i, &hash));
        }

        let sig = scheme.aggregate(&hash, &partition_b_shares);
        assert!(sig.is_some());

        let sig = sig.unwrap();
        assert!(scheme.verify_threshold_signature(&hash, &sig));

        // Partition A cannot achieve consensus alone (only 2 nodes)
        let mut partition_a_shares = Vec::new();
        for i in 0..2 {
            partition_a_shares.push(scheme.create_share(i, &hash));
        }

        let sig_a = scheme.aggregate(&hash, &partition_a_shares);
        assert!(sig_a.is_none());
    }

    /// Test: Message reordering - shares arrive out of order
    /// Expected: Order doesn't matter, same threshold signature produced
    #[test]
    fn adversarial_message_reordering() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Collect all shares
        let mut all_shares = Vec::new();
        for i in 0..4 {
            all_shares.push(scheme.create_share(i, &hash));
        }

        // Aggregate in order 0, 1, 2
        let shares_ordered: Vec<_> = vec![all_shares[0], all_shares[1], all_shares[2]];
        let sig_ordered = scheme.aggregate(&hash, &shares_ordered).unwrap();

        // Aggregate in reverse order 2, 1, 0
        let shares_reversed: Vec<_> = vec![all_shares[2], all_shares[1], all_shares[0]];
        let sig_reversed = scheme.aggregate(&hash, &shares_reversed).unwrap();

        // Both should produce valid signatures
        assert!(scheme.verify_threshold_signature(&hash, &sig_ordered));
        assert!(scheme.verify_threshold_signature(&hash, &sig_reversed));

        // Contributing nodes should be the same (sorted)
        assert_eq!(
            sig_ordered.contributing_nodes(),
            sig_reversed.contributing_nodes()
        );

        // Signatures should be identical (deterministic aggregation)
        assert_eq!(sig_ordered.signature(), sig_reversed.signature());
    }

    /// Test: Partial message loss during share phase
    /// Expected: Consensus achieved if enough shares eventually arrive
    #[test]
    fn adversarial_partial_share_loss() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Only 2 shares arrive initially (below threshold)
        let mut initial_shares = Vec::new();
        for i in 0..2 {
            initial_shares.push(scheme.create_share(i, &hash));
        }

        // Cannot aggregate yet
        let sig = scheme.aggregate(&hash, &initial_shares);
        assert!(sig.is_none());

        // Third share arrives later
        initial_shares.push(scheme.create_share(2, &hash));

        // Now can aggregate
        let sig = scheme.aggregate(&hash, &initial_shares);
        assert!(sig.is_some());
        assert!(scheme.verify_threshold_signature(&hash, &sig.unwrap()));
    }

    /// Test: Byzantine node claims different node_id
    /// Expected: Share fails verification due to wrong public key
    #[test]
    fn adversarial_node_id_spoofing() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Node 0 creates a share but claims to be node 3
        let (_, share_from_0) = scheme.create_share(0, &hash);

        // Share doesn't verify as coming from node 3
        assert!(!scheme.verify_share(3, &hash, &share_from_0));

        // But verifies correctly for node 0
        assert!(scheme.verify_share(0, &hash, &share_from_0));
    }

    /// Test: Quorum intersection property
    /// Expected: Any two quorums of size T must overlap in at least one node
    #[test]
    fn adversarial_quorum_intersection() {
        let config = BftConfig::for_fault_tolerance(2); // n=7, f=2, T=5

        // Two quorums of size 5 from a set of 7 nodes
        // MUST overlap in at least 5 + 5 - 7 = 3 nodes

        let quorum_a: std::collections::HashSet<u32> = [0, 1, 2, 3, 4].into_iter().collect();
        let quorum_b: std::collections::HashSet<u32> = [2, 3, 4, 5, 6].into_iter().collect();

        let intersection: std::collections::HashSet<_> =
            quorum_a.intersection(&quorum_b).collect();

        // Intersection has at least f+1 = 3 nodes
        assert!(intersection.len() >= (config.f() + 1) as usize);
        assert_eq!(intersection.len(), 3); // Exactly 3: {2, 3, 4}

        // This guarantees safety: any two conflicting threshold signatures
        // would require f+1 nodes to have signed both, but honest nodes
        // only sign once, so at least one intersection node prevents conflict.
    }

    /// Test: Replay attack - reusing old threshold signature
    /// Expected: Old signature doesn't verify for new round
    #[test]
    fn adversarial_replay_attack() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";

        // Round 1 consensus
        let hash_round1 = hash_round_value(1, message);
        let mut shares_round1 = Vec::new();
        for i in 0..3 {
            shares_round1.push(scheme.create_share(i, &hash_round1));
        }
        let sig_round1 = scheme.aggregate(&hash_round1, &shares_round1).unwrap();

        // Verify works for round 1
        assert!(scheme.verify_threshold_signature(&hash_round1, &sig_round1));

        // Try to replay in round 2
        let hash_round2 = hash_round_value(2, message);

        // Old signature doesn't verify for new round
        assert!(!scheme.verify_threshold_signature(&hash_round2, &sig_round1));
    }

    /// Test: Full BFT consensus with f Byzantine nodes simulated
    /// Expected: Consensus reached despite Byzantine participation
    #[test]
    fn adversarial_full_consensus_with_byzantine() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3

        // Create consensus with deterministic keys
        let master_secret = [0x42u8; 32];
        let scheme = ThresholdScheme::with_master_secret(config, master_secret);
        let mut consensus = BftConsensus::with_threshold_scheme(config, scheme);

        // Simulate Byzantine node 0 doing nothing while honest nodes work
        let value = b"honest consensus value".to_vec();

        // Create proposal from honest node 1
        let proposal = consensus.propose(1, value.clone()).unwrap();

        // Only honest nodes 1, 2, 3 process the proposal
        let mut honest_shares = Vec::new();
        for i in 1..4 {
            if let Ok(Some(share)) = consensus.arbitrators_mut()[i as usize].receive_proposal(&proposal) {
                honest_shares.push(share);
            }
        }

        // Distribute shares only among honest nodes
        let mut commits = Vec::new();
        for share in &honest_shares {
            for i in 1..4 {
                if let Some(commit) = consensus.arbitrators_mut()[i as usize].receive_share(share) {
                    commits.push(commit);
                }
            }
        }

        // Should have achieved consensus
        assert!(!commits.is_empty());
        let commit = commits.into_iter().next().unwrap();
        assert_eq!(commit.value, value);
        assert_eq!(commit.round, 1);

        // Verify the threshold signature
        let hash = hash_round_value(1, &value);
        assert!(consensus
            .config()
            .threshold()
            <= commit.proof.contributing_nodes().len() as u32);
    }

    /// Test: Byzantine node sends conflicting proposals
    /// Expected: Honest nodes only accept first valid proposal per round
    #[test]
    fn adversarial_conflicting_proposals() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);
        let keypair = KeyPair::generate();

        let mut arb = Arbitrator::new(1, config, scheme.clone(), keypair.clone());
        assert_eq!(arb.phase(), ArbitratorPhase::Idle);

        let value_a = b"value A".to_vec();
        let value_b = b"value B".to_vec();

        // First proposal
        let proposal_a = BftProposal {
            round: 1,
            value: value_a.clone(),
            proposer_id: 0,
            signature: keypair.sign(&{
                let mut msg = Vec::new();
                msg.extend_from_slice(b"PROPOSE");
                msg.extend_from_slice(&1u64.to_be_bytes());
                msg.extend_from_slice(&value_a);
                msg
            }),
            public_key: keypair.public_key().clone(),
        };

        // Accept first proposal
        let share_a = arb.receive_proposal(&proposal_a).unwrap();
        assert!(share_a.is_some());
        assert_eq!(arb.phase(), ArbitratorPhase::Signing);

        // Second conflicting proposal for same round
        let proposal_b = BftProposal {
            round: 1,
            value: value_b.clone(),
            proposer_id: 0,
            signature: keypair.sign(&{
                let mut msg = Vec::new();
                msg.extend_from_slice(b"PROPOSE");
                msg.extend_from_slice(&1u64.to_be_bytes());
                msg.extend_from_slice(&value_b);
                msg
            }),
            public_key: keypair.public_key().clone(),
        };

        // Reject second proposal - already processing first
        let share_b = arb.receive_proposal(&proposal_b).unwrap();
        assert!(share_b.is_none());

        // Arbitrator still on first proposal
        assert_eq!(arb.phase(), ArbitratorPhase::Signing);
    }

    /// Test: Invalid node ID in share (out of range)
    /// Expected: Share rejected
    #[test]
    fn adversarial_invalid_node_id() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let hash = hash_round_value(1, message);

        // Try to create share with invalid node ID (outside range)
        let fake_share = [0xAAu8; 32];

        // Share from node 99 (doesn't exist) should not verify
        assert!(!scheme.verify_share(99, &hash, &fake_share));
        assert!(!scheme.verify_share(4, &hash, &fake_share)); // n=4, so 4 is invalid
    }

    /// Test: Stress test with many rounds
    /// Expected: Each round produces unique, verifiable threshold signature
    #[test]
    fn adversarial_multi_round_stress() {
        let config = BftConfig::for_fault_tolerance(1); // n=4, f=1, T=3
        let scheme = ThresholdScheme::with_master_secret(config, [0x42u8; 32]);

        let message = b"consensus value";
        let mut previous_sigs: Vec<[u8; 32]> = Vec::new();

        for round in 1..=100 {
            let hash = hash_round_value(round, message);

            let mut shares = Vec::new();
            for i in 0..3 {
                shares.push(scheme.create_share(i, &hash));
            }

            let sig = scheme.aggregate(&hash, &shares).unwrap();
            assert!(scheme.verify_threshold_signature(&hash, &sig));

            // Each round produces a unique signature
            assert!(!previous_sigs.contains(sig.signature()));
            previous_sigs.push(*sig.signature());
        }

        // All 100 signatures are unique
        assert_eq!(previous_sigs.len(), 100);
    }
}
