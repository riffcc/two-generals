"""
Two Generals Protocol - State Machine Implementation

This module implements the core TwoGenerals protocol state machine with
C -> D -> T -> Q phase transitions. The protocol achieves deterministic
coordination through epistemic proof escalation.

Protocol Phases:
- INIT: Initial state, preparing commitment
- COMMITMENT: Flooding C_X, waiting for C_Y
- DOUBLE: Have both commitments, flooding D_X, waiting for D_Y
- TRIPLE: Have both doubles, flooding T_X, waiting for T_Y
- QUAD: Have both triples, flooding Q_X, waiting for Q_Y
- COMPLETE: Bilateral receipt pair (Q_A, Q_B) achieved
- ABORTED: Deadline passed without achieving fixpoint

The key insight: Once Q_X is constructible, Q_Y is also constructible.
This is the bilateral construction property that makes TGP work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Callable
import hashlib

from .types import (
    Party,
    Commitment,
    DoubleProof,
    TripleProof,
    QuadProof,
    Message,
)
from .crypto import KeyPair, PublicKey


class ProtocolState(Enum):
    """
    Protocol state machine states.

    Transitions follow the epistemic proof escalation:
    INIT -> COMMITMENT -> DOUBLE -> TRIPLE -> QUAD -> COMPLETE

    Each transition occurs upon receiving the counterparty's artifact
    at the current level.
    """
    INIT = auto()           # Before commitment created
    COMMITMENT = auto()     # Flooding C_X, awaiting C_Y
    DOUBLE = auto()         # Flooding D_X, awaiting D_Y
    TRIPLE = auto()         # Flooding T_X, awaiting T_Y
    QUAD = auto()           # Flooding Q_X, awaiting Q_Y
    COMPLETE = auto()       # Fixpoint achieved - can ATTACK
    ABORTED = auto()        # Deadline passed - must ABORT


class Decision(Enum):
    """Final protocol decision."""
    ATTACK = auto()   # Fixpoint achieved
    ABORT = auto()    # Could not achieve fixpoint


@dataclass
class ProtocolMessage:
    """
    A message in the protocol for network transmission.

    Wraps proof artifacts with metadata for flooding.
    """
    sender: Party
    state: ProtocolState
    payload: Commitment | DoubleProof | TripleProof | QuadProof
    sequence: int = 0

    def serialize(self) -> bytes:
        """Serialize for network transmission."""
        if isinstance(self.payload, Commitment):
            return self.payload.canonical_bytes()
        elif isinstance(self.payload, DoubleProof):
            return self.payload.canonical_bytes()
        elif isinstance(self.payload, TripleProof):
            return self.payload.canonical_bytes()
        elif isinstance(self.payload, QuadProof):
            return self.payload.canonical_bytes()
        return b""


@dataclass
class TwoGenerals:
    """
    Two Generals Protocol state machine.

    Implements the complete C -> D -> T -> Q proof escalation with
    continuous flooding semantics. Each party maintains their own
    instance and exchanges messages until both reach COMPLETE.

    The protocol guarantees:
    - If one party can construct Q, both can
    - Outcomes are always symmetric (both ATTACK or both ABORT)
    - No message is "special" - continuous flooding ensures any copy suffices

    Example usage:
        alice_keys = KeyPair.generate()
        bob_keys = KeyPair.generate()

        alice = TwoGenerals.create(Party.ALICE, alice_keys, bob_keys.public_key)
        bob = TwoGenerals.create(Party.BOB, bob_keys, alice_keys.public_key)

        # Exchange messages until both complete
        while not (alice.is_complete and bob.is_complete):
            for msg in alice.get_messages_to_send():
                bob.receive(msg)
            for msg in bob.get_messages_to_send():
                alice.receive(msg)
    """
    party: Party
    keypair: KeyPair
    counterparty_public_key: PublicKey
    state: ProtocolState = field(default=ProtocolState.INIT)

    # Proof artifacts at each level
    own_commitment: Optional[Commitment] = None
    other_commitment: Optional[Commitment] = None
    own_double: Optional[DoubleProof] = None
    other_double: Optional[DoubleProof] = None
    own_triple: Optional[TripleProof] = None
    other_triple: Optional[TripleProof] = None
    own_quad: Optional[QuadProof] = None
    other_quad: Optional[QuadProof] = None

    # Message sequencing
    sequence_counter: int = 0

    # Commitment message (customizable)
    commitment_message: bytes = field(default=b"I will attack at dawn if you agree")

    @classmethod
    def create(
        cls,
        party: Party,
        keypair: KeyPair,
        counterparty_public_key: PublicKey,
        commitment_message: Optional[bytes] = None,
    ) -> TwoGenerals:
        """
        Create a new TwoGenerals protocol instance.

        Args:
            party: Which party this instance represents (ALICE or BOB)
            keypair: This party's signing keypair
            counterparty_public_key: The other party's public key for verification
            commitment_message: Optional custom commitment message

        Returns:
            Initialized TwoGenerals instance ready to begin protocol
        """
        instance = cls(
            party=party,
            keypair=keypair,
            counterparty_public_key=counterparty_public_key,
        )
        if commitment_message is not None:
            instance.commitment_message = commitment_message

        # Immediately create and sign our commitment
        instance._create_commitment()
        return instance

    def _create_commitment(self) -> None:
        """Create and sign our initial commitment (Phase 1)."""
        signature = self.keypair.sign(self.commitment_message)
        self.own_commitment = Commitment(
            party=self.party,
            message=self.commitment_message,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.state = ProtocolState.COMMITMENT

    def _create_double_proof(self) -> None:
        """
        Create double proof once we have counterparty's commitment (Phase 2).

        D_X = Sign_X(C_X || C_Y || "Both parties committed")
        """
        assert self.own_commitment is not None
        assert self.other_commitment is not None

        # Sign the combination of both commitments
        payload = self.own_commitment.canonical_bytes() + self.other_commitment.canonical_bytes() + b"Both parties committed"
        signature = self.keypair.sign(payload)

        self.own_double = DoubleProof(
            party=self.party,
            own_commitment=self.own_commitment,
            other_commitment=self.other_commitment,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.state = ProtocolState.DOUBLE

    def _create_triple_proof(self) -> None:
        """
        Create triple proof once we have counterparty's double (Phase 3).

        T_X = Sign_X(D_X || D_Y || "Both parties have double proofs")
        """
        assert self.own_double is not None
        assert self.other_double is not None

        # Sign the combination of both double proofs
        payload = self.own_double.canonical_bytes() + self.other_double.canonical_bytes() + b"Both parties have double proofs"
        signature = self.keypair.sign(payload)

        self.own_triple = TripleProof(
            party=self.party,
            own_double=self.own_double,
            other_double=self.other_double,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.state = ProtocolState.TRIPLE

    def _create_quad_proof(self) -> None:
        """
        Create quaternary proof once we have counterparty's triple (Phase 4).

        Q_X = Sign_X(T_X || T_Y || "Fixpoint achieved")

        This is the epistemic fixpoint. By construction, if we can create Q_X,
        the counterparty can create Q_Y. The bilateral construction property
        guarantees symmetric outcomes.
        """
        assert self.own_triple is not None
        assert self.other_triple is not None

        # Sign the combination of both triple proofs
        payload = self.own_triple.canonical_bytes() + self.other_triple.canonical_bytes() + b"Fixpoint achieved"
        signature = self.keypair.sign(payload)

        self.own_quad = QuadProof(
            party=self.party,
            own_triple=self.own_triple,
            other_triple=self.other_triple,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.state = ProtocolState.QUAD

    def receive(self, msg: ProtocolMessage | Commitment | DoubleProof | TripleProof | QuadProof) -> bool:
        """
        Process a received message from the counterparty.

        Args:
            msg: The received message or proof artifact

        Returns:
            True if the message caused a state transition, False otherwise
        """
        # Extract payload if wrapped in ProtocolMessage
        if isinstance(msg, ProtocolMessage):
            payload = msg.payload
        else:
            payload = msg

        # Handle based on payload type
        if isinstance(payload, Commitment):
            return self._receive_commitment(payload)
        elif isinstance(payload, DoubleProof):
            return self._receive_double_proof(payload)
        elif isinstance(payload, TripleProof):
            return self._receive_triple_proof(payload)
        elif isinstance(payload, QuadProof):
            return self._receive_quad_proof(payload)

        return False

    def _verify_signature(self, signature: bytes, message: bytes, public_key_bytes: bytes) -> bool:
        """Verify a signature using the counterparty's public key."""
        try:
            pub_key = PublicKey.from_bytes(public_key_bytes)
            return pub_key.verify(message, signature)
        except Exception:
            return False

    def _receive_commitment(self, commitment: Commitment) -> bool:
        """Process a received commitment."""
        # Must be from counterparty
        if commitment.party == self.party:
            return False

        # Already have it
        if self.other_commitment is not None:
            return False

        # Verify signature
        if not self._verify_signature(
            commitment.signature,
            commitment.message,
            commitment.public_key,
        ):
            return False

        self.other_commitment = commitment

        # If we're in COMMITMENT state and now have both, advance to DOUBLE
        if self.state == ProtocolState.COMMITMENT and self.own_commitment is not None:
            self._create_double_proof()
            return True

        return True

    def _receive_double_proof(self, double: DoubleProof) -> bool:
        """Process a received double proof."""
        # Must be from counterparty
        if double.party == self.party:
            return False

        # Already have it
        if self.other_double is not None:
            return False

        # Verify the double proof signature
        payload = double.own_commitment.canonical_bytes() + double.other_commitment.canonical_bytes() + b"Both parties committed"
        if not self._verify_signature(double.signature, payload, double.public_key):
            return False

        # Extract embedded artifacts if we don't have them
        if self.other_commitment is None:
            # The double proof contains the counterparty's commitment
            self.other_commitment = double.own_commitment
            if self.state == ProtocolState.COMMITMENT and self.own_commitment is not None:
                self._create_double_proof()

        self.other_double = double

        # If we're in DOUBLE state and now have both, advance to TRIPLE
        if self.state == ProtocolState.DOUBLE and self.own_double is not None:
            self._create_triple_proof()
            return True

        return True

    def _receive_triple_proof(self, triple: TripleProof) -> bool:
        """
        Process a received triple proof.

        CRITICAL: Receiving T_Y gives us D_Y for free (it's embedded).
        This is the nested proof embedding that enables bilateral construction.
        """
        # Must be from counterparty
        if triple.party == self.party:
            return False

        # Already have it
        if self.other_triple is not None:
            return False

        # Verify the triple proof signature
        payload = triple.own_double.canonical_bytes() + triple.other_double.canonical_bytes() + b"Both parties have double proofs"
        if not self._verify_signature(triple.signature, payload, triple.public_key):
            return False

        # Extract embedded artifacts if we don't have them
        # T_Y contains D_Y (own_double) which contains C_Y
        if self.other_double is None:
            self.other_double = triple.own_double
            if self.other_commitment is None:
                self.other_commitment = triple.own_double.own_commitment

            # Cascade state updates
            if self.state == ProtocolState.COMMITMENT and self.own_commitment is not None:
                self._create_double_proof()
            if self.state == ProtocolState.DOUBLE and self.own_double is not None:
                self._create_triple_proof()

        self.other_triple = triple

        # If we're in TRIPLE state and now have both, advance to QUAD
        if self.state == ProtocolState.TRIPLE and self.own_triple is not None:
            self._create_quad_proof()
            return True

        return True

    def _receive_quad_proof(self, quad: QuadProof) -> bool:
        """
        Process a received quad proof.

        Receiving Q_Y means the counterparty has achieved the fixpoint.
        By the bilateral construction property, we can also achieve it.
        """
        # Must be from counterparty
        if quad.party == self.party:
            return False

        # Already have it
        if self.other_quad is not None:
            return False

        # Verify the quad proof signature
        payload = quad.own_triple.canonical_bytes() + quad.other_triple.canonical_bytes() + b"Fixpoint achieved"
        if not self._verify_signature(quad.signature, payload, quad.public_key):
            return False

        # Extract embedded artifacts
        if self.other_triple is None:
            self.other_triple = quad.own_triple
            # Cascade extraction
            if self.other_double is None:
                self.other_double = quad.own_triple.own_double
            if self.other_commitment is None:
                self.other_commitment = quad.own_triple.own_double.own_commitment

            # Cascade state updates
            if self.state == ProtocolState.COMMITMENT and self.own_commitment is not None:
                if self.other_commitment is None:
                    self.other_commitment = quad.own_triple.own_double.own_commitment
                self._create_double_proof()
            if self.state == ProtocolState.DOUBLE and self.own_double is not None:
                self._create_triple_proof()
            if self.state == ProtocolState.TRIPLE and self.own_triple is not None:
                self._create_quad_proof()

        self.other_quad = quad

        # If we have both quad proofs, we're COMPLETE
        if self.own_quad is not None:
            self.state = ProtocolState.COMPLETE
            return True

        return True

    def get_messages_to_send(self) -> List[ProtocolMessage]:
        """
        Get messages to flood at the current state.

        In continuous flooding mode, we send all artifacts at our current
        level and below. Higher-level proofs embed lower-level ones, so
        receiving T_X is sufficient even if C_X and D_X were lost.

        Returns:
            List of messages to send (flood) to counterparty
        """
        messages = []
        self.sequence_counter += 1

        # Always send highest available proof (it embeds all lower ones)
        if self.state == ProtocolState.COMPLETE or self.state == ProtocolState.QUAD:
            if self.own_quad is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=self.state,
                    payload=self.own_quad,
                    sequence=self.sequence_counter,
                ))
        elif self.state == ProtocolState.TRIPLE:
            if self.own_triple is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=self.state,
                    payload=self.own_triple,
                    sequence=self.sequence_counter,
                ))
        elif self.state == ProtocolState.DOUBLE:
            if self.own_double is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=self.state,
                    payload=self.own_double,
                    sequence=self.sequence_counter,
                ))
        elif self.state == ProtocolState.COMMITMENT:
            if self.own_commitment is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=self.state,
                    payload=self.own_commitment,
                    sequence=self.sequence_counter,
                ))

        return messages

    @property
    def is_complete(self) -> bool:
        """Check if the protocol has reached the fixpoint."""
        return self.state == ProtocolState.COMPLETE

    @property
    def can_attack(self) -> bool:
        """Check if this party can safely ATTACK."""
        return self.is_complete and self.own_quad is not None

    def get_decision(self) -> Decision:
        """
        Get the final decision.

        Returns:
            ATTACK if fixpoint achieved, ABORT otherwise
        """
        if self.is_complete:
            return Decision.ATTACK
        return Decision.ABORT

    def abort(self) -> None:
        """
        Abort the protocol (e.g., deadline passed).

        After calling abort(), this party will decide ABORT.
        """
        if self.state != ProtocolState.COMPLETE:
            self.state = ProtocolState.ABORTED

    def get_bilateral_receipt(self) -> Optional[tuple[QuadProof, QuadProof]]:
        """
        Get the bilateral receipt pair (Q_A, Q_B) if complete.

        Returns:
            Tuple of (own_quad, other_quad) if complete, None otherwise
        """
        if self.is_complete and self.own_quad is not None and self.other_quad is not None:
            return (self.own_quad, self.other_quad)
        return None

    def __repr__(self) -> str:
        return f"TwoGenerals(party={self.party.name}, state={self.state.name})"


def run_protocol_simulation(
    alice_keypair: KeyPair,
    bob_keypair: KeyPair,
    max_rounds: int = 100,
    message_filter: Optional[Callable[[ProtocolMessage], bool]] = None,
) -> tuple[TwoGenerals, TwoGenerals]:
    """
    Run a complete protocol simulation between Alice and Bob.

    This is useful for testing the protocol under various conditions.

    Args:
        alice_keypair: Alice's signing keypair
        bob_keypair: Bob's signing keypair
        max_rounds: Maximum number of message exchange rounds
        message_filter: Optional filter to simulate message loss (return False to drop)

    Returns:
        Tuple of (alice_state, bob_state) after simulation
    """
    alice = TwoGenerals.create(
        party=Party.ALICE,
        keypair=alice_keypair,
        counterparty_public_key=bob_keypair.public_key,
    )
    bob = TwoGenerals.create(
        party=Party.BOB,
        keypair=bob_keypair,
        counterparty_public_key=alice_keypair.public_key,
    )

    for _ in range(max_rounds):
        # Exchange messages
        for msg in alice.get_messages_to_send():
            if message_filter is None or message_filter(msg):
                bob.receive(msg)

        for msg in bob.get_messages_to_send():
            if message_filter is None or message_filter(msg):
                alice.receive(msg)

        # Check if both complete
        if alice.is_complete and bob.is_complete:
            break

    return alice, bob
