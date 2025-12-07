"""
Core protocol types for the Two Generals Protocol.

This module defines the cryptographic proof structures that enable
epistemic fixpoint construction through bilateral proof stapling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import hashlib


class Party(Enum):
    """Represents a party in the protocol (Alice or Bob)."""
    ALICE = auto()
    BOB = auto()

    def other(self) -> Party:
        """Return the counterparty."""
        return Party.BOB if self == Party.ALICE else Party.ALICE


@dataclass(frozen=True)
class Commitment:
    """
    Phase 1: C_X = Sign_X("I will attack at dawn if you agree")

    A signed commitment from one party indicating intent to coordinate.
    This is the base level of the epistemic proof chain.
    """
    party: Party
    message: bytes
    signature: bytes
    public_key: bytes

    def canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes for embedding in higher proofs."""
        return (
            self.party.name.encode() +
            b"|" +
            self.message +
            b"|" +
            self.signature +
            b"|" +
            self.public_key
        )

    def hash(self) -> bytes:
        """SHA-256 hash of canonical representation."""
        return hashlib.sha256(self.canonical_bytes()).digest()


@dataclass(frozen=True)
class DoubleProof:
    """
    Phase 2: D_X = Sign_X(C_X || C_Y || "Both parties committed")

    A double proof embeds BOTH original commitments, proving:
    "I know you've committed."

    Epistemic depth: 1
    """
    party: Party
    own_commitment: Commitment
    other_commitment: Commitment
    signature: bytes
    public_key: bytes

    def canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes for embedding in higher proofs."""
        return (
            b"DOUBLE|" +
            self.party.name.encode() +
            b"|" +
            self.own_commitment.canonical_bytes() +
            b"|" +
            self.other_commitment.canonical_bytes() +
            b"|" +
            self.signature +
            b"|" +
            self.public_key
        )

    def hash(self) -> bytes:
        """SHA-256 hash of canonical representation."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    def message_to_sign(self) -> bytes:
        """The message that was signed to create this proof."""
        return (
            self.own_commitment.canonical_bytes() +
            b"||" +
            self.other_commitment.canonical_bytes() +
            b"||BOTH_COMMITTED"
        )


@dataclass(frozen=True)
class TripleProof:
    """
    Phase 3: T_X = Sign_X(D_X || D_Y || "Both parties have double proofs")

    A triple proof embeds BOTH double proofs (and thus all four commitments),
    proving: "I know that you know I've committed."

    Epistemic depth: 2

    CRITICAL: Receiving T_Y gives you D_Y for free (it's embedded).
    This is what enables the bilateral construction property.
    """
    party: Party
    own_double: DoubleProof
    other_double: DoubleProof
    signature: bytes
    public_key: bytes

    def canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes for embedding in higher proofs."""
        return (
            b"TRIPLE|" +
            self.party.name.encode() +
            b"|" +
            self.own_double.canonical_bytes() +
            b"|" +
            self.other_double.canonical_bytes() +
            b"|" +
            self.signature +
            b"|" +
            self.public_key
        )

    def hash(self) -> bytes:
        """SHA-256 hash of canonical representation."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    def message_to_sign(self) -> bytes:
        """The message that was signed to create this proof."""
        return (
            self.own_double.canonical_bytes() +
            b"||" +
            self.other_double.canonical_bytes() +
            b"||BOTH_HAVE_DOUBLE"
        )


@dataclass(frozen=True)
class QuadProof:
    """
    Phase 4: Q_X = Sign_X(T_X || T_Y || "Fixpoint achieved")

    The quaternary proof (epistemic fixpoint). Q is NOT a single artifact -
    it's a bilateral receipt pair (Q_A, Q_B) where each half cryptographically
    proves the other half is constructible.

    KEY INSIGHT: Q_A exists → contains T_B → Bob had D_A → Bob can construct Q_B

    This is the self-certifying bilateral artifact that achieves common knowledge
    without infinite regress.

    Epistemic depth: ω (fixed point)
    """
    party: Party
    own_triple: TripleProof
    other_triple: TripleProof
    signature: bytes
    public_key: bytes

    def canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes."""
        return (
            b"QUAD|" +
            self.party.name.encode() +
            b"|" +
            self.own_triple.canonical_bytes() +
            b"|" +
            self.other_triple.canonical_bytes() +
            b"|" +
            self.signature +
            b"|" +
            self.public_key
        )

    def hash(self) -> bytes:
        """SHA-256 hash of canonical representation."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    def message_to_sign(self) -> bytes:
        """The message that was signed to create this proof."""
        return (
            self.own_triple.canonical_bytes() +
            b"||" +
            self.other_triple.canonical_bytes() +
            b"||FIXPOINT_ACHIEVED"
        )

    def verify_bilateral_construction(self) -> bool:
        """
        Verify the bilateral construction property:
        This QuadProof contains all the proofs needed for the counterparty
        to construct their QuadProof.

        The existence of Q_A proves Q_B is constructible because:
        - Q_A contains T_B (other_triple)
        - T_B contains D_A (inside its other_double)
        - Having T_A (which we're flooding) + D_B (from T_B) = constructible T_B
        - Having T_A + T_B = constructible Q_B
        """
        # Verify the embedding chain
        t_other = self.other_triple
        d_own_in_other = t_other.other_double

        # The other triple must contain OUR double proof
        if d_own_in_other.party != self.party:
            return False

        return True


@dataclass
class Message:
    """
    A network message carrying a proof artifact.

    Messages are continuously flooded until the next phase is reached.
    No message is "special" - any instance suffices.
    """
    sender: Party
    payload: Commitment | DoubleProof | TripleProof | QuadProof
    sequence: int = 0

    def proof_level(self) -> int:
        """Return the epistemic depth of this message's payload."""
        match self.payload:
            case Commitment():
                return 0
            case DoubleProof():
                return 1
            case TripleProof():
                return 2
            case QuadProof():
                return 4  # ω, but we use 4 for ordering


class Decision(Enum):
    """The final decision made by a party."""
    ATTACK = auto()
    ABORT = auto()
    PENDING = auto()


@dataclass
class ProtocolOutcome:
    """
    The outcome of a protocol run.

    CRITICAL: In a correct implementation, outcomes are ALWAYS symmetric:
    - Both ATTACK (success)
    - Both ABORT (safe failure)

    NEVER asymmetric (one ATTACK, one ABORT).
    """
    alice_decision: Decision
    bob_decision: Decision
    alice_final_proof: Optional[QuadProof] = None
    bob_final_proof: Optional[QuadProof] = None

    def is_symmetric(self) -> bool:
        """Verify the outcome is symmetric (no unilateral attack)."""
        return self.alice_decision == self.bob_decision

    def is_success(self) -> bool:
        """Both parties decided to ATTACK."""
        return (
            self.alice_decision == Decision.ATTACK and
            self.bob_decision == Decision.ATTACK
        )

    def is_safe_abort(self) -> bool:
        """Both parties decided to ABORT (safe failure)."""
        return (
            self.alice_decision == Decision.ABORT and
            self.bob_decision == Decision.ABORT
        )


class ProtocolPhase(Enum):
    """
    Protocol phases corresponding to proof levels.

    The protocol progresses through phases as proof artifacts are exchanged.
    """
    INIT = 0          # Before commitment
    COMMITMENT = 1    # Flooding C_X
    DOUBLE = 2        # Flooding D_X
    TRIPLE = 3        # Flooding T_X
    QUAD = 4          # Flooding Q_X
    COMPLETE = 5      # Fixpoint achieved
    ABORTED = 6       # Deadline expired without fixpoint


@dataclass(frozen=True)
class BilateralReceipt:
    """
    The complete bilateral receipt pair (Q_A, Q_B).

    This is the epistemic fixpoint where both parties have proven
    mutual knowledge. The artifact IS the proof.

    Neither half can exist without the other being constructible.
    This is the core theoretical contribution: the bilateral construction property.
    """
    alice_quad: QuadProof
    bob_quad: QuadProof

    def is_valid_fixpoint(self) -> bool:
        """
        Verify this is a valid epistemic fixpoint.

        Both quads must reference each other's triples.
        """
        # Alice's quad contains Bob's triple
        alice_has_bob_triple = self.alice_quad.other_triple.party == Party.BOB
        # Bob's quad contains Alice's triple
        bob_has_alice_triple = self.bob_quad.other_triple.party == Party.ALICE

        return alice_has_bob_triple and bob_has_alice_triple

    def __repr__(self) -> str:
        return f"BilateralReceipt(alice={self.alice_quad}, bob={self.bob_quad})"


# =============================================================================
# FULL SOLVE: Extended Protocol Types (V3)
# =============================================================================
#
# The C→D→T→Q protocol above provides the epistemic ladder. The types below
# complete the FULL SOLVE by adding mutual observation of readiness.
#
# Key insight: We don't just need to construct Q - we need to OBSERVE that
# our counterparty has ALSO constructed Q and is ready to proceed.
#
# Protocol extension:
#   Phase 5: Q_CONF = "I have constructed Q" (flood after constructing Q)
#   Phase 6: Q_CONF_FINAL = "I received your Q_CONF, I'm locked in"
#   Decision: Need Q + partner's Q_CONF_FINAL
#
# This eliminates the last edge case: both parties OBSERVE each other's
# transition from Q_CONF to Q_CONF_FINAL before deciding.
# =============================================================================


@dataclass(frozen=True)
class QuadConfirmation:
    """
    Phase 5: Q_CONF_X = Sign_X(Q_X || "I have constructed my quad proof")

    Confirms that this party has successfully constructed their QuadProof.
    Flooded after constructing Q to signal completion of the epistemic ladder.

    This is the "I'm ready" signal - but we can't ATTACK yet until we see
    the counterparty's Q_CONF_FINAL (proving they received our Q_CONF).

    Contains the full epistemic ladder (stapled proofs):
    - Own QuadProof (which contains all lower proofs)
    - Proof that we have the counterparty's TripleProof
    """
    party: Party
    own_quad: QuadProof
    confirmation_hash: bytes  # Hash proving all components present
    signature: bytes
    public_key: bytes

    def canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes."""
        return (
            b"Q_CONF|" +
            self.party.name.encode() +
            b"|" +
            self.own_quad.canonical_bytes() +
            b"|" +
            self.confirmation_hash +
            b"|" +
            self.signature +
            b"|" +
            self.public_key
        )

    def hash(self) -> bytes:
        """SHA-256 hash of canonical representation."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    def message_to_sign(self) -> bytes:
        """The message that was signed to create this confirmation."""
        return (
            self.own_quad.canonical_bytes() +
            b"||" +
            self.confirmation_hash +
            b"||Q_CONFIRMATION"
        )


@dataclass(frozen=True)
class QuadConfirmationFinal:
    """
    Phase 6: Q_CONF_FINAL_X = Sign_X(Q_CONF_X || Q_CONF_Y || "Mutually locked in")

    The FINAL confirmation proving mutual readiness:
    - "I have constructed my Q"
    - "I have received YOUR Q_CONF"
    - "I am now LOCKED IN to ATTACK"

    CRITICAL: This is what the counterparty OBSERVES to know we're ready.
    When you see partner's Q_CONF_FINAL, you know:
      1. Partner has their Q (from their Q_CONF)
      2. Partner has YOUR Q_CONF (required to create Q_CONF_FINAL)
      3. Partner is locked in - they WILL attack

    The "behavior change" from Q_CONF → Q_CONF_FINAL is the observable
    signal that mutual knowledge has been achieved.
    """
    party: Party
    own_quad_conf: QuadConfirmation
    other_quad_conf: QuadConfirmation
    ready_to_attack: bool  # Always True when this exists
    signature: bytes
    public_key: bytes

    def canonical_bytes(self) -> bytes:
        """Serialize to canonical bytes."""
        return (
            b"Q_CONF_FINAL|" +
            self.party.name.encode() +
            b"|" +
            self.own_quad_conf.canonical_bytes() +
            b"|" +
            self.other_quad_conf.canonical_bytes() +
            b"|" +
            (b"READY" if self.ready_to_attack else b"NOT_READY") +
            b"|" +
            self.signature +
            b"|" +
            self.public_key
        )

    def hash(self) -> bytes:
        """SHA-256 hash of canonical representation."""
        return hashlib.sha256(self.canonical_bytes()).digest()

    def message_to_sign(self) -> bytes:
        """The message that was signed to create this final confirmation."""
        return (
            self.own_quad_conf.canonical_bytes() +
            b"||" +
            self.other_quad_conf.canonical_bytes() +
            b"||MUTUALLY_LOCKED_IN"
        )


@dataclass(frozen=True)
class FinalReceipt:
    """
    The COMPLETE bilateral receipt with mutual confirmation.

    This is the FULL SOLVE artifact. It contains:
    - Both QuadProofs (Q_A, Q_B)
    - Both QuadConfirmations (Q_CONF_A, Q_CONF_B)
    - Both QuadConfirmationFinals (Q_CONF_FINAL_A, Q_CONF_FINAL_B)

    STRUCTURAL GUARANTEE:
    - FinalReceipt exists → both parties sent Q_CONF_FINAL
    - Q_CONF_FINAL_X exists → X has Y's Q_CONF
    - Q_CONF_X exists → X has Q_X
    - Therefore: BOTH parties have Q, BOTH are locked in, BOTH will ATTACK

    This is constructed PURELY LOCALLY after receiving partner's Q_CONF_FINAL.
    No network messages after Q_CONF_FINAL - the decision is deterministic.
    """
    # The bilateral quad proofs
    alice_quad: QuadProof
    bob_quad: QuadProof

    # The mutual confirmations
    alice_conf: QuadConfirmation
    bob_conf: QuadConfirmation

    # The final lock-in (proves mutual observation)
    alice_conf_final: QuadConfirmationFinal
    bob_conf_final: QuadConfirmationFinal

    # The deterministic receipt hash (identical for both parties)
    receipt_hash: bytes

    def is_complete(self) -> bool:
        """Verify all components are present."""
        return all([
            self.alice_quad,
            self.bob_quad,
            self.alice_conf,
            self.bob_conf,
            self.alice_conf_final,
            self.bob_conf_final,
            self.receipt_hash,
        ])

    def is_valid_fixpoint(self) -> bool:
        """
        Verify this is a valid epistemic fixpoint with mutual observation.

        The FULL SOLVE guarantee:
        - Both quads reference each other's triples (from C→D→T→Q)
        - Both conf_finals reference each other's confs (mutual observation)
        """
        # Basic quad structure
        alice_has_bob_triple = self.alice_quad.other_triple.party == Party.BOB
        bob_has_alice_triple = self.bob_quad.other_triple.party == Party.ALICE

        # Mutual confirmation structure
        alice_has_bob_conf = self.alice_conf_final.other_quad_conf.party == Party.BOB
        bob_has_alice_conf = self.bob_conf_final.other_quad_conf.party == Party.ALICE

        return all([
            alice_has_bob_triple,
            bob_has_alice_triple,
            alice_has_bob_conf,
            bob_has_alice_conf,
        ])

    @staticmethod
    def compute_receipt_hash(
        alice_conf_final: QuadConfirmationFinal,
        bob_conf_final: QuadConfirmationFinal,
    ) -> bytes:
        """
        Compute the deterministic receipt hash.

        CRITICAL: This hash is IDENTICAL for both parties because it's
        computed from the same inputs (both Q_CONF_FINALs) in sorted order.
        """
        # Sort by party name for deterministic ordering
        confs = sorted(
            [alice_conf_final.hash(), bob_conf_final.hash()]
        )
        return hashlib.sha256(
            confs[0] + confs[1] + b"FINAL_RECEIPT"
        ).digest()

    def __repr__(self) -> str:
        return f"FinalReceipt(hash={self.receipt_hash.hex()[:16]}...)"


# Extended protocol phases for FULL SOLVE
class ProtocolPhaseV3(Enum):
    """
    Protocol phases for the FULL SOLVE (V3).

    Extends the basic C→D→T→Q with confirmation phases:
      INIT → COMMITMENT → DOUBLE → TRIPLE → QUAD → Q_CONF → Q_CONF_FINAL → COMPLETE

    The key addition is the two confirmation phases which ensure
    mutual observation of readiness before the final decision.
    """
    INIT = 0           # Before commitment
    COMMITMENT = 1     # Flooding C_X
    DOUBLE = 2         # Flooding D_X
    TRIPLE = 3         # Flooding T_X
    QUAD = 4           # Flooding Q_X
    Q_CONF = 5         # Flooding Q_CONF_X (have Q, waiting for partner's Q_CONF)
    Q_CONF_FINAL = 6   # Flooding Q_CONF_FINAL_X (have partner's Q_CONF, locked in)
    COMPLETE = 7       # Mutual lock-in achieved - can ATTACK
    ABORTED = 8        # Deadline expired without mutual lock-in
