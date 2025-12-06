//! Cryptographic primitives for the Two Generals Protocol.
//!
//! This module provides Ed25519 signature operations for the pure epistemic
//! protocol (Part I). For production with DH hardening (Part II), additional
//! X25519 and AEAD primitives would be added.
//!
//! # Security
//!
//! - Uses `ed25519-dalek` for Ed25519 signatures
//! - Uses `blake3` for hashing (faster than SHA-256, equally secure)
//! - All secret keys are zeroized on drop

#[cfg(feature = "no_std")]
use alloc::{vec, vec::Vec};

use ed25519_dalek::{
    Signature as DalekSignature, Signer as DalekSigner, SigningKey, Verifier as DalekVerifier,
    VerifyingKey,
};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};

use crate::error::{Error, Result};

/// Ed25519 public key for signature verification.
///
/// Public keys are 32 bytes (256 bits) as per the Ed25519 specification.
#[derive(Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PublicKey {
    bytes: [u8; 32],
}

impl PublicKey {
    /// Create a public key from raw bytes.
    ///
    /// # Errors
    ///
    /// Returns an error if the bytes don't form a valid public key.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        if bytes.len() != 32 {
            return Err(Error::Crypto("public key must be 32 bytes".into()));
        }

        let mut arr = [0u8; 32];
        arr.copy_from_slice(bytes);

        // Validate that these bytes form a valid Ed25519 public key
        VerifyingKey::from_bytes(&arr).map_err(|_| Error::Crypto("invalid public key".into()))?;

        Ok(Self { bytes: arr })
    }

    /// Get the raw bytes of this public key.
    #[must_use]
    pub const fn as_bytes(&self) -> &[u8; 32] {
        &self.bytes
    }

    /// Verify a signature over a message.
    ///
    /// # Errors
    ///
    /// Returns `Error::InvalidSignature` if the signature is invalid.
    pub fn verify(&self, message: &[u8], signature: &Signature) -> Result<()> {
        let verifying_key = VerifyingKey::from_bytes(&self.bytes)
            .map_err(|_| Error::Crypto("invalid public key".into()))?;

        let sig = DalekSignature::from_bytes(&signature.bytes);

        verifying_key
            .verify(message, &sig)
            .map_err(|_| Error::InvalidSignature)
    }
}

impl core::fmt::Debug for PublicKey {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "PublicKey({}...)", hex::encode(&self.bytes[..4]))
    }
}

impl core::fmt::Display for PublicKey {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{}", hex::encode(&self.bytes))
    }
}

/// Ed25519 signature (64 bytes).
#[derive(Clone, PartialEq, Eq, Hash)]
pub struct Signature {
    bytes: [u8; 64],
}

// Manual Serialize/Deserialize for [u8; 64] since serde doesn't support arrays > 32
impl serde::Serialize for Signature {
    fn serialize<S>(&self, serializer: S) -> core::result::Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serde_bytes::serialize(&self.bytes[..], serializer)
    }
}

impl<'de> serde::Deserialize<'de> for Signature {
    fn deserialize<D>(deserializer: D) -> core::result::Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let bytes: Vec<u8> = serde_bytes::deserialize(deserializer)?;
        if bytes.len() != 64 {
            return Err(serde::de::Error::custom("signature must be 64 bytes"));
        }
        let mut arr = [0u8; 64];
        arr.copy_from_slice(&bytes);
        Ok(Self { bytes: arr })
    }
}

impl Signature {
    /// Create a signature from raw bytes.
    ///
    /// # Errors
    ///
    /// Returns an error if the signature is not 64 bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        if bytes.len() != 64 {
            return Err(Error::Crypto("signature must be 64 bytes".into()));
        }

        let mut arr = [0u8; 64];
        arr.copy_from_slice(bytes);
        Ok(Self { bytes: arr })
    }

    /// Get the raw bytes of this signature.
    #[must_use]
    pub const fn as_bytes(&self) -> &[u8; 64] {
        &self.bytes
    }
}

impl core::fmt::Debug for Signature {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "Signature({}...)", hex::encode(&self.bytes[..8]))
    }
}

/// Ed25519 key pair for signing.
///
/// Contains both the secret signing key and the public verification key.
pub struct KeyPair {
    signing_key: SigningKey,
    public_key: PublicKey,
}

impl KeyPair {
    /// Generate a new random key pair.
    ///
    /// Uses the operating system's cryptographically secure random number generator.
    #[must_use]
    pub fn generate() -> Self {
        let signing_key = SigningKey::generate(&mut OsRng);
        let verifying_key = signing_key.verifying_key();

        Self {
            signing_key,
            public_key: PublicKey {
                bytes: verifying_key.to_bytes(),
            },
        }
    }

    /// Create a key pair from a 32-byte seed.
    ///
    /// This is deterministic: the same seed always produces the same key pair.
    /// Useful for testing and reproducibility.
    ///
    /// # Errors
    ///
    /// Returns an error if the seed is not 32 bytes.
    pub fn from_seed(seed: &[u8]) -> Result<Self> {
        if seed.len() != 32 {
            return Err(Error::Crypto("seed must be 32 bytes".into()));
        }

        let mut arr = [0u8; 32];
        arr.copy_from_slice(seed);

        let signing_key = SigningKey::from_bytes(&arr);
        let verifying_key = signing_key.verifying_key();

        Ok(Self {
            signing_key,
            public_key: PublicKey {
                bytes: verifying_key.to_bytes(),
            },
        })
    }

    /// Get the public key component of this key pair.
    #[must_use]
    pub fn public_key(&self) -> &PublicKey {
        &self.public_key
    }

    /// Sign a message.
    ///
    /// Returns a 64-byte Ed25519 signature.
    pub fn sign(&self, message: &[u8]) -> Signature {
        let sig = self.signing_key.sign(message);
        Signature {
            bytes: sig.to_bytes(),
        }
    }

    /// Verify a signature (convenience method using the public key).
    ///
    /// # Errors
    ///
    /// Returns `Error::InvalidSignature` if the signature is invalid.
    pub fn verify(&self, message: &[u8], signature: &Signature) -> Result<()> {
        self.public_key.verify(message, signature)
    }
}

impl core::fmt::Debug for KeyPair {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "KeyPair(public={:?})", self.public_key)
    }
}

impl Clone for KeyPair {
    fn clone(&self) -> Self {
        Self {
            signing_key: SigningKey::from_bytes(&self.signing_key.to_bytes()),
            public_key: self.public_key.clone(),
        }
    }
}

/// High-level signing interface for proof construction.
///
/// Wraps a `KeyPair` with convenience methods for signing protocol artifacts.
pub struct Signer {
    keypair: KeyPair,
}

impl Signer {
    /// Create a new signer with the given key pair.
    #[must_use]
    pub const fn new(keypair: KeyPair) -> Self {
        Self { keypair }
    }

    /// Get the public key for this signer.
    #[must_use]
    pub fn public_key(&self) -> &PublicKey {
        self.keypair.public_key()
    }

    /// Sign a raw message.
    pub fn sign(&self, message: &[u8]) -> Signature {
        self.keypair.sign(message)
    }

    /// Sign a commitment (Phase 1).
    pub fn sign_commitment(&self, intent_message: &[u8]) -> Signature {
        self.sign(intent_message)
    }

    /// Sign a double proof (Phase 2).
    ///
    /// `D_X = Sign_X(C_X || C_Y || "BOTH_COMMITTED")`
    pub fn sign_double_proof(
        &self,
        own_commitment_bytes: &[u8],
        other_commitment_bytes: &[u8],
    ) -> Signature {
        let mut message = Vec::with_capacity(
            own_commitment_bytes.len() + other_commitment_bytes.len() + 20,
        );
        message.extend_from_slice(own_commitment_bytes);
        message.extend_from_slice(b"||");
        message.extend_from_slice(other_commitment_bytes);
        message.extend_from_slice(b"||BOTH_COMMITTED");
        self.sign(&message)
    }

    /// Sign a triple proof (Phase 3).
    ///
    /// `T_X = Sign_X(D_X || D_Y || "BOTH_HAVE_DOUBLE")`
    pub fn sign_triple_proof(
        &self,
        own_double_bytes: &[u8],
        other_double_bytes: &[u8],
    ) -> Signature {
        let mut message =
            Vec::with_capacity(own_double_bytes.len() + other_double_bytes.len() + 22);
        message.extend_from_slice(own_double_bytes);
        message.extend_from_slice(b"||");
        message.extend_from_slice(other_double_bytes);
        message.extend_from_slice(b"||BOTH_HAVE_DOUBLE");
        self.sign(&message)
    }

    /// Sign a quad proof (Phase 4 — Fixpoint).
    ///
    /// `Q_X = Sign_X(T_X || T_Y || "FIXPOINT_ACHIEVED")`
    pub fn sign_quad_proof(
        &self,
        own_triple_bytes: &[u8],
        other_triple_bytes: &[u8],
    ) -> Signature {
        let mut message =
            Vec::with_capacity(own_triple_bytes.len() + other_triple_bytes.len() + 24);
        message.extend_from_slice(own_triple_bytes);
        message.extend_from_slice(b"||");
        message.extend_from_slice(other_triple_bytes);
        message.extend_from_slice(b"||FIXPOINT_ACHIEVED");
        self.sign(&message)
    }
}

/// High-level verification interface for proof validation.
pub struct Verifier {
    public_key: PublicKey,
}

impl Verifier {
    /// Create a new verifier with the given public key.
    #[must_use]
    pub const fn new(public_key: PublicKey) -> Self {
        Self { public_key }
    }

    /// Verify a raw signature.
    ///
    /// # Errors
    ///
    /// Returns `Error::InvalidSignature` if the signature is invalid.
    pub fn verify(&self, message: &[u8], signature: &Signature) -> Result<()> {
        self.public_key.verify(message, signature)
    }

    /// Verify a commitment signature (Phase 1).
    ///
    /// # Errors
    ///
    /// Returns `Error::InvalidSignature` if the signature is invalid.
    pub fn verify_commitment(&self, signature: &Signature, message: &[u8]) -> Result<()> {
        self.verify(message, signature)
    }

    /// Verify a double proof signature (Phase 2).
    ///
    /// # Errors
    ///
    /// Returns `Error::InvalidSignature` if the signature is invalid.
    pub fn verify_double_proof(
        &self,
        signature: &Signature,
        own_commitment_bytes: &[u8],
        other_commitment_bytes: &[u8],
    ) -> Result<()> {
        let mut message = Vec::with_capacity(
            own_commitment_bytes.len() + other_commitment_bytes.len() + 20,
        );
        message.extend_from_slice(own_commitment_bytes);
        message.extend_from_slice(b"||");
        message.extend_from_slice(other_commitment_bytes);
        message.extend_from_slice(b"||BOTH_COMMITTED");
        self.verify(&message, signature)
    }

    /// Verify a triple proof signature (Phase 3).
    ///
    /// # Errors
    ///
    /// Returns `Error::InvalidSignature` if the signature is invalid.
    pub fn verify_triple_proof(
        &self,
        signature: &Signature,
        own_double_bytes: &[u8],
        other_double_bytes: &[u8],
    ) -> Result<()> {
        let mut message =
            Vec::with_capacity(own_double_bytes.len() + other_double_bytes.len() + 22);
        message.extend_from_slice(own_double_bytes);
        message.extend_from_slice(b"||");
        message.extend_from_slice(other_double_bytes);
        message.extend_from_slice(b"||BOTH_HAVE_DOUBLE");
        self.verify(&message, signature)
    }

    /// Verify a quad proof signature (Phase 4).
    ///
    /// # Errors
    ///
    /// Returns `Error::InvalidSignature` if the signature is invalid.
    pub fn verify_quad_proof(
        &self,
        signature: &Signature,
        own_triple_bytes: &[u8],
        other_triple_bytes: &[u8],
    ) -> Result<()> {
        let mut message =
            Vec::with_capacity(own_triple_bytes.len() + other_triple_bytes.len() + 24);
        message.extend_from_slice(own_triple_bytes);
        message.extend_from_slice(b"||");
        message.extend_from_slice(other_triple_bytes);
        message.extend_from_slice(b"||FIXPOINT_ACHIEVED");
        self.verify(&message, signature)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keypair_generation() {
        let kp = KeyPair::generate();
        assert_eq!(kp.public_key().as_bytes().len(), 32);
    }

    #[test]
    fn keypair_from_seed_deterministic() {
        let seed = [0x42u8; 32];
        let kp1 = KeyPair::from_seed(&seed).unwrap();
        let kp2 = KeyPair::from_seed(&seed).unwrap();
        assert_eq!(kp1.public_key().as_bytes(), kp2.public_key().as_bytes());
    }

    #[test]
    fn sign_and_verify() {
        let kp = KeyPair::generate();
        let message = b"I will attack at dawn if you agree";
        let signature = kp.sign(message);

        assert!(kp.verify(message, &signature).is_ok());
    }

    #[test]
    fn verify_wrong_message_fails() {
        let kp = KeyPair::generate();
        let message = b"I will attack at dawn if you agree";
        let signature = kp.sign(message);

        assert!(kp.verify(b"wrong message", &signature).is_err());
    }

    #[test]
    fn verify_wrong_key_fails() {
        let kp1 = KeyPair::generate();
        let kp2 = KeyPair::generate();
        let message = b"I will attack at dawn if you agree";
        let signature = kp1.sign(message);

        assert!(kp2.verify(message, &signature).is_err());
    }

    #[test]
    fn signer_verifier_roundtrip() {
        let kp = KeyPair::generate();
        let signer = Signer::new(kp.clone());
        let verifier = Verifier::new(kp.public_key().clone());

        let message = b"commitment message";
        let sig = signer.sign_commitment(message);
        assert!(verifier.verify_commitment(&sig, message).is_ok());
    }

    #[test]
    fn double_proof_signing() {
        let kp = KeyPair::generate();
        let signer = Signer::new(kp.clone());
        let verifier = Verifier::new(kp.public_key().clone());

        let own_commitment = b"own commitment bytes";
        let other_commitment = b"other commitment bytes";

        let sig = signer.sign_double_proof(own_commitment, other_commitment);
        assert!(verifier
            .verify_double_proof(&sig, own_commitment, other_commitment)
            .is_ok());
    }

    #[test]
    fn triple_proof_signing() {
        let kp = KeyPair::generate();
        let signer = Signer::new(kp.clone());
        let verifier = Verifier::new(kp.public_key().clone());

        let own_double = b"own double proof bytes";
        let other_double = b"other double proof bytes";

        let sig = signer.sign_triple_proof(own_double, other_double);
        assert!(verifier
            .verify_triple_proof(&sig, own_double, other_double)
            .is_ok());
    }

    #[test]
    fn quad_proof_signing() {
        let kp = KeyPair::generate();
        let signer = Signer::new(kp.clone());
        let verifier = Verifier::new(kp.public_key().clone());

        let own_triple = b"own triple proof bytes";
        let other_triple = b"other triple proof bytes";

        let sig = signer.sign_quad_proof(own_triple, other_triple);
        assert!(verifier
            .verify_quad_proof(&sig, own_triple, other_triple)
            .is_ok());
    }
}
