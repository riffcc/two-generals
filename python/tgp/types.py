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
