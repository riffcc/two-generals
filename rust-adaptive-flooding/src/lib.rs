//! Adaptive Flooding Protocol Implementation
//!
//! This crate implements an adaptive flooding layer for the Two Generals Protocol (TGP).
//! Instead of constant flooding, nodes can dynamically adjust flood rates based on:
//! - Data transfer needs (idle vs active)
//! - Network conditions (congestion, latency)
//! - Application requirements (priority, QoS)
//!
//! # Key Features
//!
//! - **Drip Mode**: Slow to near-zero packets when idle (1-10 pkts/sec)
//! - **Burst Mode**: Instantly ramp to max speed when needed (10K-100K+ pkts/sec)
//! - **Symmetric Control**: Both parties can independently modulate
//! - **Proof Stapling Preserved**: Adaptive rate doesn't break bilateral construction
//!
//! # Design
//!
//! The adaptive flooding layer wraps the core TGP protocol and modulates the send rate
//! based on application feedback. The core insight is that flood rate affects *when*
//! proofs arrive, not *what* they contain, so bilateral construction is preserved.

pub mod flooder;
pub mod protocol;

pub use flooder::AdaptiveFlooder;
pub use protocol::AdaptiveTGP;
