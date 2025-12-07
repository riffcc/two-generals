"""
Byzantine Fault Tolerant (BFT) Multiparty Extension for TGP.

This module extends the Two Generals Protocol to N-party consensus with
Byzantine fault tolerance, achieving BFT in two flooding steps.

System Parameters:
- Total nodes (arbitrators) = 3f + 1
- Fault tolerance = f Byzantine
- Threshold T = 2f + 1

Protocol Overview:
1. PROPOSE: Any node floods a proposal { type: PROPOSE, value: V, round: R }
2. SHARE: Each arbitrator creates and floods a partial signature share
3. COMMIT: Any node with >= T shares aggregates into threshold signature

WHY THIS ACHIEVES BFT:
- Safety: Any valid COMMIT requires >= 2f+1 shares. Two different values would
  require 4f+2 shares, but only 3f+1 nodes exist. IMPOSSIBLE.
- Liveness: 2f+1 honest nodes will eventually flood SHAREs. Some aggregator
  will collect enough and broadcast COMMIT.
- No View-Change: Any honest node can aggregate. No leader rotation needed.

The same structural insight that solves Two Generals extends to N-party:
Self-certifying artifacts via proof stapling. The artifact IS the proof.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from .crypto import KeyPair, PublicKey


# =============================================================================
# BFT System Parameters
# =============================================================================


@dataclass(frozen=True)
class BftConfig:
    """Configuration for BFT consensus.

    The number of nodes must be exactly 3f + 1 for optimal Byzantine
    fault tolerance, where f is the maximum number of Byzantine faults.
    """
    n: int  # Total nodes = 3f + 1
    f: int  # Maximum Byzantine faults

    def __post_init__(self) -> None:
        if self.n != 3 * self.f + 1:
            raise ValueError(f"n must be 3f+1: n={self.n}, f={self.f}, expected n={3*self.f+1}")
        if self.f < 0:
            raise ValueError(f"f must be non-negative: f={self.f}")

    @property
    def threshold(self) -> int:
        """Threshold T = 2f + 1 for quorum."""
        return 2 * self.f + 1

    @classmethod
    def for_fault_tolerance(cls, f: int) -> BftConfig:
        """Create config for given fault tolerance."""
        return cls(n=3*f+1, f=f)

    @classmethod
    def for_node_count(cls, n: int) -> BftConfig:
        """Create config for given node count (must be 3f+1 for some f >= 0)."""
        if n < 1:
            raise ValueError(f"n must be positive: n={n}")
        # n = 3f + 1  =>  f = (n-1)/3
        f, remainder = divmod(n - 1, 3)
        if remainder != 0:
            raise ValueError(f"n must be 3f+1 for some integer f: n={n}")
        return cls(n=n, f=f)


# =============================================================================
# BLS-like Threshold Signatures (Simplified Implementation)
# =============================================================================
#
# For production, use 'blst' or 'py_ecc' for real BLS signatures.
# This implementation provides the API and semantics for testing.


@dataclass(frozen=True)
class BlsPublicKey:
    """BLS public key for a single node in the threshold scheme."""
    data: bytes
    node_id: int

    def __repr__(self) -> str:
        return f"BlsPublicKey(node={self.node_id}, {self.data[:4].hex()}...)"


@dataclass
class BlsKeyPair:
    """BLS key pair for a single node in the threshold scheme."""
    _private_share: bytes
    public_key: BlsPublicKey
    node_id: int

    def __init__(self, node_id: int, private_share: Optional[bytes] = None):
        self.node_id = node_id
        if private_share is None:
            private_share = secrets.token_bytes(32)
        self._private_share = private_share

        # Derive public key (simplified, not real BLS curve operations)
        pub_bytes = hashlib.sha256(
            private_share + b"BLS_PUB" + node_id.to_bytes(4, 'big')
        ).digest()
        self.public_key = BlsPublicKey(pub_bytes, node_id)

    def sign_share(self, message: bytes) -> bytes:
        """Create a partial signature share over a message.

        In real BLS, this would be a pairing-based curve operation.
        """
        import hmac
        share = hmac.new(
            self._private_share,
            message + self.node_id.to_bytes(4, 'big'),
            hashlib.sha256
        ).digest()
        return share


@dataclass(frozen=True)
class ThresholdSignature:
    """Aggregated threshold signature from T partial shares.

    This proves that at least T nodes signed the same message.
    Safety guarantee: Since T = 2f+1 and n = 3f+1, any two sets of T nodes
    must overlap in at least one honest node, preventing conflicting commits.
    """
    signature: bytes
    contributing_nodes: tuple[int, ...]
    threshold: int

    def __repr__(self) -> str:
        return f"ThresholdSignature(nodes={self.contributing_nodes}, t={self.threshold})"


@dataclass
class ThresholdScheme:
    """BLS-style threshold signature scheme for BFT consensus.

    This manages key generation and distribution (in production, use DKG),
    share creation, verification, and aggregation.
    """
    config: BftConfig
    _key_pairs: dict[int, BlsKeyPair] = field(default_factory=dict)
    _public_keys: dict[int, BlsPublicKey] = field(default_factory=dict)
    _master_secret: bytes = field(default_factory=lambda: secrets.token_bytes(32))

    def __post_init__(self) -> None:
        # Generate key pairs for all nodes (in production, use DKG)
        for node_id in range(self.config.n):
            private_share = hashlib.sha256(
                self._master_secret + node_id.to_bytes(4, 'big') + b"SHARE"
            ).digest()
            kp = BlsKeyPair(node_id, private_share)
            self._key_pairs[node_id] = kp
            self._public_keys[node_id] = kp.public_key

    def get_key_pair(self, node_id: int) -> BlsKeyPair:
        """Get the key pair for a specific node."""
        if node_id not in self._key_pairs:
            raise ValueError(f"Invalid node_id: {node_id}")
        return self._key_pairs[node_id]

    def get_public_key(self, node_id: int) -> BlsPublicKey:
        """Get the public key for a specific node."""
        if node_id not in self._public_keys:
            raise ValueError(f"Invalid node_id: {node_id}")
        return self._public_keys[node_id]

    def create_share(self, node_id: int, message: bytes) -> tuple[int, bytes]:
        """Create a signature share for a message."""
        kp = self.get_key_pair(node_id)
        share = kp.sign_share(message)
        return node_id, share

    def verify_share(self, node_id: int, message: bytes, share: bytes) -> bool:
        """Verify a signature share from a specific node."""
        kp = self._key_pairs.get(node_id)
        if kp is None:
            return False
        expected_share = kp.sign_share(message)
        return share == expected_share

    def aggregate(
        self,
        message: bytes,
        shares: list[tuple[int, bytes]]
    ) -> Optional[ThresholdSignature]:
        """Aggregate signature shares into a threshold signature.

        Args:
            message: The message that was signed
            shares: List of (node_id, share) tuples

        Returns:
            ThresholdSignature if enough valid shares, None otherwise.

        Safety guarantee: Can only succeed if at least T distinct nodes
        contributed valid shares. Since T = 2f+1 and n = 3f+1, any two
        sets of T nodes overlap in at least one honest node. Therefore,
        no conflicting values can both achieve threshold signatures.
        """
        if len(shares) < self.config.threshold:
            return None

        # Verify all shares and collect valid ones
        valid_nodes: list[int] = []
        valid_shares: list[bytes] = []
        seen_nodes: set[int] = set()

        for node_id, share in shares:
            if node_id in seen_nodes:
                continue  # Skip duplicates
            if self.verify_share(node_id, message, share):
                valid_nodes.append(node_id)
                valid_shares.append(share)
                seen_nodes.add(node_id)

        if len(valid_nodes) < self.config.threshold:
            return None

        # Take exactly T shares for deterministic aggregation
        valid_nodes = valid_nodes[:self.config.threshold]
        valid_shares = valid_shares[:self.config.threshold]

        # Aggregate shares (simplified: XOR + hash)
        # Real BLS would use pairing multiplication
        aggregated = bytes(32)
        for share in valid_shares:
            aggregated = bytes(a ^ b for a, b in zip(aggregated, share))
        final_sig = hashlib.sha256(aggregated + message).digest()

        return ThresholdSignature(
            signature=final_sig,
            contributing_nodes=tuple(sorted(valid_nodes)),
            threshold=self.config.threshold
        )

    def verify_threshold_signature(
        self,
        message: bytes,
        sig: ThresholdSignature
    ) -> bool:
        """Verify an aggregated threshold signature."""
        if len(sig.contributing_nodes) < self.config.threshold:
            return False

        # Recompute the aggregation
        shares = []
        for node_id in sig.contributing_nodes[:self.config.threshold]:
            kp = self._key_pairs.get(node_id)
            if kp is None:
                return False
            shares.append(kp.sign_share(message))

        aggregated = bytes(32)
        for share in shares:
            aggregated = bytes(a ^ b for a, b in zip(aggregated, share))
        expected_sig = hashlib.sha256(aggregated + message).digest()

        return sig.signature == expected_sig


# =============================================================================
# BFT Protocol Messages
# =============================================================================


class BftMessageType(Enum):
    """Types of messages in the BFT protocol."""
    PROPOSE = auto()
    SHARE = auto()
    COMMIT = auto()


@dataclass(frozen=True)
class BftProposal:
    """Step 0: Proposal message.

    Any node (proposer) floods:
    { type: PROPOSE, value: V, round: R }
    """
    round: int
    value: bytes
    proposer_id: int
    signature: bytes
    public_key: bytes

    def hash(self) -> bytes:
        """Compute deterministic hash for signing."""
        h = hashlib.sha256()
        h.update(struct.pack('>Q', self.round))
        h.update(struct.pack('>I', len(self.value)))
        h.update(self.value)
        h.update(struct.pack('>I', self.proposer_id))
        return h.digest()

    def payload_for_signing(self) -> bytes:
        """Get the payload that should be signed."""
        return b"PROPOSE" + struct.pack('>Q', self.round) + self.value


@dataclass(frozen=True)
class BftShare:
    """Step 1: Partial signature share.

    Each arbitrator i computes and floods:
    share_i = SignShare_i(hash(R || V))
    """
    round: int
    value_hash: bytes  # hash(R || V)
    node_id: int
    share: bytes
    public_key: bytes

    def hash(self) -> bytes:
        """Compute deterministic hash for this share."""
        h = hashlib.sha256()
        h.update(struct.pack('>Q', self.round))
        h.update(self.value_hash)
        h.update(struct.pack('>I', self.node_id))
        h.update(self.share)
        return h.digest()


@dataclass(frozen=True)
class BftCommit:
    """Step 2: Aggregated commit proof.

    Any node that collects >= T distinct valid shares for (R, V):
    1. Aggregates into threshold signature
    2. Floods final proof once

    This unforgeably attests: "at least 2f+1 arbitrators signed V in round R"
    """
    round: int
    value: bytes
    proof: ThresholdSignature
    aggregator_id: int

    def hash(self) -> bytes:
        """Compute deterministic hash for this commit."""
        h = hashlib.sha256()
        h.update(struct.pack('>Q', self.round))
        h.update(struct.pack('>I', len(self.value)))
        h.update(self.value)
        h.update(self.proof.signature)
        for node_id in self.proof.contributing_nodes:
            h.update(struct.pack('>I', node_id))
        return h.digest()


# =============================================================================
# BFT Arbitrator State Machine
# =============================================================================


class ArbitratorPhase(Enum):
    """Phases of an individual arbitrator."""
    IDLE = auto()           # Waiting for proposal
    SIGNING = auto()        # Have proposal, flooding share
    AGGREGATING = auto()    # Collecting shares
    COMMITTED = auto()      # Have seen valid commit
    ABORTED = auto()        # Timed out


@dataclass
class Arbitrator:
    """A single arbitrator node in the BFT consensus.

    Each arbitrator:
    1. Receives proposals
    2. Creates and floods partial signature shares
    3. Collects shares from other arbitrators
    4. Aggregates when threshold reached
    5. Floods final commit proof
    """
    node_id: int
    config: BftConfig
    threshold_scheme: ThresholdScheme
    ed25519_keypair: KeyPair

    # Protocol state
    phase: ArbitratorPhase = ArbitratorPhase.IDLE
    current_round: int = 0
    current_proposal: Optional[BftProposal] = None
    current_value: Optional[bytes] = None
    own_share: Optional[tuple[int, bytes]] = None
    collected_shares: dict[int, bytes] = field(default_factory=dict)
    final_commit: Optional[BftCommit] = None

    def receive_proposal(self, proposal: BftProposal) -> Optional[BftShare]:
        """Process a received proposal.

        Returns a share to flood if we haven't signed for this round yet.
        """
        if self.phase != ArbitratorPhase.IDLE:
            return None  # Already processing a proposal

        if proposal.round != self.current_round + 1:
            return None  # Wrong round

        # Verify proposal signature
        msg = proposal.payload_for_signing()
        pub = PublicKey.from_bytes(proposal.public_key)
        if not pub.verify(msg, proposal.signature):
            return None  # Invalid signature

        # Accept proposal
        self.current_round = proposal.round
        self.current_proposal = proposal
        self.current_value = proposal.value
        self.phase = ArbitratorPhase.SIGNING

        # Create our share
        value_hash = hash_round_value(proposal.round, proposal.value)
        node_id, share = self.threshold_scheme.create_share(self.node_id, value_hash)
        self.own_share = (node_id, share)
        self.collected_shares[node_id] = share

        # Return share message to flood
        return BftShare(
            round=proposal.round,
            value_hash=value_hash,
            node_id=self.node_id,
            share=share,
            public_key=self.threshold_scheme.get_public_key(self.node_id).data
        )

    def receive_share(self, share: BftShare) -> Optional[BftCommit]:
        """Process a received share.

        Returns a commit to flood if we've reached threshold.
        """
        if self.phase not in (ArbitratorPhase.SIGNING, ArbitratorPhase.AGGREGATING):
            return None

        if share.round != self.current_round:
            return None  # Wrong round

        if self.current_value is None:
            return None  # No value to compare

        # Verify the share is for our current value
        expected_hash = hash_round_value(self.current_round, self.current_value)
        if share.value_hash != expected_hash:
            return None  # Different value

        # Verify the share
        if not self.threshold_scheme.verify_share(share.node_id, expected_hash, share.share):
            return None  # Invalid share

        # Store the share (ignore duplicates)
        if share.node_id in self.collected_shares:
            return None
        self.collected_shares[share.node_id] = share.share
        self.phase = ArbitratorPhase.AGGREGATING

        # Try to aggregate
        if len(self.collected_shares) >= self.config.threshold:
            shares = list(self.collected_shares.items())
            threshold_sig = self.threshold_scheme.aggregate(expected_hash, shares)

            if threshold_sig is not None:
                commit = BftCommit(
                    round=self.current_round,
                    value=self.current_value,
                    proof=threshold_sig,
                    aggregator_id=self.node_id
                )
                self.final_commit = commit
                self.phase = ArbitratorPhase.COMMITTED
                return commit

        return None

    def receive_commit(self, commit: BftCommit) -> bool:
        """Process a received commit.

        Returns True if this is a valid commit for our round.
        """
        if self.phase == ArbitratorPhase.COMMITTED:
            return True  # Already committed

        if commit.round != self.current_round:
            return False  # Wrong round

        # Verify the threshold signature
        value_hash = hash_round_value(commit.round, commit.value)
        if not self.threshold_scheme.verify_threshold_signature(value_hash, commit.proof):
            return False  # Invalid proof

        self.final_commit = commit
        self.phase = ArbitratorPhase.COMMITTED
        self.current_value = commit.value
        return True

    def get_outgoing_messages(self) -> list[BftProposal | BftShare | BftCommit]:
        """Get messages to flood based on current state."""
        messages = []

        if self.phase == ArbitratorPhase.SIGNING and self.own_share is not None:
            value_hash = hash_round_value(self.current_round, self.current_value)
            messages.append(BftShare(
                round=self.current_round,
                value_hash=value_hash,
                node_id=self.node_id,
                share=self.own_share[1],
                public_key=self.threshold_scheme.get_public_key(self.node_id).data
            ))

        if self.phase == ArbitratorPhase.COMMITTED and self.final_commit is not None:
            messages.append(self.final_commit)

        return messages

    @property
    def decision(self) -> str:
        """Get the current decision state."""
        if self.phase == ArbitratorPhase.COMMITTED:
            return "commit"
        if self.phase == ArbitratorPhase.ABORTED:
            return "abort"
        return "pending"


# =============================================================================
# BFT Consensus Coordinator
# =============================================================================


@dataclass
class BftConsensus:
    """Coordinates BFT consensus across all arbitrators.

    This manages the full 2-flood BFT protocol:
    1. PROPOSE: Proposer floods value
    2. SHARE: All honest nodes flood partial signatures
    3. COMMIT: Any node with T shares floods aggregated proof
    """
    config: BftConfig
    threshold_scheme: ThresholdScheme = field(init=False)
    arbitrators: list[Arbitrator] = field(default_factory=list)
    ed25519_keypairs: list[KeyPair] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.threshold_scheme = ThresholdScheme(self.config)

        # Create arbitrators
        for i in range(self.config.n):
            keypair = KeyPair.generate()
            self.ed25519_keypairs.append(keypair)
            arb = Arbitrator(
                node_id=i,
                config=self.config,
                threshold_scheme=self.threshold_scheme,
                ed25519_keypair=keypair
            )
            self.arbitrators.append(arb)

    def propose(self, proposer_id: int, value: bytes) -> BftProposal:
        """Create a proposal from the specified node."""
        if proposer_id < 0 or proposer_id >= self.config.n:
            raise ValueError(f"Invalid proposer_id: {proposer_id}")

        keypair = self.ed25519_keypairs[proposer_id]
        round_num = self.arbitrators[proposer_id].current_round + 1

        msg = b"PROPOSE" + struct.pack('>Q', round_num) + value
        signature = keypair.sign(msg)

        return BftProposal(
            round=round_num,
            value=value,
            proposer_id=proposer_id,
            signature=signature,
            public_key=keypair.public_key.to_bytes()
        )

    def run_round(self, value: bytes, proposer_id: int = 0) -> Optional[BftCommit]:
        """Run a complete round of BFT consensus.

        Returns the commit if consensus is reached, None if not enough shares.

        This simulates perfect network conditions (all messages delivered).
        For testing with loss, use the simulation harness.
        """
        # Phase 1: Proposal
        proposal = self.propose(proposer_id, value)

        # Phase 2: All arbitrators receive proposal and create shares
        shares = []
        for arb in self.arbitrators:
            share = arb.receive_proposal(proposal)
            if share is not None:
                shares.append(share)

        # Phase 3: All arbitrators receive all shares
        commits = []
        for share in shares:
            for arb in self.arbitrators:
                commit = arb.receive_share(share)
                if commit is not None:
                    commits.append(commit)

        # Return first commit (all should be equivalent)
        if commits:
            # Propagate commit to all arbitrators
            for arb in self.arbitrators:
                arb.receive_commit(commits[0])
            return commits[0]

        return None

    @property
    def is_committed(self) -> bool:
        """Check if consensus has been reached."""
        return all(arb.phase == ArbitratorPhase.COMMITTED for arb in self.arbitrators)


# =============================================================================
# Utility Functions
# =============================================================================

import struct


def hash_round_value(round_num: int, value: bytes) -> bytes:
    """Compute hash of round number and value for BFT consensus.

    This is what gets signed in the SHARE phase.
    """
    return hashlib.sha256(
        round_num.to_bytes(8, 'big') + value
    ).digest()


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'BftConfig',
    'BlsPublicKey',
    'BlsKeyPair',
    'ThresholdSignature',
    'ThresholdScheme',
    'BftMessageType',
    'BftProposal',
    'BftShare',
    'BftCommit',
    'ArbitratorPhase',
    'Arbitrator',
    'BftConsensus',
    'hash_round_value',
]
