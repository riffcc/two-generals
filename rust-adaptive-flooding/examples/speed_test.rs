use adaptive_flooding::{AdaptiveFlooder, AdaptiveTGP};
use std::time::{Duration, Instant};
use two_generals::{crypto::KeyPair, types::Party};
use std::io::{Read, Write};
use std::net::{TcpStream, TcpListener};
use std::thread;

fn main() {
    println!("Adaptive Flooding Speed Test");
    println!("==============================\n");

    let args: Vec<String> = std::env::args().collect();
    let is_server = args.len() > 1 && args[1] == "server";
    let is_client = args.len() > 1 && args[1] == "client";
    let target_host = args.get(2).map(|s| s.as_str()).unwrap_or("barbara.per.riff.cc");
    let target_port = args.get(3).map(|s| s.parse().unwrap_or(9500)).unwrap_or(9500); // Default to 9500

    if is_server {
        run_server(target_port);
    } else if is_client {
        run_client(target_host, target_port);
    } else {
        println!("Usage:");
        println!("  speed_test server [port]           - Run as server");
        println!("  speed_test client [host] [port]    - Run as client");
        println!("\nExample:");
        println!("  speed_test server 9500             - Server on port 9500");
        println!("  speed_test client barbara.per.riff.cc 9500 - Client to barbara");
    }
}

fn run_server(port: u16) {
    println!("Starting server on port {}...", port);

    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).expect("Failed to bind");
    println!("Server listening on 0.0.0.0:{}", port);

    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                println!("New connection: {}", stream.peer_addr().unwrap());

                // Create adaptive flooder for server
                let mut flooder = AdaptiveFlooder::new(10, 10000);
                let start_time = Instant::now();
                let mut bytes_received = 0;

                // Read data from client
                let mut buffer = [0; 1024];
                loop {
                    match stream.read(&mut buffer) {
                        Ok(0) => {
                            println!("Client disconnected");
                            break;
                        }
                        Ok(n) => {
                            bytes_received += n;

                            // Simulate adaptive processing
                            if flooder.should_send(true) {
                                // Echo back to client
                                stream.write_all(&buffer[..n]).unwrap();
                                stream.flush().unwrap();
                            }
                        }
                        Err(e) => {
                            println!("Error reading from client: {}", e);
                            break;
                        }
                    }
                }

                let elapsed = start_time.elapsed();
                let speed = bytes_received as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;

                println!("Connection closed");
                println!("Bytes received: {} ({:.2} MB)", bytes_received, bytes_received as f64 / 1024.0 / 1024.0);
                println!("Time: {:?}", elapsed);
                println!("Speed: {:.2} MB/s", speed);
                println!("Packets sent: {}", flooder.packet_count());
            }
            Err(e) => {
                println!("Error accepting connection: {}", e);
            }
        }
    }
}

fn run_client(host: &str, port: u16) {
    println!("Connecting to {}:{}", host, port);

    match TcpStream::connect(format!("{}:{}", host, port)) {
        Ok(mut stream) => {
            println!("Connected to server");

            // Create adaptive flooder for client
            let mut flooder = AdaptiveFlooder::new(10, 10000);
            let start_time = Instant::now();
            let mut bytes_sent = 0;
            let mut bytes_received = 0;

            // Test data - 1MB of data
            let test_data = vec![0u8; 1024 * 1024]; // 1MB
            let mut remaining_data = test_data.len();
            let mut offset = 0;

            // Send data in chunks
            while remaining_data > 0 {
                let chunk_size = std::cmp::min(1024, remaining_data);

                if flooder.should_send(true) {
                    match stream.write(&test_data[offset..offset + chunk_size]) {
                        Ok(n) => {
                            bytes_sent += n;
                            remaining_data -= n;
                            offset += n;

                            // Read echo back
                            let mut buffer = [0; 1024];
                            match stream.read(&mut buffer) {
                                Ok(n) => bytes_received += n,
                                Err(_) => break,
                            }
                        }
                        Err(e) => {
                            println!("Error writing to server: {}", e);
                            break;
                        }
                    }
                }

                thread::sleep(Duration::from_millis(1));
            }

            let elapsed = start_time.elapsed();
            let speed = bytes_sent as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;

            println!("\nTest complete!");
            println!("Bytes sent: {} ({:.2} MB)", bytes_sent, bytes_sent as f64 / 1024.0 / 1024.0);
            println!("Bytes received: {} ({:.2} MB)", bytes_received, bytes_received as f64 / 1024.0 / 1024.0);
            println!("Time: {:?}", elapsed);
            println!("Speed: {:.2} MB/s", speed);
            println!("Packets sent: {}", flooder.packet_count());

            // Test TGP protocol performance
            println!("\nTesting TGP protocol performance...");
            test_tgp_performance();
        }
        Err(e) => {
            println!("Failed to connect to server: {}", e);
        }
    }
}

fn test_tgp_performance() {
    let alice_kp = KeyPair::generate();
    let bob_kp = KeyPair::generate();

    let mut adaptive_alice = AdaptiveTGP::new(
        Party::Alice,
        alice_kp.clone(),
        bob_kp.public_key().clone(),
        100,   // min_rate
        10000, // max_rate
    );

    let mut adaptive_bob = AdaptiveTGP::new(
        Party::Bob,
        bob_kp,
        alice_kp.public_key().clone(),
        100,
        10000,
    );

    // Set data pending for faster protocol completion
    adaptive_alice.set_data_pending(true);
    adaptive_bob.set_data_pending(true);

    let start_time = Instant::now();
    let mut rounds = 0;

    for _ in 0..1000 {
        rounds += 1;

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

        thread::sleep(Duration::from_millis(1));
    }

    let elapsed = start_time.elapsed();

    println!("TGP Protocol Results:");
    println!("  Completed in {:?}", elapsed);
    println!("  Rounds: {}", rounds);
    println!("  Alice packets: {}", adaptive_alice.packet_count());
    println!("  Bob packets: {}", adaptive_bob.packet_count());
    println!("  Alice can attack: {}", adaptive_alice.can_attack());
    println!("  Bob can attack: {}", adaptive_bob.can_attack());

    if let Some((alice_own, alice_other)) = adaptive_alice.get_bilateral_receipt() {
        println!("  Bilateral receipt verified: Q_A({:?}) + Q_B({:?})",
                 alice_own.party, alice_other.party);
    }
}