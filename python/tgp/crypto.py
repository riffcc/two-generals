"""
TGP Cryptographic Primitives

Part I: Pure Epistemic Protocol
- Ed25519 signatures for proof stapling

Part II: DH Hardening Layer (Production Security)
- X25519 Diffie-Hellman key exchange
- HKDF-SHA256 key derivation
- ChaCha20-Poly1305 authenticated encryption

This module provides the cryptographic foundation for both the theoretical
result (signatures only) and practical deployment (full encryption).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass, field
from typing import Optional, Tuple, Union

# Use cryptography library for all primitives
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

# Constants
ED25519_PUBLIC_KEY_SIZE = 32
ED25519_SIGNATURE_SIZE = 64
X25519_PUBLIC_KEY_SIZE = 32
X25519_SHARED_SECRET_SIZE = 32
CHACHA20_KEY_SIZE = 32
CHACHA20_NONCE_SIZE = 12
CHACHA20_TAG_SIZE = 16

# Domain separation constants for HKDF
DOMAIN_SESSION_KEY = b"TGP-SESSION-KEY-V1"
DOMAIN_ENCRYPTION = b"TGP-ENCRYPT-V1"
DOMAIN_MAC = b"TGP-MAC-V1"


# =============================================================================
# Part I: Ed25519 Signatures (Pure Epistemic Protocol)
# =============================================================================


@dataclass(frozen=True)
class PublicKey:
    """Ed25519 public key for signature verification."""

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != ED25519_PUBLIC_KEY_SIZE:
            raise ValueError(f"Public key must be {ED25519_PUBLIC_KEY_SIZE} bytes")

    def verify(self, message: bytes, signature: bytes) -> bool:
        """Verify a signature against this public key.

        Args:
            message: The message that was signed
            signature: The Ed25519 signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(self.raw)
            pub.verify(signature, message)
            return True
        except Exception:
            return False

    def to_bytes(self) -> bytes:
        """Return raw public key bytes."""
        return self.raw

    @classmethod
    def from_bytes(cls, data: bytes) -> "PublicKey":
        """Create PublicKey from raw bytes."""
        return cls(raw=data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PublicKey):
            return False
        return self.raw == other.raw

    def __hash__(self) -> int:
        return hash(self.raw)


@dataclass
class KeyPair:
    """Ed25519 signing keypair.

    Provides both signing capabilities and the associated public key
    for distribution and verification.
    """

    _private_key: ed25519.Ed25519PrivateKey = field(repr=False)
    public_key: PublicKey = field(init=False)

    def __post_init__(self) -> None:
        pub_bytes = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        object.__setattr__(self, "public_key", PublicKey(raw=pub_bytes))

    @classmethod
    def generate(cls) -> "KeyPair":
        """Generate a new random Ed25519 keypair."""
        private = ed25519.Ed25519PrivateKey.generate()
        return cls(_private_key=private)

    @classmethod
    def from_seed(cls, seed: bytes) -> "KeyPair":
        """Create keypair from 32-byte seed (deterministic).

        Args:
            seed: 32-byte seed for deterministic key generation

        Returns:
            KeyPair generated from seed
        """
        if len(seed) != 32:
            raise ValueError("Seed must be 32 bytes")
        private = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
        return cls(_private_key=private)

    def sign(self, message: bytes) -> bytes:
        """Sign a message using this keypair.

        Args:
            message: The message to sign

        Returns:
            64-byte Ed25519 signature
        """
        return self._private_key.sign(message)

    def to_seed(self) -> bytes:
        """Export private key as 32-byte seed."""
        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )


# =============================================================================
# Part II: X25519 Diffie-Hellman (DH Hardening Layer)
# =============================================================================


@dataclass(frozen=True)
class DHPublicKey:
    """X25519 public key for Diffie-Hellman key exchange."""

    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != X25519_PUBLIC_KEY_SIZE:
            raise ValueError(f"DH public key must be {X25519_PUBLIC_KEY_SIZE} bytes")

    def to_bytes(self) -> bytes:
        """Return raw public key bytes."""
        return self.raw

    @classmethod
    def from_bytes(cls, data: bytes) -> "DHPublicKey":
        """Create DHPublicKey from raw bytes."""
        return cls(raw=data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DHPublicKey):
            return False
        return self.raw == other.raw

    def __hash__(self) -> int:
        return hash(self.raw)


@dataclass
class DHKeyPair:
    """X25519 keypair for Diffie-Hellman key exchange.

    Used in Part II (DH Hardening) to derive shared secrets
    after the epistemic proof phase completes.
    """

    _private_key: x25519.X25519PrivateKey = field(repr=False)
    public_key: DHPublicKey = field(init=False)

    def __post_init__(self) -> None:
        pub_bytes = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        object.__setattr__(self, "public_key", DHPublicKey(raw=pub_bytes))

    @classmethod
    def generate(cls) -> "DHKeyPair":
        """Generate a new random X25519 keypair (ephemeral)."""
        private = x25519.X25519PrivateKey.generate()
        return cls(_private_key=private)

    @classmethod
    def from_seed(cls, seed: bytes) -> "DHKeyPair":
        """Create DH keypair from 32-byte seed (deterministic).

        Args:
            seed: 32-byte seed for deterministic key generation

        Returns:
            DHKeyPair generated from seed
        """
        if len(seed) != 32:
            raise ValueError("Seed must be 32 bytes")
        private = x25519.X25519PrivateKey.from_private_bytes(seed)
        return cls(_private_key=private)

    def exchange(self, peer_public: DHPublicKey) -> bytes:
        """Perform X25519 key exchange with peer's public key.

        Args:
            peer_public: The peer's X25519 public key

        Returns:
            32-byte shared secret (raw X25519 output)
        """
        peer_key = x25519.X25519PublicKey.from_public_bytes(peer_public.raw)
        return self._private_key.exchange(peer_key)


# =============================================================================
# Part II: HKDF-SHA256 Key Derivation
# =============================================================================


def hkdf_derive(
    shared_secret: bytes,
    info: bytes,
    salt: Optional[bytes] = None,
    length: int = 32,
) -> bytes:
    """Derive a key using HKDF-SHA256.

    Args:
        shared_secret: The input keying material (e.g., DH shared secret)
        info: Context and application-specific info string
        salt: Optional salt (uses zeros if None)
        length: Desired output length in bytes (default 32)

    Returns:
        Derived key of specified length
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
        backend=default_backend(),
    )
    return hkdf.derive(shared_secret)


@dataclass(frozen=True)
class SessionKeys:
    """Symmetric keys derived from DH shared secret.

    Contains all keys needed for bidirectional authenticated encryption.
    """

    encryption_key: bytes
    mac_key: bytes
    nonce_counter: int = 0

    def __post_init__(self) -> None:
        if len(self.encryption_key) != CHACHA20_KEY_SIZE:
            raise ValueError(f"Encryption key must be {CHACHA20_KEY_SIZE} bytes")
        if len(self.mac_key) != 32:
            raise ValueError("MAC key must be 32 bytes")

    @classmethod
    def derive_from_shared_secret(
        cls,
        shared_secret: bytes,
        session_salt: bytes,
        is_initiator: bool,
    ) -> "SessionKeys":
        """Derive session keys from DH shared secret.

        Uses HKDF to expand the shared secret into multiple keys.
        The is_initiator flag ensures both parties derive keys in
        compatible order (initiator and responder get matching keys).

        Args:
            shared_secret: 32-byte X25519 shared secret
            session_salt: Salt derived from Q proofs (binds to session)
            is_initiator: True if this party initiated the exchange

        Returns:
            SessionKeys with encryption and MAC keys
        """
        # Derive master key first
        master = hkdf_derive(
            shared_secret=shared_secret,
            info=DOMAIN_SESSION_KEY,
            salt=session_salt,
            length=64,
        )

        # Split into encryption and MAC keys
        # Both parties derive the same keys because shared_secret is symmetric
        encryption_key = hkdf_derive(
            shared_secret=master,
            info=DOMAIN_ENCRYPTION + (b"\x00" if is_initiator else b"\x01"),
            salt=None,
            length=CHACHA20_KEY_SIZE,
        )

        mac_key = hkdf_derive(
            shared_secret=master,
            info=DOMAIN_MAC + (b"\x00" if is_initiator else b"\x01"),
            salt=None,
            length=32,
        )

        return cls(encryption_key=encryption_key, mac_key=mac_key)


# =============================================================================
# Part II: ChaCha20-Poly1305 Authenticated Encryption
# =============================================================================


@dataclass
class AEAD:
    """ChaCha20-Poly1305 Authenticated Encryption with Associated Data.

    Provides confidentiality and integrity for TGP messages after
    the DH handshake completes.
    """

    key: bytes
    _cipher: ChaCha20Poly1305 = field(init=False, repr=False)
    _nonce_counter: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if len(self.key) != CHACHA20_KEY_SIZE:
            raise ValueError(f"Key must be {CHACHA20_KEY_SIZE} bytes")
        self._cipher = ChaCha20Poly1305(self.key)

    def _next_nonce(self) -> bytes:
        """Generate next nonce using counter mode.

        Returns a 12-byte nonce with incrementing counter.
        """
        nonce = self._nonce_counter.to_bytes(CHACHA20_NONCE_SIZE, "little")
        self._nonce_counter += 1
        if self._nonce_counter >= 2**96:
            raise RuntimeError("Nonce counter overflow - key rotation required")
        return nonce

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: Optional[bytes] = None,
        nonce: Optional[bytes] = None,
    ) -> Tuple[bytes, bytes]:
        """Encrypt plaintext with authentication.

        Args:
            plaintext: Data to encrypt
            associated_data: Optional authenticated but not encrypted data
            nonce: Optional explicit nonce (uses counter if None)

        Returns:
            Tuple of (nonce, ciphertext_with_tag)
        """
        if nonce is None:
            nonce = self._next_nonce()
        elif len(nonce) != CHACHA20_NONCE_SIZE:
            raise ValueError(f"Nonce must be {CHACHA20_NONCE_SIZE} bytes")

        ciphertext = self._cipher.encrypt(nonce, plaintext, associated_data)
        return (nonce, ciphertext)

    def decrypt(
        self,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: Optional[bytes] = None,
    ) -> bytes:
        """Decrypt and verify ciphertext.

        Args:
            nonce: The nonce used during encryption
            ciphertext: Encrypted data with auth tag
            associated_data: Optional associated data (must match encryption)

        Returns:
            Decrypted plaintext

        Raises:
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        if len(nonce) != CHACHA20_NONCE_SIZE:
            raise ValueError(f"Nonce must be {CHACHA20_NONCE_SIZE} bytes")
        return self._cipher.decrypt(nonce, ciphertext, associated_data)


# =============================================================================
# Part II: Complete DH Handshake Session
# =============================================================================


@dataclass
class DHSession:
    """Complete DH session including key exchange and encryption setup.

    This encapsulates the full DH hardening layer workflow:
    1. Generate ephemeral DH keypair
    2. Exchange public keys (after Q proof constructed)
    3. Derive shared secret
    4. Derive session keys via HKDF
    5. Initialize AEAD for encrypted communication
    """

    dh_keypair: DHKeyPair
    is_initiator: bool
    _peer_public: Optional[DHPublicKey] = field(default=None, repr=False)
    _shared_secret: Optional[bytes] = field(default=None, repr=False)
    _session_keys: Optional[SessionKeys] = field(default=None, repr=False)
    _aead: Optional[AEAD] = field(default=None, repr=False)

    @classmethod
    def create(cls, is_initiator: bool) -> "DHSession":
        """Create a new DH session with fresh ephemeral keys.

        Args:
            is_initiator: True if this party initiated the protocol

        Returns:
            DHSession ready for key exchange
        """
        return cls(
            dh_keypair=DHKeyPair.generate(),
            is_initiator=is_initiator,
        )

    @property
    def public_key(self) -> DHPublicKey:
        """Get this session's DH public key for sending to peer."""
        return self.dh_keypair.public_key

    @property
    def is_complete(self) -> bool:
        """Check if the DH handshake is complete."""
        return self._aead is not None

    def complete_exchange(
        self,
        peer_public: DHPublicKey,
        session_salt: bytes,
    ) -> None:
        """Complete the DH exchange with peer's public key.

        Args:
            peer_public: Peer's X25519 public key
            session_salt: Salt from Q proofs (hash(Q_A || Q_B))
        """
        self._peer_public = peer_public
        self._shared_secret = self.dh_keypair.exchange(peer_public)
        self._session_keys = SessionKeys.derive_from_shared_secret(
            shared_secret=self._shared_secret,
            session_salt=session_salt,
            is_initiator=self.is_initiator,
        )
        self._aead = AEAD(key=self._session_keys.encryption_key)

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: Optional[bytes] = None,
    ) -> Tuple[bytes, bytes]:
        """Encrypt data using the session key.

        Args:
            plaintext: Data to encrypt
            associated_data: Optional AAD

        Returns:
            Tuple of (nonce, ciphertext)

        Raises:
            RuntimeError: If DH exchange not complete
        """
        if self._aead is None:
            raise RuntimeError("DH exchange not complete")
        return self._aead.encrypt(plaintext, associated_data)

    def decrypt(
        self,
        nonce: bytes,
        ciphertext: bytes,
        associated_data: Optional[bytes] = None,
    ) -> bytes:
        """Decrypt data using the session key.

        Args:
            nonce: Nonce from encryption
            ciphertext: Encrypted data
            associated_data: Optional AAD

        Returns:
            Decrypted plaintext

        Raises:
            RuntimeError: If DH exchange not complete
            cryptography.exceptions.InvalidTag: If authentication fails
        """
        if self._aead is None:
            raise RuntimeError("DH exchange not complete")
        return self._aead.decrypt(nonce, ciphertext, associated_data)


# =============================================================================
# Utility Functions
# =============================================================================


def random_bytes(n: int) -> bytes:
    """Generate cryptographically secure random bytes."""
    return secrets.token_bytes(n)


def constant_time_compare(a: bytes, b: bytes) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(a, b)


def hash_proofs(*proofs: bytes) -> bytes:
    """Hash concatenated proofs for session salt derivation.

    Used to bind DH session to the epistemic proofs (Q_A, Q_B).
    """
    h = hashlib.sha256()
    for proof in proofs:
        h.update(proof)
    return h.digest()


# =============================================================================
# Wire Format Helpers
# =============================================================================


def serialize_dh_message(
    dh_public: DHPublicKey,
    q_proof_hash: bytes,
    signature: bytes,
) -> bytes:
    """Serialize a DH contribution message.

    Format:
        dh_public (32 bytes) || q_proof_hash (32 bytes) || signature (64 bytes)
    """
    return dh_public.raw + q_proof_hash + signature


def deserialize_dh_message(data: bytes) -> Tuple[DHPublicKey, bytes, bytes]:
    """Deserialize a DH contribution message.

    Args:
        data: 128-byte DH message

    Returns:
        Tuple of (dh_public, q_proof_hash, signature)
    """
    if len(data) != 128:
        raise ValueError("DH message must be 128 bytes")
    dh_public = DHPublicKey.from_bytes(data[:32])
    q_proof_hash = data[32:64]
    signature = data[64:128]
    return (dh_public, q_proof_hash, signature)
