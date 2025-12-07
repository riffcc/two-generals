//! TGP Node Binary - Two Generals Protocol Node
//!
//! This binary provides a command-line interface for running a TGP node
//! that can coordinate with a peer over a network connection.

use std::io::{self, Write};
use two_generals::{KeyPair, Party, TwoGenerals};

fn main() {
    println!("Two Generals Protocol (TGP) Node");
    println!("================================");
    println!();

    // Generate keys for this node
    let our_keys = KeyPair::generate();
    println!("Generated key pair:");
    println!("  Public key: {}", our_keys.public_key());
    println!();

    // For now, run a local simulation
    println!("Running local protocol simulation...");
    println!();

    let peer_keys = KeyPair::generate();

    let mut alice = TwoGenerals::new(Party::Alice, our_keys.clone(), peer_keys.public_key().clone());
    let mut bob = TwoGenerals::new(Party::Bob, peer_keys.clone(), our_keys.public_key().clone());

    let mut round = 0;
    loop {
        round += 1;
        println!("Round {}", round);

        // Exchange messages
        let alice_msgs = alice.get_messages_to_send();
        let bob_msgs = bob.get_messages_to_send();

        println!("  Alice -> Bob: {} messages", alice_msgs.len());
        println!("  Bob -> Alice: {} messages", bob_msgs.len());

        for msg in alice_msgs {
            if let Err(e) = bob.receive(&msg) {
                eprintln!("  Bob receive error: {}", e);
            }
        }
        for msg in bob_msgs {
            if let Err(e) = alice.receive(&msg) {
                eprintln!("  Alice receive error: {}", e);
            }
        }

        println!("  Alice state: {:?}", alice.state());
        println!("  Bob state: {:?}", bob.state());

        if alice.is_complete() && bob.is_complete() {
            println!();
            println!("Protocol complete!");
            println!("  Alice can attack: {}", alice.can_attack());
            println!("  Bob can attack: {}", bob.can_attack());
            break;
        }

        if round > 10 {
            eprintln!("Protocol did not complete in 10 rounds");
            break;
        }

        io::stdout().flush().unwrap();
    }

    // Check bilateral receipt
    if let Some((own_q, other_q)) = alice.get_bilateral_receipt() {
        println!();
        println!("Bilateral receipt constructed:");
        println!("  Q_A party: {:?}", own_q.party);
        println!("  Q_B party: {:?}", other_q.party);
        println!();
        println!("Both halves prove mutual constructibility - epistemic fixpoint achieved.");
    }
}
