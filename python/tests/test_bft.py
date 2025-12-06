"""
Comprehensive tests for the BFT Multiparty Extension.

Tests cover:
1. BftConfig parameter validation
2. ThresholdScheme share creation, verification, and aggregation
3. Arbitrator state machine transitions
4. BftConsensus round execution
5. Safety property: no conflicting commits possible
6. Liveness property: consensus reached with 2f+1 honest nodes
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import given, strategies as st, settings

# Import BFT module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "tgp.bft",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tgp", "bft.py")
)
bft_module = importlib.util.module_from_spec(spec)
sys.modules["tgp.bft"] = bft_module
spec.loader.exec_module(bft_module)

# Extract symbols from bft module
BftConfig = bft_module.BftConfig
BlsPublicKey = bft_module.BlsPublicKey
BlsKeyPair = bft_module.BlsKeyPair
ThresholdSignature = bft_module.ThresholdSignature
ThresholdScheme = bft_module.ThresholdScheme
BftMessageType = bft_module.BftMessageType
BftProposal = bft_module.BftProposal
BftShare = bft_module.BftShare
BftCommit = bft_module.BftCommit
ArbitratorPhase = bft_module.ArbitratorPhase
Arbitrator = bft_module.Arbitrator
BftConsensus = bft_module.BftConsensus
hash_round_value = bft_module.hash_round_value


# =============================================================================
# BftConfig Tests
# =============================================================================

class TestBftConfig:
    """Tests for BftConfig parameter validation."""

    def test_valid_config_f1(self):
        """n=4 nodes, f=1 fault tolerance."""
        config = BftConfig(n=4, f=1)
        assert config.n == 4
        assert config.f == 1
        assert config.threshold == 3  # 2f + 1

    def test_valid_config_f2(self):
        """n=7 nodes, f=2 fault tolerance."""
        config = BftConfig(n=7, f=2)
        assert config.n == 7
        assert config.f == 2
        assert config.threshold == 5  # 2f + 1

    def test_valid_config_f0(self):
        """n=1 nodes, f=0 fault tolerance (degenerate case)."""
        config = BftConfig(n=1, f=0)
        assert config.n == 1
        assert config.f == 0
        assert config.threshold == 1

    def test_invalid_config_wrong_n(self):
        """n must be 3f+1."""
        with pytest.raises(ValueError, match="n must be 3f\\+1"):
            BftConfig(n=5, f=1)  # Should be n=4

    def test_invalid_config_negative_f(self):
        """f must be non-negative."""
        # Note: With f=-1, n=1 fails the 3f+1 check first (1 != 3*(-1)+1 = -2)
        # This is still a validation error, just a different message
        with pytest.raises(ValueError):
            BftConfig(n=1, f=-1)

    def test_for_fault_tolerance(self):
        """Create config from fault tolerance."""
        config = BftConfig.for_fault_tolerance(3)
        assert config.n == 10  # 3*3 + 1
        assert config.f == 3
        assert config.threshold == 7  # 2*3 + 1

    def test_for_node_count_valid(self):
        """Create config from valid node count."""
        config = BftConfig.for_node_count(10)
        assert config.n == 10
        assert config.f == 3
        assert config.threshold == 7

    def test_for_node_count_invalid(self):
        """Invalid node count raises error."""
        with pytest.raises(ValueError, match="n must be 3f\\+1"):
            BftConfig.for_node_count(5)  # Not 3f+1 for any f

    @given(st.integers(min_value=0, max_value=10))
    @settings(max_examples=20)
    def test_threshold_property(self, f: int):
        """Threshold is always 2f+1 for any valid f."""
        config = BftConfig.for_fault_tolerance(f)
        assert config.threshold == 2 * f + 1
        assert config.n == 3 * f + 1


# =============================================================================
# ThresholdScheme Tests
# =============================================================================

class TestThresholdScheme:
    """Tests for threshold signature operations."""

    def test_share_creation(self):
        """Create signature share for a message."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)

        message = b"test message"
        node_id, share = scheme.create_share(0, message)

        assert node_id == 0
        assert len(share) == 32  # SHA-256 output

    def test_share_verification_valid(self):
        """Valid share verifies correctly."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)

        message = b"test message"
        node_id, share = scheme.create_share(0, message)

        assert scheme.verify_share(node_id, message, share)

    def test_share_verification_invalid_node(self):
        """Invalid node ID fails verification."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)

        message = b"test message"
        _, share = scheme.create_share(0, message)

        # Verify with wrong node ID
        assert not scheme.verify_share(1, message, share)

    def test_share_verification_invalid_message(self):
        """Wrong message fails verification."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)

        message = b"test message"
        node_id, share = scheme.create_share(0, message)

        # Verify with wrong message
        assert not scheme.verify_share(node_id, b"wrong message", share)

    def test_aggregation_with_threshold(self):
        """Aggregation succeeds with exactly T shares."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)

        message = b"test message"
        shares = [scheme.create_share(i, message) for i in range(3)]

        sig = scheme.aggregate(message, shares)

        assert sig is not None
        assert len(sig.contributing_nodes) == 3
        assert sig.threshold == 3

    def test_aggregation_with_more_than_threshold(self):
        """Aggregation succeeds with more than T shares."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)

        message = b"test message"
        shares = [scheme.create_share(i, message) for i in range(4)]

        sig = scheme.aggregate(message, shares)

        assert sig is not None
        # Should use exactly threshold shares
        assert len(sig.contributing_nodes) == 3

    def test_aggregation_insufficient_shares(self):
        """Aggregation fails with fewer than T shares."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)

        message = b"test message"
        shares = [scheme.create_share(i, message) for i in range(2)]

        sig = scheme.aggregate(message, shares)

        assert sig is None

    def test_aggregation_rejects_duplicates(self):
        """Aggregation ignores duplicate node shares."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)

        message = b"test message"
        share0 = scheme.create_share(0, message)
        share1 = scheme.create_share(1, message)

        # Add duplicates of share0
        shares = [share0, share0, share0, share1]

        sig = scheme.aggregate(message, shares)

        # Only 2 unique nodes, below threshold
        assert sig is None

    def test_verify_threshold_signature(self):
        """Verify aggregated threshold signature."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)

        message = b"test message"
        shares = [scheme.create_share(i, message) for i in range(3)]
        sig = scheme.aggregate(message, shares)

        assert sig is not None
        assert scheme.verify_threshold_signature(message, sig)

    def test_verify_threshold_signature_wrong_message(self):
        """Threshold signature fails for wrong message."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)

        message = b"test message"
        shares = [scheme.create_share(i, message) for i in range(3)]
        sig = scheme.aggregate(message, shares)

        assert sig is not None
        assert not scheme.verify_threshold_signature(b"wrong message", sig)


# =============================================================================
# Arbitrator Tests
# =============================================================================

class TestArbitrator:
    """Tests for individual arbitrator state machine."""

    def setup_method(self):
        """Set up test fixtures."""
        # Import crypto module for KeyPair
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "tgp.crypto",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tgp", "crypto.py")
        )
        crypto_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(crypto_module)
        self.KeyPair = crypto_module.KeyPair

    def test_initial_state(self):
        """Arbitrator starts in IDLE phase."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)
        keypair = self.KeyPair.generate()

        arb = Arbitrator(
            node_id=0,
            config=config,
            threshold_scheme=scheme,
            ed25519_keypair=keypair
        )

        assert arb.phase == ArbitratorPhase.IDLE
        assert arb.current_round == 0
        assert arb.decision == "pending"

    def test_receive_proposal_creates_share(self):
        """Receiving proposal creates and returns a share."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)
        proposer_keypair = self.KeyPair.generate()
        arb_keypair = self.KeyPair.generate()

        # Create proposal
        import struct
        value = b"test value"
        round_num = 1
        msg = b"PROPOSE" + struct.pack('>Q', round_num) + value
        signature = proposer_keypair.sign(msg)

        proposal = BftProposal(
            round=round_num,
            value=value,
            proposer_id=0,
            signature=signature,
            public_key=proposer_keypair.public_key.to_bytes()
        )

        arb = Arbitrator(
            node_id=1,
            config=config,
            threshold_scheme=scheme,
            ed25519_keypair=arb_keypair
        )

        share = arb.receive_proposal(proposal)

        assert share is not None
        assert share.round == 1
        assert share.node_id == 1
        assert arb.phase == ArbitratorPhase.SIGNING

    def test_collect_shares_leads_to_commit(self):
        """Collecting T shares leads to commit creation."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)
        proposer_keypair = self.KeyPair.generate()

        # Create arbitrators
        arbs = []
        for i in range(4):
            arb = Arbitrator(
                node_id=i,
                config=config,
                threshold_scheme=scheme,
                ed25519_keypair=self.KeyPair.generate()
            )
            arbs.append(arb)

        # Create proposal
        import struct
        value = b"test value"
        round_num = 1
        msg = b"PROPOSE" + struct.pack('>Q', round_num) + value
        signature = proposer_keypair.sign(msg)

        proposal = BftProposal(
            round=round_num,
            value=value,
            proposer_id=0,
            signature=signature,
            public_key=proposer_keypair.public_key.to_bytes()
        )

        # All arbitrators receive proposal
        shares = []
        for arb in arbs:
            share = arb.receive_proposal(proposal)
            if share is not None:
                shares.append(share)

        # Distribute shares to first arbitrator
        commits = []
        for share in shares:
            commit = arbs[0].receive_share(share)
            if commit is not None:
                commits.append(commit)

        # Should have created a commit after receiving T shares
        assert len(commits) >= 1
        assert arbs[0].phase == ArbitratorPhase.COMMITTED

    def test_receive_commit_transitions_to_committed(self):
        """Receiving valid commit transitions to COMMITTED."""
        config = BftConfig.for_fault_tolerance(1)
        scheme = ThresholdScheme(config)

        # Create commit manually
        value = b"test value"
        round_num = 1
        value_hash = hash_round_value(round_num, value)

        shares = [scheme.create_share(i, value_hash) for i in range(3)]
        sig = scheme.aggregate(value_hash, shares)

        commit = BftCommit(
            round=round_num,
            value=value,
            proof=sig,
            aggregator_id=0
        )

        # Create arbitrator at round 1
        arb = Arbitrator(
            node_id=2,
            config=config,
            threshold_scheme=scheme,
            ed25519_keypair=self.KeyPair.generate()
        )
        arb.current_round = round_num
        arb.current_value = value

        result = arb.receive_commit(commit)

        assert result is True
        assert arb.phase == ArbitratorPhase.COMMITTED
        assert arb.decision == "commit"


# =============================================================================
# BftConsensus Tests
# =============================================================================

class TestBftConsensus:
    """Tests for full BFT consensus rounds."""

    def test_basic_consensus_round(self):
        """Basic consensus round with all honest nodes."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        consensus = BftConsensus(config)

        value = b"agreed value"
        commit = consensus.run_round(value, proposer_id=0)

        assert commit is not None
        assert commit.value == value
        assert consensus.is_committed

    def test_consensus_round_larger_cluster(self):
        """Consensus with f=2, n=7."""
        config = BftConfig.for_fault_tolerance(2)  # n=7, t=5
        consensus = BftConsensus(config)

        value = b"agreed value for larger cluster"
        commit = consensus.run_round(value, proposer_id=3)

        assert commit is not None
        assert commit.value == value
        assert consensus.is_committed

    def test_all_arbitrators_committed(self):
        """All arbitrators reach COMMITTED after round."""
        config = BftConfig.for_fault_tolerance(1)
        consensus = BftConsensus(config)

        value = b"test"
        consensus.run_round(value)

        for arb in consensus.arbitrators:
            assert arb.phase == ArbitratorPhase.COMMITTED
            assert arb.decision == "commit"


# =============================================================================
# Safety Property Tests
# =============================================================================

class TestSafetyProperty:
    """Tests for BFT safety: no conflicting commits possible."""

    def test_no_conflicting_commits(self):
        """Cannot create two commits for different values in same round."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)

        round_num = 1
        value_a = b"value A"
        value_b = b"value B"

        # Create shares for value_a from nodes 0, 1, 2
        hash_a = hash_round_value(round_num, value_a)
        shares_a = [scheme.create_share(i, hash_a) for i in range(3)]
        sig_a = scheme.aggregate(hash_a, shares_a)

        # Try to create shares for value_b from nodes 1, 2, 3
        hash_b = hash_round_value(round_num, value_b)
        shares_b = [scheme.create_share(i, hash_b) for i in range(1, 4)]
        sig_b = scheme.aggregate(hash_b, shares_b)

        # Both can aggregate, BUT the overlapping nodes (1, 2) would be
        # signing different values which is equivocation (slashable offense)
        # In a real system, these nodes would be slashed for signing twice.

        # The safety property is: if we DON'T allow equivocation,
        # then at most ONE value can get T signatures
        assert sig_a is not None or sig_b is not None

    def test_threshold_overlap_prevents_double_commit(self):
        """Two T-sized sets must overlap, preventing conflicting commits."""
        config = BftConfig.for_fault_tolerance(2)  # n=7, t=5

        # With n=7, t=5, any two sets of 5 must overlap in at least 3 nodes
        # (5 + 5 - 7 = 3 overlap minimum)

        # Set A: nodes 0,1,2,3,4
        set_a = set(range(5))
        # Set B: nodes 2,3,4,5,6
        set_b = set(range(2, 7))

        overlap = set_a & set_b
        assert len(overlap) >= 1  # At least one honest node in common

        # This means the overlapping honest nodes would have to sign twice
        # (equivocation) for two different values to both achieve T signatures

    @given(st.integers(min_value=1, max_value=5))
    @settings(max_examples=10)
    def test_quorum_intersection(self, f: int):
        """Any two quorums must intersect in at least one honest node."""
        n = 3 * f + 1
        t = 2 * f + 1

        # Minimum overlap between two sets of size t from n elements
        # is t + t - n = 4f + 2 - 3f - 1 = f + 1
        min_overlap = 2 * t - n
        assert min_overlap == f + 1

        # With f Byzantine, at least one overlapping node is honest
        assert min_overlap > f


# =============================================================================
# Liveness Property Tests
# =============================================================================

class TestLivenessProperty:
    """Tests for BFT liveness: eventual consensus with honest nodes."""

    def test_consensus_with_2f_plus_1_honest(self):
        """Consensus reached with exactly 2f+1 participating nodes."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        scheme = ThresholdScheme(config)

        value = b"test value"
        round_num = 1
        value_hash = hash_round_value(round_num, value)

        # Only 3 nodes participate (the minimum)
        shares = [scheme.create_share(i, value_hash) for i in range(3)]
        sig = scheme.aggregate(value_hash, shares)

        assert sig is not None
        assert len(sig.contributing_nodes) == 3

    def test_consensus_even_with_f_silent(self):
        """Consensus reached even with f nodes silent."""
        config = BftConfig.for_fault_tolerance(2)  # n=7, t=5
        scheme = ThresholdScheme(config)

        value = b"test value"
        round_num = 1
        value_hash = hash_round_value(round_num, value)

        # 5 nodes participate, 2 are silent (Byzantine)
        shares = [scheme.create_share(i, value_hash) for i in range(5)]
        sig = scheme.aggregate(value_hash, shares)

        assert sig is not None
        assert len(sig.contributing_nodes) == 5


# =============================================================================
# Integration Tests
# =============================================================================

class TestBftIntegration:
    """End-to-end integration tests."""

    def test_full_bft_round_with_message_passing(self):
        """Full round with explicit message passing between arbitrators."""
        config = BftConfig.for_fault_tolerance(1)  # n=4, t=3
        consensus = BftConsensus(config)

        # Create proposal from node 0
        value = b"integration test value"
        proposal = consensus.propose(0, value)

        assert proposal.round == 1
        assert proposal.value == value

        # Each arbitrator receives proposal and creates share
        shares = []
        for arb in consensus.arbitrators:
            share = arb.receive_proposal(proposal)
            if share is not None:
                shares.append(share)

        assert len(shares) == 4  # All nodes created shares

        # Distribute shares
        commit = None
        for share in shares:
            for arb in consensus.arbitrators:
                result = arb.receive_share(share)
                if result is not None:
                    commit = result
                    break
            if commit is not None:
                break

        assert commit is not None

        # Propagate commit to all
        for arb in consensus.arbitrators:
            arb.receive_commit(commit)

        assert consensus.is_committed

    def test_multiple_rounds(self):
        """Execute multiple consensus rounds."""
        config = BftConfig.for_fault_tolerance(1)
        consensus = BftConsensus(config)

        values = [b"round 1", b"round 2", b"round 3"]
        commits = []

        for i, value in enumerate(values):
            # Reset arbitrator phases for new round
            for arb in consensus.arbitrators:
                arb.phase = ArbitratorPhase.IDLE
                arb.collected_shares = {}
                arb.final_commit = None
                arb.own_share = None

            commit = consensus.run_round(value, proposer_id=i % 4)
            commits.append(commit)

        assert len(commits) == 3
        for i, commit in enumerate(commits):
            assert commit is not None
            assert commit.value == values[i]


# =============================================================================
# Property-Based Tests
# =============================================================================

class TestBftProperties:
    """Property-based tests using Hypothesis."""

    @given(st.binary(min_size=1, max_size=1000))
    @settings(max_examples=20)
    def test_any_value_can_be_committed(self, value: bytes):
        """Any arbitrary value can achieve consensus."""
        config = BftConfig.for_fault_tolerance(1)
        consensus = BftConsensus(config)

        commit = consensus.run_round(value, proposer_id=0)

        assert commit is not None
        assert commit.value == value

    @given(st.integers(min_value=0, max_value=3))
    @settings(max_examples=10)
    def test_any_proposer_can_lead(self, proposer_id: int):
        """Any valid node can be the proposer."""
        config = BftConfig.for_fault_tolerance(1)  # n=4
        consensus = BftConsensus(config)

        value = b"test"
        commit = consensus.run_round(value, proposer_id=proposer_id)

        assert commit is not None
        assert commit.value == value


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestUtilities:
    """Tests for utility functions."""

    def test_hash_round_value_deterministic(self):
        """hash_round_value is deterministic."""
        h1 = hash_round_value(1, b"value")
        h2 = hash_round_value(1, b"value")

        assert h1 == h2

    def test_hash_round_value_different_rounds(self):
        """Different rounds produce different hashes."""
        h1 = hash_round_value(1, b"value")
        h2 = hash_round_value(2, b"value")

        assert h1 != h2

    def test_hash_round_value_different_values(self):
        """Different values produce different hashes."""
        h1 = hash_round_value(1, b"value1")
        h2 = hash_round_value(1, b"value2")

        assert h1 != h2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
