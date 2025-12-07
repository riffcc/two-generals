//! Error types for the Two Generals Protocol.

use thiserror::Error;

/// Result type alias for TGP operations.
pub type Result<T> = core::result::Result<T, Error>;

/// Errors that can occur during TGP operations.
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum Error {
    /// Invalid signature on a message.
    #[error("invalid signature")]
    InvalidSignature,

    /// Message from unexpected party.
    #[error("unexpected party: expected {expected:?}, got {got:?}")]
    UnexpectedParty {
        /// Expected party identifier.
        expected: crate::types::Party,
        /// Actual party identifier.
        got: crate::types::Party,
    },

    /// Invalid proof chain - nested proofs don't match expected structure.
    #[error("invalid proof chain at level {level}")]
    InvalidProofChain {
        /// The proof level where validation failed.
        level: u8,
    },

    /// Message received in wrong protocol state.
    #[error("invalid state transition: cannot accept {message_type} in state {current_state}")]
    InvalidStateTransition {
        /// Current protocol state.
        current_state: &'static str,
        /// Type of message that was rejected.
        message_type: &'static str,
    },

    /// Protocol already completed.
    #[error("protocol already completed")]
    AlreadyCompleted,

    /// Serialization error.
    #[error("serialization error: {0}")]
    Serialization(#[cfg(feature = "std")] String, #[cfg(not(feature = "std"))] &'static str),

    /// Cryptographic operation failed.
    #[error("cryptographic error: {0}")]
    Crypto(#[cfg(feature = "std")] String, #[cfg(not(feature = "std"))] &'static str),

    /// BFT consensus error.
    #[error("BFT error: {0}")]
    Bft(#[cfg(feature = "std")] String, #[cfg(not(feature = "std"))] &'static str),
}

#[cfg(feature = "std")]
impl From<cbor4ii::serde::EncodeError<std::io::Error>> for Error {
    fn from(e: cbor4ii::serde::EncodeError<std::io::Error>) -> Self {
        Error::Serialization(e.to_string())
    }
}

#[cfg(feature = "std")]
impl From<ed25519_dalek::SignatureError> for Error {
    fn from(_: ed25519_dalek::SignatureError) -> Self {
        Error::InvalidSignature
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn error_display_invalid_signature() {
        let err = Error::InvalidSignature;
        assert_eq!(format!("{}", err), "invalid signature");
    }

    #[test]
    fn error_display_unexpected_party() {
        let err = Error::UnexpectedParty {
            expected: crate::types::Party::Alice,
            got: crate::types::Party::Bob,
        };
        assert!(format!("{}", err).contains("Alice"));
        assert!(format!("{}", err).contains("Bob"));
    }

    #[test]
    fn error_display_invalid_proof_chain() {
        let err = Error::InvalidProofChain { level: 2 };
        assert!(format!("{}", err).contains("2"));
    }

    #[test]
    fn error_display_invalid_state_transition() {
        let err = Error::InvalidStateTransition {
            current_state: "Double",
            message_type: "Commitment",
        };
        assert!(format!("{}", err).contains("Double"));
        assert!(format!("{}", err).contains("Commitment"));
    }

    #[test]
    fn error_display_already_completed() {
        let err = Error::AlreadyCompleted;
        assert_eq!(format!("{}", err), "protocol already completed");
    }

    #[test]
    fn error_display_serialization() {
        let err = Error::Serialization("test error".into());
        assert!(format!("{}", err).contains("test error"));
    }

    #[test]
    fn error_display_crypto() {
        let err = Error::Crypto("crypto error".into());
        assert!(format!("{}", err).contains("crypto error"));
    }

    #[test]
    fn error_clone() {
        let err = Error::InvalidSignature;
        let cloned = err.clone();
        assert_eq!(err, cloned);
    }

    #[test]
    fn error_eq() {
        assert_eq!(Error::InvalidSignature, Error::InvalidSignature);
        assert_ne!(Error::InvalidSignature, Error::AlreadyCompleted);
    }
}
