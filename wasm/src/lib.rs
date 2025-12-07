//! WebAssembly bindings for the Two Generals Protocol.
//!
//! This module exposes the TGP protocol to JavaScript/TypeScript via wasm-bindgen.
//! It provides a complete simulation interface for the web visualizer.

use wasm_bindgen::prelude::*;
use serde::{Deserialize, Serialize};

// Initialize panic hook for better error messages in browser console
#[wasm_bindgen(start)]
pub fn init_panic_hook() {
    #[cfg(feature = "console_error_panic_hook")]
    console_error_panic_hook::set_once();
}

/// Party identifier for the two-party protocol.
#[wasm_bindgen]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WasmParty {
    Alice = 0,
    Bob = 1,
}

impl WasmParty {
    pub fn other(self) -> Self {
        match self {
            WasmParty::Alice => WasmParty::Bob,
            WasmParty::Bob => WasmParty::Alice,
        }
    }
}

/// Protocol phase for tracking state transitions.
#[wasm_bindgen]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WasmPhase {
    Init = 0,
    Commitment = 1,
    Double = 2,
    Triple = 3,
    Quad = 4,
    Complete = 5,
    Aborted = 6,
}

/// Final decision made by a party.
#[wasm_bindgen]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WasmDecision {
    Pending = 0,
    Attack = 1,
    Abort = 2,
}

/// Message type for protocol communication.
#[wasm_bindgen]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WasmMessageType {
    Commitment = 1,
    DoubleProof = 2,
    TripleProof = 3,
    QuadProof = 4,
}

/// A protocol message for network transmission.
#[wasm_bindgen]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WasmMessage {
    sender: WasmParty,
    sequence: u64,
    msg_type: WasmMessageType,
    /// Simulated message payload (hash of proof data)
    payload_hash: String,
}

#[wasm_bindgen]
impl WasmMessage {
    #[wasm_bindgen(getter)]
    pub fn sender(&self) -> WasmParty {
        self.sender
    }

    #[wasm_bindgen(getter)]
    pub fn sequence(&self) -> u64 {
        self.sequence
    }

    #[wasm_bindgen(getter)]
    pub fn msg_type(&self) -> WasmMessageType {
        self.msg_type
    }

    #[wasm_bindgen(getter)]
    pub fn payload_hash(&self) -> String {
        self.payload_hash.clone()
    }
}

/// Simplified cryptographic key pair for WASM.
/// Uses a deterministic pseudo-random generator for consistent simulation.
#[derive(Debug, Clone)]
struct SimKeyPair {
    seed: [u8; 32],
}

impl SimKeyPair {
    fn new(seed: u32) -> Self {
        let mut bytes = [0u8; 32];
        for (i, b) in bytes.iter_mut().enumerate() {
            *b = ((seed.wrapping_mul(1103515245).wrapping_add(12345 + i as u32)) >> 16) as u8;
        }
        Self { seed: bytes }
    }

    fn public_key_hex(&self) -> String {
        hex::encode(&self.seed[..16])
    }

    fn sign(&self, _message: &[u8]) -> String {
        // Simulated signature - deterministic based on seed
        hex::encode(&self.seed)
    }
}

/// Two Generals Protocol state machine for WASM.
///
/// This is a simplified implementation for the web visualizer that
/// demonstrates the protocol's phase transitions without full cryptography.
#[wasm_bindgen]
pub struct WasmTwoGenerals {
    party: WasmParty,
    phase: WasmPhase,
    keypair: SimKeyPair,
    counterparty_pubkey: String,

    // Own artifacts
    own_commitment: bool,
    own_double: bool,
    own_triple: bool,
    own_quad: bool,

    // Received artifacts
    other_commitment: bool,
    other_double: bool,
    other_triple: bool,
    other_quad: bool,

    sequence: u64,
}

#[wasm_bindgen]
impl WasmTwoGenerals {
    /// Create a new TGP instance for a party.
    #[wasm_bindgen(constructor)]
    pub fn new(party: WasmParty, seed: u32, counterparty_pubkey: &str) -> Self {
        let keypair = SimKeyPair::new(seed);

        Self {
            party,
            phase: WasmPhase::Commitment,
            keypair,
            counterparty_pubkey: counterparty_pubkey.to_string(),
            own_commitment: true, // Created on init
            own_double: false,
            own_triple: false,
            own_quad: false,
            other_commitment: false,
            other_double: false,
            other_triple: false,
            other_quad: false,
            sequence: 0,
        }
    }

    /// Get the public key for this party.
    #[wasm_bindgen]
    pub fn public_key(&self) -> String {
        self.keypair.public_key_hex()
    }

    /// Get the current protocol phase.
    #[wasm_bindgen]
    pub fn phase(&self) -> WasmPhase {
        self.phase
    }

    /// Get the party identifier.
    #[wasm_bindgen]
    pub fn party(&self) -> WasmParty {
        self.party
    }

    /// Check if the protocol has completed (fixpoint achieved).
    #[wasm_bindgen]
    pub fn is_complete(&self) -> bool {
        matches!(self.phase, WasmPhase::Complete)
    }

    /// Check if this party can safely attack.
    #[wasm_bindgen]
    pub fn can_attack(&self) -> bool {
        self.is_complete() && self.own_quad
    }

    /// Get the final decision.
    #[wasm_bindgen]
    pub fn get_decision(&self) -> WasmDecision {
        if self.is_complete() {
            WasmDecision::Attack
        } else if matches!(self.phase, WasmPhase::Aborted) {
            WasmDecision::Abort
        } else {
            WasmDecision::Pending
        }
    }

    /// Abort the protocol.
    #[wasm_bindgen]
    pub fn abort(&mut self) {
        if !self.is_complete() {
            self.phase = WasmPhase::Aborted;
        }
    }

    /// Get the next message to send (for continuous flooding).
    #[wasm_bindgen]
    pub fn next_message(&mut self) -> Option<WasmMessage> {
        self.sequence += 1;

        let (msg_type, payload_hash) = match self.phase {
            WasmPhase::Complete | WasmPhase::Quad => {
                if self.own_quad {
                    (WasmMessageType::QuadProof, format!("Q_{:?}_{}", self.party, self.sequence))
                } else {
                    return None;
                }
            }
            WasmPhase::Triple => {
                if self.own_triple {
                    (WasmMessageType::TripleProof, format!("T_{:?}_{}", self.party, self.sequence))
                } else {
                    return None;
                }
            }
            WasmPhase::Double => {
                if self.own_double {
                    (WasmMessageType::DoubleProof, format!("D_{:?}_{}", self.party, self.sequence))
                } else {
                    return None;
                }
            }
            WasmPhase::Commitment => {
                if self.own_commitment {
                    (WasmMessageType::Commitment, format!("C_{:?}_{}", self.party, self.sequence))
                } else {
                    return None;
                }
            }
            _ => return None,
        };

        Some(WasmMessage {
            sender: self.party,
            sequence: self.sequence,
            msg_type,
            payload_hash,
        })
    }

    /// Receive a message from the counterparty.
    /// Returns true if the message was processed and caused a state change.
    #[wasm_bindgen]
    pub fn receive(&mut self, msg: &WasmMessage) -> bool {
        // Ignore messages from self
        if msg.sender == self.party {
            return false;
        }

        let mut changed = false;

        match msg.msg_type {
            WasmMessageType::Commitment => {
                if !self.other_commitment {
                    self.other_commitment = true;
                    changed = true;
                    self.try_advance();
                }
            }
            WasmMessageType::DoubleProof => {
                // Double proof contains commitment
                if !self.other_commitment {
                    self.other_commitment = true;
                    changed = true;
                }
                if !self.other_double {
                    self.other_double = true;
                    changed = true;
                    self.try_advance();
                }
            }
            WasmMessageType::TripleProof => {
                // Triple proof contains double and commitment
                if !self.other_commitment {
                    self.other_commitment = true;
                    changed = true;
                }
                if !self.other_double {
                    self.other_double = true;
                    changed = true;
                }
                if !self.other_triple {
                    self.other_triple = true;
                    changed = true;
                    self.try_advance();
                }
            }
            WasmMessageType::QuadProof => {
                // Quad proof contains all lower proofs
                if !self.other_commitment {
                    self.other_commitment = true;
                    changed = true;
                }
                if !self.other_double {
                    self.other_double = true;
                    changed = true;
                }
                if !self.other_triple {
                    self.other_triple = true;
                    changed = true;
                }
                if !self.other_quad {
                    self.other_quad = true;
                    changed = true;
                    self.try_advance();
                }
            }
        }

        changed
    }

    /// Try to advance to the next phase based on current state.
    fn try_advance(&mut self) {
        loop {
            let old_phase = self.phase;

            match self.phase {
                WasmPhase::Commitment => {
                    if self.own_commitment && self.other_commitment {
                        self.own_double = true;
                        self.phase = WasmPhase::Double;
                    }
                }
                WasmPhase::Double => {
                    if self.own_double && self.other_double {
                        self.own_triple = true;
                        self.phase = WasmPhase::Triple;
                    }
                }
                WasmPhase::Triple => {
                    if self.own_triple && self.other_triple {
                        self.own_quad = true;
                        self.phase = WasmPhase::Quad;
                    }
                }
                WasmPhase::Quad => {
                    if self.own_quad && self.other_quad {
                        self.phase = WasmPhase::Complete;
                    }
                }
                _ => {}
            }

            if self.phase == old_phase {
                break;
            }
        }
    }

    /// Get state as JSON for debugging.
    #[wasm_bindgen]
    pub fn state_json(&self) -> String {
        serde_json::json!({
            "party": format!("{:?}", self.party),
            "phase": format!("{:?}", self.phase),
            "own": {
                "commitment": self.own_commitment,
                "double": self.own_double,
                "triple": self.own_triple,
                "quad": self.own_quad,
            },
            "other": {
                "commitment": self.other_commitment,
                "double": self.other_double,
                "triple": self.other_triple,
                "quad": self.other_quad,
            },
            "sequence": self.sequence,
        }).to_string()
    }
}

/// Simulation harness for running protocol simulations.
#[wasm_bindgen]
pub struct WasmSimulation {
    alice: WasmTwoGenerals,
    bob: WasmTwoGenerals,
    round: u32,
    max_rounds: u32,
    loss_rate: f64,
    rng_seed: u32,
}

#[wasm_bindgen]
impl WasmSimulation {
    /// Create a new simulation.
    #[wasm_bindgen(constructor)]
    pub fn new(max_rounds: u32, loss_rate: f64, seed: u32) -> Self {
        let alice_keypair = SimKeyPair::new(seed);
        let bob_keypair = SimKeyPair::new(seed.wrapping_add(1));

        let alice = WasmTwoGenerals::new(
            WasmParty::Alice,
            seed,
            &bob_keypair.public_key_hex(),
        );
        let bob = WasmTwoGenerals::new(
            WasmParty::Bob,
            seed.wrapping_add(1),
            &alice_keypair.public_key_hex(),
        );

        Self {
            alice,
            bob,
            round: 0,
            max_rounds,
            loss_rate,
            rng_seed: seed,
        }
    }

    /// Simple pseudo-random number generator.
    fn next_rand(&mut self) -> f64 {
        self.rng_seed = self.rng_seed.wrapping_mul(1103515245).wrapping_add(12345);
        ((self.rng_seed >> 16) as f64) / 32768.0
    }

    /// Run one round of the simulation.
    /// Returns JSON with messages sent and received.
    #[wasm_bindgen]
    pub fn step(&mut self) -> String {
        if self.round >= self.max_rounds {
            return serde_json::json!({
                "round": self.round,
                "complete": true,
                "alice_complete": self.alice.is_complete(),
                "bob_complete": self.bob.is_complete(),
                "messages": [],
            }).to_string();
        }

        self.round += 1;
        let mut messages = Vec::new();

        // Alice sends
        if let Some(msg) = self.alice.next_message() {
            let delivered = self.next_rand() >= self.loss_rate;
            if delivered {
                self.bob.receive(&msg);
            }
            messages.push(serde_json::json!({
                "from": "Alice",
                "to": "Bob",
                "type": format!("{:?}", msg.msg_type),
                "delivered": delivered,
            }));
        }

        // Bob sends
        if let Some(msg) = self.bob.next_message() {
            let delivered = self.next_rand() >= self.loss_rate;
            if delivered {
                self.alice.receive(&msg);
            }
            messages.push(serde_json::json!({
                "from": "Bob",
                "to": "Alice",
                "type": format!("{:?}", msg.msg_type),
                "delivered": delivered,
            }));
        }

        serde_json::json!({
            "round": self.round,
            "complete": self.alice.is_complete() && self.bob.is_complete(),
            "alice": {
                "phase": format!("{:?}", self.alice.phase()),
                "complete": self.alice.is_complete(),
                "decision": format!("{:?}", self.alice.get_decision()),
            },
            "bob": {
                "phase": format!("{:?}", self.bob.phase()),
                "complete": self.bob.is_complete(),
                "decision": format!("{:?}", self.bob.get_decision()),
            },
            "messages": messages,
        }).to_string()
    }

    /// Run the simulation to completion or max rounds.
    #[wasm_bindgen]
    pub fn run_to_completion(&mut self) -> String {
        while self.round < self.max_rounds && !(self.alice.is_complete() && self.bob.is_complete()) {
            self.step();
        }

        serde_json::json!({
            "rounds": self.round,
            "max_rounds": self.max_rounds,
            "alice": {
                "complete": self.alice.is_complete(),
                "decision": format!("{:?}", self.alice.get_decision()),
            },
            "bob": {
                "complete": self.bob.is_complete(),
                "decision": format!("{:?}", self.bob.get_decision()),
            },
            "symmetric": self.alice.get_decision() == self.bob.get_decision(),
        }).to_string()
    }

    /// Get Alice's state.
    #[wasm_bindgen]
    pub fn alice_state(&self) -> String {
        self.alice.state_json()
    }

    /// Get Bob's state.
    #[wasm_bindgen]
    pub fn bob_state(&self) -> String {
        self.bob.state_json()
    }
}

/// Run multiple simulations and return statistics.
#[wasm_bindgen]
pub fn run_batch_simulation(
    num_runs: u32,
    max_rounds: u32,
    loss_rate: f64,
    base_seed: u32,
) -> String {
    let mut symmetric_attack = 0u32;
    let mut symmetric_abort = 0u32;
    let mut asymmetric = 0u32;
    let mut total_rounds = 0u32;

    for i in 0..num_runs {
        let mut sim = WasmSimulation::new(max_rounds, loss_rate, base_seed.wrapping_add(i * 1000));
        sim.run_to_completion();

        total_rounds += sim.round;

        let alice_decision = sim.alice.get_decision();
        let bob_decision = sim.bob.get_decision();

        if alice_decision == bob_decision {
            match alice_decision {
                WasmDecision::Attack => symmetric_attack += 1,
                WasmDecision::Abort | WasmDecision::Pending => symmetric_abort += 1,
            }
        } else {
            asymmetric += 1;
        }
    }

    serde_json::json!({
        "num_runs": num_runs,
        "max_rounds": max_rounds,
        "loss_rate": loss_rate,
        "results": {
            "symmetric_attack": symmetric_attack,
            "symmetric_abort": symmetric_abort,
            "asymmetric": asymmetric,
        },
        "avg_rounds": total_rounds as f64 / num_runs as f64,
        "protocol_valid": asymmetric == 0,
    }).to_string()
}

/// Get WASM module version.
#[wasm_bindgen]
pub fn version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_perfect_channel() {
        let mut sim = WasmSimulation::new(100, 0.0, 42);
        sim.run_to_completion();

        assert!(sim.alice.is_complete());
        assert!(sim.bob.is_complete());
        assert!(sim.alice.can_attack());
        assert!(sim.bob.can_attack());
    }

    #[test]
    fn test_lossy_channel_symmetric() {
        // Run multiple simulations at 50% loss
        for seed in 0..100 {
            let mut sim = WasmSimulation::new(1000, 0.5, seed);
            sim.run_to_completion();

            // Outcomes must be symmetric
            assert_eq!(
                sim.alice.get_decision(),
                sim.bob.get_decision(),
                "Asymmetric outcome at seed {}", seed
            );
        }
    }

    #[test]
    fn test_phase_transitions() {
        let alice_key = SimKeyPair::new(1);
        let bob_key = SimKeyPair::new(2);

        let mut alice = WasmTwoGenerals::new(WasmParty::Alice, 1, &bob_key.public_key_hex());
        let mut bob = WasmTwoGenerals::new(WasmParty::Bob, 2, &alice_key.public_key_hex());

        // Both start in Commitment phase
        assert_eq!(alice.phase(), WasmPhase::Commitment);
        assert_eq!(bob.phase(), WasmPhase::Commitment);

        // Exchange until complete
        for _ in 0..10 {
            if let Some(msg) = alice.next_message() {
                bob.receive(&msg);
            }
            if let Some(msg) = bob.next_message() {
                alice.receive(&msg);
            }

            if alice.is_complete() && bob.is_complete() {
                break;
            }
        }

        assert!(alice.is_complete());
        assert!(bob.is_complete());
    }
}
