//! Two Generals Protocol (TGP) - Rust Implementation
//!
//! A deterministically failsafe solution to the Coordinated Attack Problem
//! using cryptographic proof stapling and bilateral construction properties.
//!
//! # Overview
//!
//! This crate provides a high-performance, memory-safe implementation of TGP
//! with optional `no_std` support for embedded and WebAssembly targets.
//!
//! # Features
//!
//! - `std` (default): Full standard library support with async networking
//! - `no_std`: Embedded-friendly implementation without allocator dependencies
//!
//! # Example
//!
//! ```rust,ignore
//! use two_generals::{TwoGenerals, KeyPair};
//!
//! let alice_keys = KeyPair::generate();
//! let bob_keys = KeyPair::generate();
//!
//! let mut alice = TwoGenerals::new(alice_keys, bob_keys.public_key());
//! let mut bob = TwoGenerals::new(bob_keys, alice_keys.public_key());
//!
//! // Exchange messages until coordination achieved
//! loop {
//!     if let Some(msg) = alice.next_message() {
//!         bob.receive(&msg)?;
//!     }
//!     if let Some(msg) = bob.next_message() {
//!         alice.receive(&msg)?;
//!     }
//!     if alice.can_attack() && bob.can_attack() {
//!         break;
//!     }
//! }
//! ```

#![cfg_attr(feature = "no_std", no_std)]
#![deny(unsafe_code)]
#![deny(missing_docs)]
#![warn(clippy::all, clippy::pedantic)]

#[cfg(feature = "no_std")]
extern crate alloc;

pub mod crypto;
pub mod error;
pub mod protocol;
pub mod types;

pub use crypto::{KeyPair, PublicKey, Signature, Signer, Verifier};
pub use error::{Error, Result};
pub use protocol::{run_protocol_simulation, ProtocolState, TwoGenerals};
pub use types::{Commitment, Decision, DoubleProof, Message, MessagePayload, Party, ProtocolPhase, QuadProof, TripleProof};
