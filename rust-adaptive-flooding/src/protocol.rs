//! Adaptive TGP Protocol Integration
//!
//! This module integrates the adaptive flooding controller with the core TGP protocol.
//! It provides a wrapper around TwoGenerals that uses adaptive rate control for message flooding.

use two_generals::{crypto::KeyPair, types::Party, TwoGenerals, Message};

use crate::flooder::AdaptiveFlooder;

/// Adaptive TGP protocol that wraps TwoGenerals with adaptive flooding.
///
/// This struct combines the core TGP protocol with an adaptive flood controller
/// to dynamically adjust the message send rate based on application needs.
#[derive(Debug)]
pub struct AdaptiveTGP {
    /// The underlying TGP protocol instance
    protocol: TwoGenerals,
    /// The adaptive flood controller
    flooder: AdaptiveFlooder,
    /// Buffer for outgoing messages
    send_buffer: Vec<Message>,
    /// Whether data transfer is active
    data_pending: bool,
}

impl AdaptiveTGP {
    /// Create a new AdaptiveTGP instance.
    ///
    /// # Arguments
    ///
    /// * `party` - Which party this instance represents (Alice or Bob)
    /// * `keypair` - This party's signing key pair
    /// * `counterparty_public_key` - The counterparty's public key
    /// * `min_rate` - Minimum packets per second (drip mode)
    /// * `max_rate` - Maximum packets per second (burst mode)
    ///
    /// # Returns
    ///
    /// A new `AdaptiveTGP` instance ready for adaptive protocol execution.
    #[must_use]
    pub fn new(
        party: Party,
        keypair: KeyPair,
        counterparty_public_key: two_generals::crypto::PublicKey,
        min_rate: u64,
        max_rate: u64,
    ) -> Self {
        Self {
            protocol: TwoGenerals::new(party, keypair, counterparty_public_key),
            flooder: AdaptiveFlooder::new(min_rate, max_rate),
            send_buffer: Vec::new(),
            data_pending: false,
        }
    }

    /// Create a new AdaptiveTGP instance with a custom commitment message.
    ///
    /// # Arguments
    ///
    /// * `party` - Which party this instance represents
    /// * `keypair` - This party's signing key pair
    /// * `counterparty_public_key` - The counterparty's public key
    /// * `commitment_message` - Custom commitment message
    /// * `min_rate` - Minimum packets per second
    /// * `max_rate` - Maximum packets per second
    #[must_use]
    pub fn with_commitment_message(
        party: Party,
        keypair: KeyPair,
        counterparty_public_key: two_generals::crypto::PublicKey,
        commitment_message: Vec<u8>,
        min_rate: u64,
        max_rate: u64,
    ) -> Self {
        Self {
            protocol: TwoGenerals::with_commitment_message(
                party,
                keypair,
                counterparty_public_key,
                commitment_message,
            ),
            flooder: AdaptiveFlooder::new(min_rate, max_rate),
            send_buffer: Vec::new(),
            data_pending: false,
        }
    }

    /// Get the current protocol state.
    ///
    /// # Returns
    ///
    /// The current TGP protocol state.
    #[must_use]
    pub fn state(&self) -> two_generals::ProtocolState {
        self.protocol.state()
    }

    /// Check if the protocol has reached the fixpoint.
    ///
    /// # Returns
    ///
    /// `true` if the protocol is complete.
    #[must_use]
    pub fn is_complete(&self) -> bool {
        self.protocol.is_complete()
    }

    /// Check if this party can safely ATTACK.
    ///
    /// # Returns
    ///
    /// `true` if the party can attack.
    #[must_use]
    pub fn can_attack(&self) -> bool {
        self.protocol.can_attack()
    }

    /// Get the final decision.
    ///
    /// # Returns
    ///
    /// The protocol decision (Attack or Abort).
    #[must_use]
    pub fn get_decision(&self) -> two_generals::Decision {
        self.protocol.get_decision()
    }

    /// Get the bilateral receipt pair if complete.
    ///
    /// # Returns
    ///
    /// Optional tuple of (own_quad, other_quad) if complete.
    #[must_use]
    pub fn get_bilateral_receipt(&self) -> Option<(&two_generals::QuadProof, &two_generals::QuadProof)> {
        self.protocol.get_bilateral_receipt()
    }

    /// Abort the protocol.
    pub fn abort(&mut self) {
        self.protocol.abort();
    }

    /// Set whether data is pending for transfer.
    ///
    /// This controls the adaptive flood rate - when data is pending,
    /// the flooder will ramp up to maximum rate, otherwise it will
    /// ramp down to minimum rate.
    ///
    /// # Arguments
    ///
    /// * `pending` - `true` if data is waiting to be sent.
    pub fn set_data_pending(&mut self, pending: bool) {
        self.data_pending = pending;
    }

    /// Get messages to send based on adaptive rate control.
    ///
    /// This method respects the adaptive flood rate - it will only
    /// return messages when the flooder determines it's time to send.
    ///
    /// # Returns
    ///
    /// Vector of messages to send (may be empty if rate-limited).
    pub fn get_messages_to_send(&mut self) -> Vec<Message> {
        // Check if we should send based on adaptive rate
        if self.flooder.should_send(self.data_pending) {
            // Get messages from the underlying protocol
            let messages = self.protocol.get_messages_to_send();

            // Store in buffer and return
            self.send_buffer = messages.clone();
            messages
        } else {
            Vec::new()
        }
    }

    /// Process a received message from the counterparty.
    ///
    /// # Arguments
    ///
    /// * `msg` - The received message
    ///
    /// # Returns
    ///
    /// Result indicating success or failure.
    pub fn receive(&mut self, msg: &Message) -> two_generals::Result<bool> {
        self.protocol.receive(msg)
    }

    /// Get the current flood rate.
    ///
    /// # Returns
    ///
    /// Current packets per second.
    #[must_use]
    pub fn current_rate(&self) -> u64 {
        self.flooder.current_rate()
    }

    /// Get the total number of packets sent.
    ///
    /// # Returns
    ///
    /// Total packet count.
    #[must_use]
    pub fn packet_count(&self) -> u64 {
        self.flooder.packet_count()
    }

    /// Reset the packet counter.
    pub fn reset_counter(&mut self) {
        self.flooder.reset_counter();
    }

    /// Get the underlying protocol instance.
    ///
    /// # Returns
    ///
    /// Reference to the underlying TwoGenerals protocol.
    #[must_use]
    pub fn protocol(&self) -> &TwoGenerals {
        &self.protocol
    }

    /// Get mutable access to the underlying protocol instance.
    ///
    /// # Returns
    ///
    /// Mutable reference to the underlying TwoGenerals protocol.
    pub fn protocol_mut(&mut self) -> &mut TwoGenerals {
        &mut self.protocol
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    use two_generals::crypto::KeyPair;

    #[test]
    fn test_adaptive_tgp_initialization() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let adaptive_alice = AdaptiveTGP::new(
            two_generals::Party::Alice,
            alice_kp.clone(),
            bob_kp.public_key().clone(),
            1,
            1000,
        );

        assert!(matches!(adaptive_alice.state(), two_generals::ProtocolState::Commitment));
        assert_eq!(adaptive_alice.current_rate(), 1); // Starts at min rate
    }

    #[test]
    fn test_adaptive_tgp_with_custom_message() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let custom_msg = b"Custom attack plan".to_vec();

        let adaptive_alice = AdaptiveTGP::with_commitment_message(
            two_generals::Party::Alice,
            alice_kp.clone(),
            bob_kp.public_key().clone(),
            custom_msg,
            1,
            1000,
        );

        assert!(matches!(adaptive_alice.state(), two_generals::ProtocolState::Commitment));
    }

    #[test]
    fn test_adaptive_tgp_completion() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let mut adaptive_alice = AdaptiveTGP::new(
            two_generals::Party::Alice,
            alice_kp.clone(),
            bob_kp.public_key().clone(),
            100, // Higher min rate for faster test
            1000,
        );

        let mut adaptive_bob = AdaptiveTGP::new(
            two_generals::Party::Bob,
            bob_kp,
            alice_kp.public_key().clone(),
            100,
            1000,
        );

        // Set data pending to enable faster sending
        adaptive_alice.set_data_pending(true);
        adaptive_bob.set_data_pending(true);

        // Run protocol to completion
        for _ in 0..100 {
            // Alice sends to Bob
            for msg in adaptive_alice.get_messages_to_send() {
                let _ = adaptive_bob.receive(&msg);
            }

            // Bob sends to Alice
            for msg in adaptive_bob.get_messages_to_send() {
                let _ = adaptive_alice.receive(&msg);
            }

            // Check if both complete
            if adaptive_alice.is_complete() && adaptive_bob.is_complete() {
                break;
            }

            // Small delay to allow rate modulation
            std::thread::sleep(Duration::from_millis(1));
        }

        assert!(adaptive_alice.is_complete());
        assert!(adaptive_bob.is_complete());
        assert!(adaptive_alice.can_attack());
        assert!(adaptive_bob.can_attack());
    }

    #[test]
    fn test_adaptive_tgp_rate_modulation() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let mut adaptive_alice = AdaptiveTGP::new(
            two_generals::Party::Alice,
            alice_kp,
            bob_kp.public_key().clone(),
            1,
            1000,
        );

        // Start with no data pending - should be at min rate
        assert_eq!(adaptive_alice.current_rate(), 1);

        // Set data pending and trigger sends
        adaptive_alice.set_data_pending(true);
        for _ in 0..10 {
            let _ = adaptive_alice.get_messages_to_send();
        }

        // Rate should have increased
        let rate_with_data = adaptive_alice.current_rate();
        assert!(rate_with_data > 1, "Rate should increase when data is pending");

        // Clear data pending
        adaptive_alice.set_data_pending(false);
        for _ in 0..10 {
            let _ = adaptive_alice.get_messages_to_send();
        }

        // Rate should decrease
        let rate_without_data = adaptive_alice.current_rate();
        assert!(rate_without_data < rate_with_data, "Rate should decrease when data is not pending");
    }

    #[test]
    fn test_adaptive_tgp_bilateral_receipt() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let mut adaptive_alice = AdaptiveTGP::new(
            two_generals::Party::Alice,
            alice_kp.clone(),
            bob_kp.public_key().clone(),
            100, // Higher min rate for faster test
            1000,
        );

        let mut adaptive_bob = AdaptiveTGP::new(
            two_generals::Party::Bob,
            bob_kp,
            alice_kp.public_key().clone(),
            100,
            1000,
        );

        // Set data pending for faster completion
        adaptive_alice.set_data_pending(true);
        adaptive_bob.set_data_pending(true);

        // Run to completion
        for _ in 0..100 {
            for msg in adaptive_alice.get_messages_to_send() {
                let _ = adaptive_bob.receive(&msg);
            }

            for msg in adaptive_bob.get_messages_to_send() {
                let _ = adaptive_alice.receive(&msg);
            }

            if adaptive_alice.is_complete() && adaptive_bob.is_complete() {
                break;
            }

            std::thread::sleep(Duration::from_millis(1));
        }

        // Verify bilateral receipt
        let alice_receipt = adaptive_alice.get_bilateral_receipt();
        let bob_receipt = adaptive_bob.get_bilateral_receipt();

        assert!(alice_receipt.is_some());
        assert!(bob_receipt.is_some());

        let (alice_own, alice_other) = alice_receipt.unwrap();
        let (bob_own, bob_other) = bob_receipt.unwrap();

        assert_eq!(alice_own.party, two_generals::Party::Alice);
        assert_eq!(alice_other.party, two_generals::Party::Bob);
        assert_eq!(bob_own.party, two_generals::Party::Bob);
        assert_eq!(bob_other.party, two_generals::Party::Alice);
    }

    #[test]
    fn test_adaptive_tgp_abort() {
        let alice_kp = KeyPair::generate();
        let bob_kp = KeyPair::generate();

        let mut adaptive_alice = AdaptiveTGP::new(
            two_generals::Party::Alice,
            alice_kp,
            bob_kp.public_key().clone(),
            1,
            1000,
        );

        // Abort before completing
        adaptive_alice.abort();

        assert!(!adaptive_alice.can_attack());
        assert!(matches!(
            adaptive_alice.get_decision(),
            two_generals::Decision::Abort
        ));
    }
}
