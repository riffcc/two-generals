use adaptive_flooding::{AdaptiveFlooder, AdaptiveTGP};
use std::time::Duration;
use two_generals::{crypto::KeyPair, types::Party};

fn main() {
    println!("Adaptive Flooding Protocol Demo");
    println!("================================\n");

    // Example 1: Standalone flooder
    println!("Example 1: Standalone AdaptiveFlooder");
    println!("-------------------------------------");

    let mut flooder = AdaptiveFlooder::new(1, 1000);

    println!("Initial rate: {} pkts/sec", flooder.current_rate());

    // Simulate sending with data pending
    println!("\nSimulating sends with data pending (should ramp up):");
    for i in 0..5 {
        if flooder.should_send(true) {
            println!("  Send {} at rate: {} pkts/sec", i + 1, flooder.current_rate());
        }
        std::thread::sleep(Duration::from_millis(10));
    }

    // Simulate sending without data pending
    println!("\nSimulating sends without data pending (should ramp down):");
    for i in 0..5 {
        if flooder.should_send(false) {
            println!("  Send {} at rate: {} pkts/sec", i + 1, flooder.current_rate());
        }
        std::thread::sleep(Duration::from_millis(10));
    }

    println!("\nTotal packets sent: {}", flooder.packet_count());

    // Example 2: Adaptive TGP protocol
    println!("\n\nExample 2: Adaptive TGP Protocol");
    println!("---------------------------------");

    let alice_kp = KeyPair::generate();
    let bob_kp = KeyPair::generate();

    let mut adaptive_alice = AdaptiveTGP::new(
        Party::Alice,
        alice_kp.clone(),
        bob_kp.public_key().clone(),
        10,   // min_rate
        1000, // max_rate
    );

    let mut adaptive_bob = AdaptiveTGP::new(
        Party::Bob,
        bob_kp,
        alice_kp.public_key().clone(),
        10,
        1000,
    );

    // Set data pending for faster protocol completion
    adaptive_alice.set_data_pending(true);
    adaptive_bob.set_data_pending(true);

    println!("Running adaptive TGP protocol...");

    let start_time = std::time::Instant::now();
    let mut _round = 0;

    for _ in 0..200 {
        _round += 1;

        // Alice sends to Bob
        let alice_msgs = adaptive_alice.get_messages_to_send();
        for msg in alice_msgs {
            let _ = adaptive_bob.receive(&msg);
        }

        // Bob sends to Alice
        let bob_msgs = adaptive_bob.get_messages_to_send();
        for msg in bob_msgs {
            let _ = adaptive_alice.receive(&msg);
        }

        // Check completion
        if adaptive_alice.is_complete() && adaptive_bob.is_complete() {
            break;
        }

        std::thread::sleep(Duration::from_millis(1));
    }

    let elapsed = start_time.elapsed();

    println!("Protocol completed in {:?}", elapsed);
    println!("Alice state: {:?}", adaptive_alice.state());
    println!("Bob state: {:?}", adaptive_bob.state());
    println!("Alice can attack: {}", adaptive_alice.can_attack());
    println!("Bob can attack: {}", adaptive_bob.can_attack());
    println!("Alice packets sent: {}", adaptive_alice.packet_count());
    println!("Bob packets sent: {}", adaptive_bob.packet_count());

    // Verify bilateral receipt
    if let Some((alice_own, alice_other)) = adaptive_alice.get_bilateral_receipt() {
        println!("\nBilateral Receipt Verified:");
        println!("  Alice has Q_A (party: {:?}) and Q_B (party: {:?})",
                 alice_own.party, alice_other.party);
    }

    println!("\n✓ Adaptive flooding protocol demo complete!");
}
