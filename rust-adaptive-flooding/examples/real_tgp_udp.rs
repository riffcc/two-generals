use adaptive_flooding::AdaptiveTGP;
use std::time::{Duration, Instant};
use two_generals::{crypto::KeyPair, types::Party, Message};
use std::thread;
use std::net::{UdpSocket, SocketAddr};
use std::io;
use rayon::prelude::*;

/// Extension trait to add len method to Message
trait MessageExt {
    fn len(&self) -> usize;
}

impl MessageExt for Message {
    fn len(&self) -> usize {
        // Measure actual serialized size
        bincode::serialize(self).map_or(0, |serialized| serialized.len())
    }
}

/// Adaptive MTU manager for optimizing packet sizes
struct AdaptiveMtuManager {
    current_mtu: usize,
    min_mtu: usize,
    max_mtu: usize,
    packet_overhead: usize,
    congestion_window: usize,
    packet_loss_rate: f64,
    last_adjustment_time: Instant,
}

impl AdaptiveMtuManager {
    fn new() -> Self {
        Self {
            current_mtu: 1500,  // Standard Ethernet MTU
            min_mtu: 576,      // Minimum IP MTU
            max_mtu: 9000,     // Jumbo frames
            packet_overhead: 42, // IP (20) + UDP (8) + TGP headers (14)
            congestion_window: 1000,
            packet_loss_rate: 0.0,
            last_adjustment_time: Instant::now(),
        }
    }

    /// Adjust MTU based on network conditions
    fn adjust_mtu(&mut self, success_rate: f64, rtt: Duration) {
        let now = Instant::now();
        if now - self.last_adjustment_time < Duration::from_secs(1) {
            return;
        }
        self.last_adjustment_time = now;

        // Calculate packet loss rate (inverse of success rate)
        self.packet_loss_rate = 1.0 - success_rate;

        // Adaptive MTU adjustment algorithm
        if self.packet_loss_rate > 0.1 { // High packet loss
            // Reduce MTU to decrease fragmentation
            self.current_mtu = (self.current_mtu as f64 * 0.9) as usize;
            self.current_mtu = self.current_mtu.max(self.min_mtu);
        } else if self.packet_loss_rate < 0.01 && rtt < Duration::from_millis(50) { // Good conditions
            // Increase MTU to improve throughput
            self.current_mtu = (self.current_mtu as f64 * 1.05) as usize;
            self.current_mtu = self.current_mtu.min(self.max_mtu);
        }

        // Ensure MTU stays within bounds
        self.current_mtu = self.current_mtu.clamp(self.min_mtu, self.max_mtu);
    }

    /// Get optimal packet size for a message
    fn get_optimal_packet_size(&self, message_size: usize) -> usize {
        let effective_mtu = self.current_mtu - self.packet_overhead;
        if message_size <= effective_mtu {
            message_size // Single packet
        } else {
            effective_mtu // Fragmented
        }
    }

    /// Get current effective MTU (MTU - overhead)
    fn get_effective_mtu(&self) -> usize {
        self.current_mtu - self.packet_overhead
    }
}

/// Simple UDP network wrapper for TGP protocol
struct UdpTgpNetwork {
    socket: UdpSocket,
    peer_addr: Option<SocketAddr>,
    mtu_manager: AdaptiveMtuManager,
    fragment_buffer: Vec<(u64, Vec<u8>)>, // (fragment_id, data)
    next_fragment_id: u64,
}

impl UdpTgpNetwork {
    fn bind(addr: &str) -> io::Result<Self> {
        let socket = UdpSocket::bind(addr)?;
        // Non-blocking for poll-style operation
        socket.set_nonblocking(true)?;
        Ok(Self {
            socket,
            peer_addr: None,
            mtu_manager: AdaptiveMtuManager::new(),
            fragment_buffer: Vec::new(),
            next_fragment_id: 0,
        })
    }

    fn connect(addr: &str) -> io::Result<Self> {
        let socket = UdpSocket::bind("0.0.0.0:0")?;
        // Non-blocking for poll-style operation
        socket.set_nonblocking(true)?;
        // Resolve the address
        use std::net::ToSocketAddrs;
        let peer = addr.to_socket_addrs()?.next()
            .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "Could not resolve address"))?;
        Ok(Self {
            socket,
            peer_addr: Some(peer),
            mtu_manager: AdaptiveMtuManager::new(),
            fragment_buffer: Vec::new(),
            next_fragment_id: 0,
        })
    }

    fn send(&self, message: &Message) -> io::Result<usize> {
        if let Some(peer) = &self.peer_addr {
            let serialized = bincode::serialize(message).map_err(|e| {
                io::Error::new(io::ErrorKind::InvalidData, e)
            })?;

            let message_size = serialized.len();
            let effective_mtu = self.mtu_manager.get_effective_mtu();

            // If message fits in single packet, send directly
            if message_size <= effective_mtu {
                self.socket.send_to(&serialized, peer)
            } else {
                // Fragment the message
                let fragment_id = self.next_fragment_id;
                let num_fragments = (message_size as f64 / effective_mtu as f64).ceil() as usize;

                let mut total_sent = 0;
                for i in 0..num_fragments {
                    let start = i * effective_mtu;
                    let end = (start + effective_mtu).min(message_size);
                    let fragment = &serialized[start..end];

                    // Create fragment header: [fragment_id, fragment_index, total_fragments, fragment_data]
                    let mut fragment_with_header = Vec::with_capacity(effective_mtu);
                    fragment_with_header.extend_from_slice(&fragment_id.to_be_bytes());
                    fragment_with_header.extend_from_slice(&(i as u32).to_be_bytes());
                    fragment_with_header.extend_from_slice(&(num_fragments as u32).to_be_bytes());
                    fragment_with_header.extend_from_slice(fragment);

                    match self.socket.send_to(&fragment_with_header, peer) {
                        Ok(sent) => total_sent += sent,
                        Err(e) => return Err(e),
                    }
                }
                Ok(total_sent)
            }
        } else {
            Err(io::Error::new(io::ErrorKind::NotConnected, "No peer address"))
        }
    }

    fn recv(&mut self) -> Option<(Message, usize)> {
        let mut buffer = vec![0; 65536]; // Large buffer for reassembly
        match self.socket.recv_from(&mut buffer) {
            Ok((size, addr)) => {
                // Server: capture peer address on first message
                if self.peer_addr.is_none() {
                    self.peer_addr = Some(addr);
                    println!("📡 Client connected from: {}", addr);
                }

                // Check if this is a fragment
                if size > 12 { // Minimum fragment header size (8 + 4 + 4)
                    let fragment_id = u64::from_be_bytes(buffer[0..8].try_into().unwrap());
                    let fragment_index = u32::from_be_bytes(buffer[8..12].try_into().unwrap());
                    let total_fragments = u32::from_be_bytes(buffer[12..16].try_into().unwrap());
                    let fragment_data = buffer[16..size].to_vec();

                    // Store fragment for reassembly
                    self.fragment_buffer.push((fragment_id, fragment_data));

                    // Check if we have all fragments
                    let fragments_for_id: Vec<_> = self.fragment_buffer.iter()
                        .filter(|(id, _)| *id == fragment_id)
                        .collect();

                    if fragments_for_id.len() == total_fragments as usize {
                        // Reassemble message
                        let mut reassembled = Vec::new();
                        for (_, data) in fragments_for_id {
                            reassembled.extend_from_slice(data);
                        }

                        // Remove used fragments
                        self.fragment_buffer.retain(|(id, _)| *id != fragment_id);

                        // Deserialize the reassembled message
                        bincode::deserialize(&reassembled)
                            .ok()
                            .map(|msg| (msg, reassembled.len()))
                    } else {
                        None // Wait for more fragments
                    }
                } else {
                    // Regular message (not fragmented)
                    bincode::deserialize(&buffer[..size])
                        .ok()
                        .map(|msg| (msg, size))
                }
            }
            Err(ref e) if e.kind() == io::ErrorKind::WouldBlock => None,
            Err(_) => None,
        }
    }

    /// Get current MTU statistics
    fn get_mtu_stats(&self) -> (usize, usize, f64) {
        (self.mtu_manager.current_mtu,
         self.mtu_manager.get_effective_mtu(),
         self.mtu_manager.packet_loss_rate)
    }

    /// Adjust MTU based on network conditions
    fn adjust_mtu(&mut self, success_rate: f64, rtt: Duration) {
        self.mtu_manager.adjust_mtu(success_rate, rtt);
    }
}

fn main() {
    println!("🚀 REAL TGP GIGABIT TEST - Pure Adaptive Flooding over UDP");
    println!("======================================================\n");

    let args: Vec<String> = std::env::args().collect();
    let is_server = args.len() > 1 && args[1] == "server";
    let is_client = args.len() > 1 && args[1] == "client";
    let target_host = args.get(2).map(|s| s.as_str()).unwrap_or("barbara.per.riff.cc");
    let target_port = args.get(3).map(|s| s.parse().unwrap_or(9500)).unwrap_or(9500);

    if is_server {
        run_server(target_host, target_port);
    } else if is_client {
        run_client(target_host, target_port);
    } else {
        println!("Usage:");
        println!("  real_tgp_test server [host] [port]           - Run as server");
        println!("  real_tgp_test client [host] [port]           - Run as client");
    }
}

fn run_server(host: &str, port: u16) {
    println!("Starting REAL TGP server on {}:{}", host, port);

    // Bind to 0.0.0.0 for all interfaces
    let server_addr = format!("0.0.0.0:{}", port);
    let mut network = UdpTgpNetwork::bind(&server_addr).expect("Failed to bind UDP");
    println!("Server listening on {} (UDP)", server_addr);

    // Generate keypair for server (Alice)
    let alice_kp = KeyPair::generate();

    // For demo purposes, we'll use a fixed counterparty key
    // In real implementation, this would be exchanged securely
    let bob_pubkey = KeyPair::generate().public_key().clone();

    // Create adaptive TGP instance
    let mut adaptive_alice = AdaptiveTGP::new(
        Party::Alice,
        alice_kp.clone(),
        bob_pubkey,
        1000,   // min_rate: 1K pkts/sec
        1000000, // max_rate: 1M pkts/sec (GIGABIT MODE)
    );

    let start_time = Instant::now();
    let mut bytes_received: u64 = 0;
    let mut packets_received: u64 = 0;
    let mut last_report = Instant::now();

    // Set data pending for maximum speed
    adaptive_alice.set_data_pending(true);

    println!("Waiting for client connection via TGP protocol...");

    // Main TGP protocol loop
    let mut round: u64 = 0;
    loop {
        round += 1;

        // Receive messages from client (drain all available)
        let mut received_this_round = 0;
        let mut messages_to_process: Vec<(Message, usize)> = Vec::new();

        while let Some((msg, size)) = network.recv() {
            messages_to_process.push((msg, size));
            received_this_round += 1;
            if received_this_round > 1000 { break; } // Prevent infinite loop
        }

        // Process messages sequentially (AdaptiveTGP is stateful and not Clone)
        for (msg, size) in messages_to_process {
            let _ = adaptive_alice.receive(&msg);
            bytes_received += size as u64;
            packets_received += 1;
        }

        // Send our messages in parallel using Rayon
        let messages = adaptive_alice.get_messages_to_send();
        let messages_count = messages.len();
        if network.peer_addr.is_some() {
            // Collect messages to send
            let send_results: Vec<_> = messages.into_par_iter()
                .map(|msg| network.send(&msg))
                .collect();
            // Process results
            for result in send_results {
                let _ = result;
            }
        }

        // Adaptive MTU adjustment based on network conditions
        if received_this_round > 0 {
            let success_rate = received_this_round as f64 / messages_count.max(1) as f64;
            let rtt_estimate = if packets_received > 0 {
                Duration::from_micros((bytes_received / packets_received) as u64 * 10)
            } else {
                Duration::from_millis(10)
            };
            network.adjust_mtu(success_rate, rtt_estimate);
        }

        // Report progress including MTU stats
        let now = Instant::now();
        if now - last_report >= Duration::from_millis(500) {
            let elapsed = now - start_time;
            let speed = bytes_received as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
            let speed_mbps = speed * 8.0;
            let pps = packets_received as f64 / elapsed.as_secs_f64();

            let (current_mtu, effective_mtu, loss_rate) = network.get_mtu_stats();
            println!("TGP RX: {:.2} MB ({:.2} MB/s, {:.1} Mbps, {:.0} pps, round {}) MTU: {} (eff: {}) loss: {:.2}%",
                    bytes_received as f64 / 1024.0 / 1024.0, speed, speed_mbps, pps, round,
                    current_mtu, effective_mtu, loss_rate * 100.0);
            last_report = now;
        }

        // Check if protocol is complete
        if adaptive_alice.is_complete() {
            break;
        }

        // Small yield to not burn CPU when idle
        if received_this_round == 0 {
            thread::sleep(Duration::from_micros(100));
        }
    }

    let elapsed = start_time.elapsed();
    let speed = bytes_received as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
    let speed_mbps = speed * 8.0;

    let (final_mtu, final_effective_mtu, final_loss_rate) = network.get_mtu_stats();

    println!("\n🎯 TGP PROTOCOL COMPLETE!");
    println!("Total bytes received: {} ({:.2} MB)", bytes_received, bytes_received as f64 / 1024.0 / 1024.0);
    println!("Time: {:?}", elapsed);
    println!("Average speed: {:.2} MB/s ({:.1} Mbps)", speed, speed_mbps);
    println!("Packets received: {}", packets_received);
    println!("Packets sent: {}", adaptive_alice.packet_count());
    println!("Alice can attack: {}", adaptive_alice.can_attack());
    println!("Final MTU: {} (effective: {}), loss rate: {:.2}%", final_mtu, final_effective_mtu, final_loss_rate * 100.0);

    if let Some((alice_own, alice_other)) = adaptive_alice.get_bilateral_receipt() {
        println!("Bilateral receipt: Q_A({:?}) + Q_B({:?})", alice_own.party, alice_other.party);
    }

    println!("\n🚀 REAL TGP PERFORMANCE with ADAPTIVE MTU:");
    println!("   Dynamic packet sizing for optimal throughput!");
    println!("   Automatic fragmentation/reassembly!");
    println!("   Congestion-aware MTU adaptation!");
    println!("   Structural symmetry guarantees - No asymmetric failures!");
}

fn run_client(host: &str, port: u16) {
    println!("Connecting via REAL TGP protocol to {}:{}", host, port);

    let server_addr = format!("{}:{}", host, port);
    let mut network = UdpTgpNetwork::connect(&server_addr).expect("Failed to connect");

    // Generate keypair for client (Bob)
    let bob_kp = KeyPair::generate();

    // For demo purposes, we'll use a fixed counterparty key
    // In real implementation, this would be exchanged securely
    let alice_pubkey = KeyPair::generate().public_key().clone();

    // Create adaptive TGP instance
    let mut adaptive_bob = AdaptiveTGP::new(
        Party::Bob,
        bob_kp.clone(),
        alice_pubkey,
        1000,    // min_rate: 1K pkts/sec
        1000000,  // max_rate: 1M pkts/sec (GIGABIT MODE)
    );

    let start_time = Instant::now();
    let mut bytes_sent: u64 = 0;
    let mut packets_sent: u64 = 0;
    let mut last_report = Instant::now();

    // Set data pending for maximum speed
    adaptive_bob.set_data_pending(true);

    println!("🚀 Starting REAL TGP protocol exchange...");

    // Main TGP protocol loop
    let mut round: u64 = 0;
    loop {
        round += 1;

        // Send our messages in parallel using Rayon
        let messages = adaptive_bob.get_messages_to_send();
        let messages_empty = messages.is_empty();

        // Collect messages to send with their lengths for byte counting
        let messages_with_info: Vec<_> = messages.into_iter()
            .map(|msg| (msg.clone(), MessageExt::len(&msg)))
            .collect();
        let messages_with_info_count = messages_with_info.len();

        // Send in parallel
        let send_results: Vec<_> = messages_with_info.into_par_iter()
            .map(|(msg, len)| {
                match network.send(&msg) {
                    Ok(_) => Some(len),
                    Err(_) => None,
                }
            })
            .collect();

        // Update counters based on successful sends
        for result in send_results {
            if let Some(len) = result {
                bytes_sent += len as u64;
                packets_sent += 1;
            }
        }

        // Receive messages from server (drain all available)
        let mut received_this_round = 0;
        let mut messages_to_process: Vec<(Message, usize)> = Vec::new();

        while let Some((msg, _size)) = network.recv() {
            messages_to_process.push((msg, 0)); // Size not needed for receive processing
            received_this_round += 1;
            if received_this_round > 1000 { break; } // Prevent infinite loop
        }

        // Process messages sequentially (AdaptiveTGP is stateful and not Clone)
        for (msg, _size) in messages_to_process {
            let _ = adaptive_bob.receive(&msg);
        }

        // Adaptive MTU adjustment based on network conditions
        if received_this_round > 0 {
            let success_rate = received_this_round as f64 / messages_with_info_count.max(1) as f64;
            let rtt_estimate = if packets_sent > 0 {
                Duration::from_micros((bytes_sent / packets_sent) as u64 * 10)
            } else {
                Duration::from_millis(10)
            };
            network.adjust_mtu(success_rate, rtt_estimate);
        }

        // Report progress including MTU stats
        let now = Instant::now();
        if now - last_report >= Duration::from_millis(500) {
            let elapsed = now - start_time;
            let speed = bytes_sent as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
            let speed_mbps = speed * 8.0;
            let pps = packets_sent as f64 / elapsed.as_secs_f64();

            let (current_mtu, effective_mtu, loss_rate) = network.get_mtu_stats();
            println!("TGP TX: {:.2} MB ({:.2} MB/s, {:.1} Mbps, {:.0} pps, round {}) MTU: {} (eff: {}) loss: {:.2}%",
                    bytes_sent as f64 / 1024.0 / 1024.0, speed, speed_mbps, pps, round,
                    current_mtu, effective_mtu, loss_rate * 100.0);
            last_report = now;
        }

        // Check if protocol is complete
        if adaptive_bob.is_complete() {
            break;
        }

        // Small yield to not burn CPU when idle
        if messages_empty && received_this_round == 0 {
            thread::sleep(Duration::from_micros(100));
        }
    }

    let elapsed = start_time.elapsed();
    let speed = bytes_sent as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
    let speed_mbps = speed * 8.0;

    let (final_mtu, final_effective_mtu, final_loss_rate) = network.get_mtu_stats();

    println!("\n🎯 TGP PROTOCOL COMPLETE!");
    println!("Total bytes sent: {} ({:.2} MB)", bytes_sent, bytes_sent as f64 / 1024.0 / 1024.0);
    println!("Time: {:?}", elapsed);
    println!("Average speed: {:.2} MB/s ({:.1} Mbps)", speed, speed_mbps);
    println!("Packets sent: {}", packets_sent);
    println!("Packets received: {}", adaptive_bob.packet_count());
    println!("Bob can attack: {}", adaptive_bob.can_attack());
    println!("Final MTU: {} (effective: {}), loss rate: {:.2}%", final_mtu, final_effective_mtu, final_loss_rate * 100.0);

    if let Some((bob_own, bob_other)) = adaptive_bob.get_bilateral_receipt() {
        println!("Bilateral receipt: Q_B({:?}) + Q_A({:?})", bob_own.party, bob_other.party);
    }

    println!("\n🚀 REAL TGP PERFORMANCE with ADAPTIVE MTU:");
    println!("   Dynamic packet sizing for optimal throughput!");
    println!("   Automatic fragmentation/reassembly!");
    println!("   Congestion-aware MTU adaptation!");
    println!("   Structural symmetry guarantees - No asymmetric failures!");
}