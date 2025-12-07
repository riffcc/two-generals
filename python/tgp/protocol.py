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
    # V3 FULL SOLVE types
    QuadConfirmation,
    QuadConfirmationFinal,
    FinalReceipt,
    ProtocolPhaseV3,
)
from .crypto import (
    KeyPair,
    PublicKey,
    DHSession,
    DHPublicKey,
    hash_proofs,
    serialize_dh_message,
    deserialize_dh_message,
)


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
    Two Generals Protocol state machine with DH hardening.

    Implements the complete C -> D -> T -> Q proof escalation with
    continuous flooding semantics, plus optional DH key exchange
    for session key derivation (Part II hardening).

    The protocol guarantees:
    - If one party can construct Q, both can
    - Outcomes are always symmetric (both ATTACK or both ABORT)
    - No message is "special" - continuous flooding ensures any copy suffices
    - Optional DH layer provides forward-secure session keys

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

        # After Q achieved, complete DH exchange for session keys
        alice_dh = alice.create_dh_contribution()
        bob_dh = bob.create_dh_contribution()
        alice.complete_dh_exchange(bob_dh)
        bob.complete_dh_exchange(alice_dh)

        # Now can encrypt/decrypt with session keys
        nonce, ct = alice.encrypt(b"Hello")
        pt = bob.decrypt(nonce, ct)
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

    # DH hardening layer (Part II)
    dh_session: Optional[DHSession] = field(default=None, repr=False)
    own_dh_contribution: Optional[bytes] = field(default=None, repr=False)
    other_dh_contribution: Optional[bytes] = field(default=None, repr=False)

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
        """
        Check if the protocol has reached the fixpoint.

        Per the paper (Algorithm 1, lines 9-12): decide ATTACK upon
        constructing Q_X after receiving T_Y. We don't need to wait
        for Q_Y - the bilateral construction property guarantees that
        if we can construct Q_X, then Q_Y is constructible.
        """
        return self.own_quad is not None

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

    # =========================================================================
    # Part II: DH Hardening Layer Methods
    # =========================================================================

    def _get_session_salt(self) -> bytes:
        """
        Compute session salt from bilateral receipt for DH key derivation.

        The salt binds the DH session to the specific Q proofs, preventing
        replay attacks and ensuring the session keys are unique to this
        protocol run.
        """
        if self.own_quad is None or self.other_quad is None:
            raise RuntimeError("Cannot derive session salt without bilateral receipt")
        return hash_proofs(
            self.own_quad.canonical_bytes(),
            self.other_quad.canonical_bytes(),
        )

    def create_dh_contribution(self) -> bytes:
        """
        Create a signed DH contribution message for key exchange.

        This should only be called after the protocol reaches COMPLETE state.
        The DH contribution includes:
        - Our X25519 public key
        - Hash of our Q proof (for binding)
        - Signature over the above

        Returns:
            Serialized DH contribution message (128 bytes)

        Raises:
            RuntimeError: If protocol not yet complete
        """
        if not self.is_complete or self.own_quad is None:
            raise RuntimeError("Cannot create DH contribution before protocol complete")

        # Initialize DH session if not already done
        if self.dh_session is None:
            is_initiator = self.party == Party.ALICE
            self.dh_session = DHSession.create(is_initiator=is_initiator)

        # Create the signed contribution
        q_proof_hash = self.own_quad.hash()
        dh_public = self.dh_session.public_key

        # Sign: DH_public || Q_proof_hash || "DH_CONTRIB"
        message_to_sign = dh_public.to_bytes() + q_proof_hash + b"DH_CONTRIB"
        signature = self.keypair.sign(message_to_sign)

        # Serialize the contribution
        self.own_dh_contribution = serialize_dh_message(dh_public, q_proof_hash, signature)
        return self.own_dh_contribution

    def receive_dh_contribution(self, dh_message: bytes) -> bool:
        """
        Process a received DH contribution from the counterparty.

        Args:
            dh_message: The serialized DH contribution (128 bytes)

        Returns:
            True if the contribution was valid and accepted

        Raises:
            RuntimeError: If protocol not yet complete
            ValueError: If message format is invalid
        """
        if not self.is_complete or self.other_quad is None:
            raise RuntimeError("Cannot receive DH contribution before protocol complete")

        # Deserialize
        dh_public, q_proof_hash, signature = deserialize_dh_message(dh_message)

        # Verify the Q proof hash matches what we have
        expected_hash = self.other_quad.hash()
        if q_proof_hash != expected_hash:
            return False

        # Verify the signature
        message_to_verify = dh_public.to_bytes() + q_proof_hash + b"DH_CONTRIB"
        if not self.counterparty_public_key.verify(message_to_verify, signature):
            return False

        self.other_dh_contribution = dh_message
        return True

    def complete_dh_exchange(self, peer_dh_message: Optional[bytes] = None) -> bool:
        """
        Complete the DH key exchange and derive session keys.

        This combines receiving the peer's contribution (if provided) and
        computing the shared secret and session keys.

        Args:
            peer_dh_message: Optional peer DH contribution. If not provided,
                            uses previously received contribution.

        Returns:
            True if exchange completed successfully

        Raises:
            RuntimeError: If protocol not complete or missing contributions
        """
        if not self.is_complete:
            raise RuntimeError("Cannot complete DH before protocol complete")

        # Process new contribution if provided
        if peer_dh_message is not None:
            if not self.receive_dh_contribution(peer_dh_message):
                return False

        # Ensure we have both contributions
        if self.dh_session is None or self.other_dh_contribution is None:
            raise RuntimeError("Missing DH contributions")

        # Extract peer's public key
        peer_public, _, _ = deserialize_dh_message(self.other_dh_contribution)

        # Compute session salt from bilateral receipt
        session_salt = self._get_session_salt()

        # Complete the exchange
        self.dh_session.complete_exchange(peer_public, session_salt)
        return True

    @property
    def is_dh_complete(self) -> bool:
        """Check if the DH exchange has completed and session keys are ready."""
        return self.dh_session is not None and self.dh_session.is_complete

    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """
        Encrypt data using the session key derived from DH exchange.

        Args:
            plaintext: Data to encrypt
            associated_data: Optional authenticated but not encrypted data

        Returns:
            Tuple of (nonce, ciphertext)

        Raises:
            RuntimeError: If DH exchange not complete
        """
        if not self.is_dh_complete:
            raise RuntimeError("DH exchange not complete")
        return self.dh_session.encrypt(plaintext, associated_data)

    def decrypt(
        self,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: Optional[bytes] = None,
    ) -> bytes:
        """
        Decrypt data using the session key derived from DH exchange.

        Args:
            nonce: Nonce from encryption
            ciphertext: Encrypted data with auth tag
            associated_data: Optional authenticated data (must match encryption)

        Returns:
            Decrypted plaintext

        Raises:
            RuntimeError: If DH exchange not complete
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        if not self.is_dh_complete:
            raise RuntimeError("DH exchange not complete")
        return self.dh_session.decrypt(nonce, ciphertext, associated_data)

    def __repr__(self) -> str:
        dh_status = "DH_READY" if self.is_dh_complete else "NO_DH"
        return f"TwoGenerals(party={self.party.name}, state={self.state.name}, {dh_status})"


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

        # Check if both complete with bilateral Q exchange
        # (need both own_quad AND other_quad for DH layer)
        if (alice.is_complete and bob.is_complete and
            alice.other_quad is not None and bob.other_quad is not None):
            break

    return alice, bob


# =============================================================================
# FULL SOLVE: TwoGeneralsV3 with Confirmation Phases
# =============================================================================
#
# The V3 protocol extends C→D→T→Q with mutual observation:
#
#   C → D → T → Q → Q_CONF → Q_CONF_FINAL → COMPLETE
#
# Key insight: Q alone proves "I can construct the fixpoint"
# But Q_CONF_FINAL proves "I know you know we both can construct it"
#
# This eliminates the last edge case where one party constructs Q
# but doesn't know if the counterparty has also received everything.
#
# Protocol extension:
#   Phase 5 (Q_CONF): "I have constructed Q" - flood after constructing Q_X
#   Phase 6 (Q_CONF_FINAL): "I received your Q_CONF, I'm locked in"
#   Decision: Need FinalReceipt (from both Q_CONFs) AND partner's Q_CONF_FINAL
# =============================================================================


@dataclass
class TwoGeneralsV3:
    """
    Two Generals Protocol V3 - FULL SOLVE with Confirmation Phases.

    Extends the basic C→D→T→Q protocol with mutual observation:
    - Q_CONF: "I have constructed Q and have all proofs"
    - Q_CONF_FINAL: "I received your Q_CONF, I'm locked in to ATTACK"

    The V3 protocol guarantees:
    - All properties of V1 (bilateral construction, symmetric outcomes)
    - PLUS mutual observation of readiness before final decision
    - Parties see each other's "behavior change" from Q_CONF to Q_CONF_FINAL
    - FinalReceipt is constructed LOCALLY after receiving partner's Q_CONF_FINAL

    This is the FULL SOLVE - no edge cases remain.

    Example usage:
        alice = TwoGeneralsV3.create(Party.ALICE, alice_keys, bob_keys.public_key)
        bob = TwoGeneralsV3.create(Party.BOB, bob_keys, alice_keys.public_key)

        # Exchange messages until both complete (includes confirmation phases)
        while True:
            for msg in alice.get_messages_to_send():
                bob.receive(msg)
            for msg in bob.get_messages_to_send():
                alice.receive(msg)
            if alice.is_fully_complete and bob.is_fully_complete:
                break

        assert alice.get_decision() == Decision.ATTACK
        assert bob.get_decision() == Decision.ATTACK
    """
    party: Party
    keypair: KeyPair
    counterparty_public_key: PublicKey
    phase: ProtocolPhaseV3 = field(default=ProtocolPhaseV3.INIT)

    # Base protocol artifacts (C → D → T → Q)
    own_commitment: Optional[Commitment] = None
    other_commitment: Optional[Commitment] = None
    own_double: Optional[DoubleProof] = None
    other_double: Optional[DoubleProof] = None
    own_triple: Optional[TripleProof] = None
    other_triple: Optional[TripleProof] = None
    own_quad: Optional[QuadProof] = None
    other_quad: Optional[QuadProof] = None

    # V3 confirmation artifacts
    own_quad_conf: Optional[QuadConfirmation] = None
    other_quad_conf: Optional[QuadConfirmation] = None
    own_quad_conf_final: Optional[QuadConfirmationFinal] = None
    other_quad_conf_final: Optional[QuadConfirmationFinal] = None

    # Final bilateral receipt (constructed locally)
    final_receipt: Optional[FinalReceipt] = None

    # Message sequencing
    sequence_counter: int = 0

    # Commitment message
    commitment_message: bytes = field(default=b"I will attack at dawn if you agree")

    @classmethod
    def create(
        cls,
        party: Party,
        keypair: KeyPair,
        counterparty_public_key: PublicKey,
        commitment_message: Optional[bytes] = None,
    ) -> TwoGeneralsV3:
        """Create a new TwoGeneralsV3 protocol instance."""
        instance = cls(
            party=party,
            keypair=keypair,
            counterparty_public_key=counterparty_public_key,
        )
        if commitment_message is not None:
            instance.commitment_message = commitment_message

        # Immediately create commitment
        instance._create_commitment()
        return instance

    # =========================================================================
    # Phase 1-4: Base Protocol (C → D → T → Q)
    # =========================================================================

    def _create_commitment(self) -> None:
        """Create and sign our initial commitment (Phase 1)."""
        signature = self.keypair.sign(self.commitment_message)
        self.own_commitment = Commitment(
            party=self.party,
            message=self.commitment_message,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.phase = ProtocolPhaseV3.COMMITMENT

    def _create_double_proof(self) -> None:
        """Create double proof (Phase 2)."""
        assert self.own_commitment is not None
        assert self.other_commitment is not None

        payload = (
            self.own_commitment.canonical_bytes() +
            self.other_commitment.canonical_bytes() +
            b"Both parties committed"
        )
        signature = self.keypair.sign(payload)

        self.own_double = DoubleProof(
            party=self.party,
            own_commitment=self.own_commitment,
            other_commitment=self.other_commitment,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.phase = ProtocolPhaseV3.DOUBLE

    def _create_triple_proof(self) -> None:
        """Create triple proof (Phase 3)."""
        assert self.own_double is not None
        assert self.other_double is not None

        payload = (
            self.own_double.canonical_bytes() +
            self.other_double.canonical_bytes() +
            b"Both parties have double proofs"
        )
        signature = self.keypair.sign(payload)

        self.own_triple = TripleProof(
            party=self.party,
            own_double=self.own_double,
            other_double=self.other_double,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.phase = ProtocolPhaseV3.TRIPLE

    def _create_quad_proof(self) -> None:
        """Create quad proof (Phase 4)."""
        assert self.own_triple is not None
        assert self.other_triple is not None

        payload = (
            self.own_triple.canonical_bytes() +
            self.other_triple.canonical_bytes() +
            b"Fixpoint achieved"
        )
        signature = self.keypair.sign(payload)

        self.own_quad = QuadProof(
            party=self.party,
            own_triple=self.own_triple,
            other_triple=self.other_triple,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.phase = ProtocolPhaseV3.QUAD

        # Immediately create Q_CONF after constructing Q
        self._create_quad_confirmation()

    # =========================================================================
    # Phase 5-6: V3 Confirmation Phases (Q_CONF → Q_CONF_FINAL)
    # =========================================================================

    def _create_quad_confirmation(self) -> None:
        """
        Create Q_CONF (Phase 5): "I have constructed my quad proof"

        This is created immediately after constructing Q_X.
        It signals to the counterparty that we've reached the epistemic fixpoint.
        """
        assert self.own_quad is not None

        # Confirmation hash proves we have all components
        confirmation_hash = hashlib.sha256(
            self.own_quad.canonical_bytes() +
            b"||Q_CONF||" +
            self.party.name.encode()
        ).digest()

        # Sign the confirmation
        message_to_sign = (
            self.own_quad.canonical_bytes() +
            b"||" +
            confirmation_hash +
            b"||Q_CONFIRMATION"
        )
        signature = self.keypair.sign(message_to_sign)

        self.own_quad_conf = QuadConfirmation(
            party=self.party,
            own_quad=self.own_quad,
            confirmation_hash=confirmation_hash,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.phase = ProtocolPhaseV3.Q_CONF

    def _create_quad_confirmation_final(self) -> None:
        """
        Create Q_CONF_FINAL (Phase 6): "I received your Q_CONF, I'm locked in"

        This requires:
        1. Our own Q_CONF (constructed after our Q)
        2. Partner's Q_CONF (received from network)

        This is the "behavior change" signal - counterparty observes us
        transition from Q_CONF to Q_CONF_FINAL and knows we're locked in.
        """
        assert self.own_quad_conf is not None
        assert self.other_quad_conf is not None

        # Sign the combined confirmations
        message_to_sign = (
            self.own_quad_conf.canonical_bytes() +
            b"||" +
            self.other_quad_conf.canonical_bytes() +
            b"||MUTUALLY_LOCKED_IN"
        )
        signature = self.keypair.sign(message_to_sign)

        self.own_quad_conf_final = QuadConfirmationFinal(
            party=self.party,
            own_quad_conf=self.own_quad_conf,
            other_quad_conf=self.other_quad_conf,
            ready_to_attack=True,
            signature=signature,
            public_key=self.keypair.public_key.to_bytes(),
        )
        self.phase = ProtocolPhaseV3.Q_CONF_FINAL

    def _construct_final_receipt(self) -> None:
        """
        Construct the FinalReceipt (PURELY LOCAL).

        This is constructed after receiving partner's Q_CONF_FINAL.
        The receipt is bilateral: identical for both parties.

        CRITICAL: No network messages after this - decision is deterministic.
        """
        assert self.own_quad is not None
        assert self.other_quad is not None
        assert self.own_quad_conf is not None
        assert self.other_quad_conf is not None
        assert self.own_quad_conf_final is not None
        assert self.other_quad_conf_final is not None

        # Compute deterministic receipt hash
        receipt_hash = FinalReceipt.compute_receipt_hash(
            self.own_quad_conf_final if self.party == Party.ALICE else self.other_quad_conf_final,
            self.other_quad_conf_final if self.party == Party.ALICE else self.own_quad_conf_final,
        )

        # Arrange by party for consistency
        if self.party == Party.ALICE:
            self.final_receipt = FinalReceipt(
                alice_quad=self.own_quad,
                bob_quad=self.other_quad,
                alice_conf=self.own_quad_conf,
                bob_conf=self.other_quad_conf,
                alice_conf_final=self.own_quad_conf_final,
                bob_conf_final=self.other_quad_conf_final,
                receipt_hash=receipt_hash,
            )
        else:
            self.final_receipt = FinalReceipt(
                alice_quad=self.other_quad,
                bob_quad=self.own_quad,
                alice_conf=self.other_quad_conf,
                bob_conf=self.own_quad_conf,
                alice_conf_final=self.other_quad_conf_final,
                bob_conf_final=self.own_quad_conf_final,
                receipt_hash=receipt_hash,
            )
        self.phase = ProtocolPhaseV3.COMPLETE

    # =========================================================================
    # Message Reception
    # =========================================================================

    def _verify_signature(self, signature: bytes, message: bytes, public_key_bytes: bytes) -> bool:
        """Verify a signature using the counterparty's public key."""
        try:
            pub_key = PublicKey.from_bytes(public_key_bytes)
            return pub_key.verify(message, signature)
        except Exception:
            return False

    def receive(self, msg) -> bool:
        """
        Process a received message from the counterparty.

        Handles all message types: base protocol (C/D/T/Q) and V3 confirmations.

        Returns:
            True if the message caused a state transition
        """
        # Extract payload if wrapped
        payload = msg.payload if hasattr(msg, 'payload') else msg

        # Route to appropriate handler
        if isinstance(payload, Commitment):
            return self._receive_commitment(payload)
        elif isinstance(payload, DoubleProof):
            return self._receive_double_proof(payload)
        elif isinstance(payload, TripleProof):
            return self._receive_triple_proof(payload)
        elif isinstance(payload, QuadProof):
            return self._receive_quad_proof(payload)
        elif isinstance(payload, QuadConfirmation):
            return self._receive_quad_conf(payload)
        elif isinstance(payload, QuadConfirmationFinal):
            return self._receive_quad_conf_final(payload)

        return False

    def _receive_commitment(self, commitment: Commitment) -> bool:
        """Process received commitment."""
        if commitment.party == self.party:
            return False
        if self.other_commitment is not None:
            return False

        if not self._verify_signature(
            commitment.signature,
            commitment.message,
            commitment.public_key,
        ):
            return False

        self.other_commitment = commitment

        if self.phase == ProtocolPhaseV3.COMMITMENT and self.own_commitment is not None:
            self._create_double_proof()
            return True

        return True

    def _receive_double_proof(self, double: DoubleProof) -> bool:
        """Process received double proof."""
        if double.party == self.party:
            return False
        if self.other_double is not None:
            return False

        payload = (
            double.own_commitment.canonical_bytes() +
            double.other_commitment.canonical_bytes() +
            b"Both parties committed"
        )
        if not self._verify_signature(double.signature, payload, double.public_key):
            return False

        # Extract embedded commitment if needed
        if self.other_commitment is None:
            self.other_commitment = double.own_commitment
            if self.phase == ProtocolPhaseV3.COMMITMENT and self.own_commitment is not None:
                self._create_double_proof()

        self.other_double = double

        if self.phase == ProtocolPhaseV3.DOUBLE and self.own_double is not None:
            self._create_triple_proof()
            return True

        return True

    def _receive_triple_proof(self, triple: TripleProof) -> bool:
        """Process received triple proof (with embedded proof extraction)."""
        if triple.party == self.party:
            return False
        if self.other_triple is not None:
            return False

        payload = (
            triple.own_double.canonical_bytes() +
            triple.other_double.canonical_bytes() +
            b"Both parties have double proofs"
        )
        if not self._verify_signature(triple.signature, payload, triple.public_key):
            return False

        # Extract embedded proofs (T_Y contains D_Y contains C_Y)
        if self.other_double is None:
            self.other_double = triple.own_double
            if self.other_commitment is None:
                self.other_commitment = triple.own_double.own_commitment

            # Cascade state updates
            if self.phase == ProtocolPhaseV3.COMMITMENT and self.own_commitment is not None:
                self._create_double_proof()
            if self.phase == ProtocolPhaseV3.DOUBLE and self.own_double is not None:
                self._create_triple_proof()

        self.other_triple = triple

        if self.phase == ProtocolPhaseV3.TRIPLE and self.own_triple is not None:
            self._create_quad_proof()
            return True

        return True

    def _receive_quad_proof(self, quad: QuadProof) -> bool:
        """Process received quad proof (with full cascade extraction)."""
        if quad.party == self.party:
            return False
        if self.other_quad is not None:
            return False

        payload = (
            quad.own_triple.canonical_bytes() +
            quad.other_triple.canonical_bytes() +
            b"Fixpoint achieved"
        )
        if not self._verify_signature(quad.signature, payload, quad.public_key):
            return False

        # Extract full proof chain
        if self.other_triple is None:
            self.other_triple = quad.own_triple
            if self.other_double is None:
                self.other_double = quad.own_triple.own_double
            if self.other_commitment is None:
                self.other_commitment = quad.own_triple.own_double.own_commitment

            # Cascade state updates
            if self.phase == ProtocolPhaseV3.COMMITMENT and self.own_commitment is not None:
                if self.other_commitment is None:
                    self.other_commitment = quad.own_triple.own_double.own_commitment
                self._create_double_proof()
            if self.phase == ProtocolPhaseV3.DOUBLE and self.own_double is not None:
                self._create_triple_proof()
            if self.phase == ProtocolPhaseV3.TRIPLE and self.own_triple is not None:
                self._create_quad_proof()

        self.other_quad = quad
        return True

    def _receive_quad_conf(self, quad_conf: QuadConfirmation) -> bool:
        """
        Process received Q_CONF from counterparty.

        Upon receiving partner's Q_CONF, if we have our own Q_CONF,
        we can create Q_CONF_FINAL (signaling readiness for decision).
        """
        if quad_conf.party == self.party:
            return False
        if self.other_quad_conf is not None:
            return False

        # Verify signature
        message_to_verify = (
            quad_conf.own_quad.canonical_bytes() +
            b"||" +
            quad_conf.confirmation_hash +
            b"||Q_CONFIRMATION"
        )
        if not self._verify_signature(quad_conf.signature, message_to_verify, quad_conf.public_key):
            return False

        self.other_quad_conf = quad_conf

        # Extract embedded quad if we don't have it
        if self.other_quad is None:
            self._receive_quad_proof(quad_conf.own_quad)

        # If we have our Q_CONF and now have partner's, create Q_CONF_FINAL
        if self.own_quad_conf is not None and self.phase == ProtocolPhaseV3.Q_CONF:
            self._create_quad_confirmation_final()
            return True

        return True

    def _receive_quad_conf_final(self, quad_conf_final: QuadConfirmationFinal) -> bool:
        """
        Process received Q_CONF_FINAL from counterparty.

        This is the "behavior change" signal - we now know the counterparty
        is locked in and will ATTACK. If we have our own Q_CONF_FINAL,
        we can construct the FinalReceipt.
        """
        if quad_conf_final.party == self.party:
            return False
        if self.other_quad_conf_final is not None:
            return False

        # Verify signature
        message_to_verify = (
            quad_conf_final.own_quad_conf.canonical_bytes() +
            b"||" +
            quad_conf_final.other_quad_conf.canonical_bytes() +
            b"||MUTUALLY_LOCKED_IN"
        )
        if not self._verify_signature(
            quad_conf_final.signature,
            message_to_verify,
            quad_conf_final.public_key,
        ):
            return False

        self.other_quad_conf_final = quad_conf_final

        # Extract embedded Q_CONF if we don't have it
        if self.other_quad_conf is None:
            self._receive_quad_conf(quad_conf_final.own_quad_conf)

        # If we have both Q_CONF_FINALs, construct FinalReceipt
        if self.own_quad_conf_final is not None and self.phase == ProtocolPhaseV3.Q_CONF_FINAL:
            self._construct_final_receipt()
            return True

        return True

    # =========================================================================
    # Message Generation
    # =========================================================================

    def get_messages_to_send(self) -> List[ProtocolMessage]:
        """
        Get messages to flood at the current phase.

        V3 sends the highest-level artifact available (it embeds all lower ones).
        """
        messages = []
        self.sequence_counter += 1

        # Determine what to send based on phase
        if self.phase == ProtocolPhaseV3.COMPLETE or self.phase == ProtocolPhaseV3.Q_CONF_FINAL:
            # Send Q_CONF_FINAL (embeds Q_CONF which embeds Q)
            if self.own_quad_conf_final is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=ProtocolState.COMPLETE,  # Map to base state
                    payload=self.own_quad_conf_final,
                    sequence=self.sequence_counter,
                ))
        elif self.phase == ProtocolPhaseV3.Q_CONF:
            # Send Q_CONF (embeds Q)
            if self.own_quad_conf is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=ProtocolState.QUAD,
                    payload=self.own_quad_conf,
                    sequence=self.sequence_counter,
                ))
        elif self.phase == ProtocolPhaseV3.QUAD:
            # Send Q
            if self.own_quad is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=ProtocolState.QUAD,
                    payload=self.own_quad,
                    sequence=self.sequence_counter,
                ))
        elif self.phase == ProtocolPhaseV3.TRIPLE:
            if self.own_triple is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=ProtocolState.TRIPLE,
                    payload=self.own_triple,
                    sequence=self.sequence_counter,
                ))
        elif self.phase == ProtocolPhaseV3.DOUBLE:
            if self.own_double is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=ProtocolState.DOUBLE,
                    payload=self.own_double,
                    sequence=self.sequence_counter,
                ))
        elif self.phase == ProtocolPhaseV3.COMMITMENT:
            if self.own_commitment is not None:
                messages.append(ProtocolMessage(
                    sender=self.party,
                    state=ProtocolState.COMMITMENT,
                    payload=self.own_commitment,
                    sequence=self.sequence_counter,
                ))

        return messages

    # =========================================================================
    # Decision Logic
    # =========================================================================

    @property
    def is_complete(self) -> bool:
        """
        Check if the base protocol (C→D→T→Q) is complete.

        This is the "naive solution" completion check.
        For FULL SOLVE, use is_fully_complete instead.
        """
        return self.own_quad is not None

    @property
    def is_fully_complete(self) -> bool:
        """
        Check if the FULL SOLVE is complete.

        This requires:
        1. FinalReceipt constructed (proves bilateral completion)
        2. Partner's Q_CONF_FINAL received (proves partner locked in)

        This is the FULL SOLVE completion check - no edge cases.
        """
        return (
            self.final_receipt is not None and
            self.other_quad_conf_final is not None
        )

    @property
    def can_attack(self) -> bool:
        """Check if this party can safely ATTACK (FULL SOLVE)."""
        return self.is_fully_complete

    def get_decision(self) -> Decision:
        """
        Get the final decision.

        FULL SOLVE decision rule:
        - Have FinalReceipt AND partner's Q_CONF_FINAL → ATTACK
        - Missing either → ABORT

        The structural guarantee:
        - FinalReceipt exists → both parties sent Q_CONF_FINAL
        - Q_CONF_FINAL_X exists → X has Y's Q_CONF
        - Q_CONF_X exists → X has Q_X
        - Therefore: BOTH have Q, BOTH locked in, BOTH will ATTACK
        """
        if self.is_fully_complete:
            return Decision.ATTACK
        return Decision.ABORT

    def abort(self) -> None:
        """Abort the protocol (e.g., deadline passed)."""
        if self.phase != ProtocolPhaseV3.COMPLETE:
            self.phase = ProtocolPhaseV3.ABORTED

    def get_final_receipt(self) -> Optional[FinalReceipt]:
        """Get the FinalReceipt if fully complete."""
        return self.final_receipt

    def __repr__(self) -> str:
        return f"TwoGeneralsV3(party={self.party.name}, phase={self.phase.name})"


def run_protocol_simulation_v3(
    alice_keypair: KeyPair,
    bob_keypair: KeyPair,
    max_rounds: int = 100,
    message_filter: Optional[Callable[[ProtocolMessage], bool]] = None,
) -> tuple[TwoGeneralsV3, TwoGeneralsV3]:
    """
    Run a complete V3 protocol simulation between Alice and Bob.

    This includes the full confirmation phases (Q_CONF → Q_CONF_FINAL).

    Args:
        alice_keypair: Alice's signing keypair
        bob_keypair: Bob's signing keypair
        max_rounds: Maximum number of message exchange rounds
        message_filter: Optional filter to simulate message loss

    Returns:
        Tuple of (alice_state, bob_state) after simulation
    """
    alice = TwoGeneralsV3.create(
        party=Party.ALICE,
        keypair=alice_keypair,
        counterparty_public_key=bob_keypair.public_key,
    )
    bob = TwoGeneralsV3.create(
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

        # Check if both fully complete
        if alice.is_fully_complete and bob.is_fully_complete:
            break

    return alice, bob
