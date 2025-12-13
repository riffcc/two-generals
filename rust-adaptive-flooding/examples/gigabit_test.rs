use adaptive_flooding::AdaptiveFlooder;
use std::time::{Duration, Instant};
use std::io::{Read, Write};
use std::net::{TcpStream, TcpListener};
use std::thread;

fn main() {
    println!("Gigabit Speed Test - Full Performance");
    println!("====================================\n");

    let args: Vec<String> = std::env::args().collect();
    let is_server = args.len() > 1 && args[1] == "server";
    let is_client = args.len() > 1 && args[1] == "client";
    let target_host = args.get(2).map(|s| s.as_str()).unwrap_or("barbara.per.riff.cc");
    let target_port = args.get(3).map(|s| s.parse().unwrap_or(9500)).unwrap_or(9500);

    if is_server {
        run_server(target_port);
    } else if is_client {
        run_client(target_host, target_port);
    } else {
        println!("Usage:");
        println!("  gigabit_test server [port]           - Run as server");
        println!("  gigabit_test client [host] [port]    - Run as client");
    }
}

fn run_server(port: u16) {
    println!("Starting gigabit server on port {}...", port);

    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).expect("Failed to bind");
    println!("Server listening on 0.0.0.0:{}", port);

    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                println!("New connection: {}", stream.peer_addr().unwrap());

                // MAXIMUM PERFORMANCE CONFIGURATION
                let mut flooder = AdaptiveFlooder::new(1000, 1000000); // 1K-1M pkts/sec
                let start_time = Instant::now();
                let mut bytes_received = 0;
                let mut last_report = Instant::now();

                // Large buffer for gigabit speeds
                let mut buffer = [0; 65536]; // 64KB buffer
                loop {
                    match stream.read(&mut buffer) {
                        Ok(0) => {
                            println!("Client disconnected");
                            break;
                        }
                        Ok(n) => {
                            bytes_received += n;

                            // Echo back immediately with maximum rate
                            if flooder.should_send(true) {
                                stream.write_all(&buffer[..n]).unwrap();
                                stream.flush().unwrap();
                            }

                            // High-frequency progress reporting
                            let now = Instant::now();
                            if now - last_report >= Duration::from_millis(200) {
                                let elapsed = now - start_time;
                                let speed = bytes_received as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
                                let speed_mbps = speed * 8.0; // Convert to Mbps
                                println!("RX: {:.2} MB ({:.2} MB/s, {:.1} Mbps)",
                                        bytes_received as f64 / 1024.0 / 1024.0, speed, speed_mbps);
                                last_report = now;
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
                let speed_mbps = speed * 8.0;

                println!("\nConnection closed");
                println!("Total bytes received: {} ({:.2} MB)", bytes_received, bytes_received as f64 / 1024.0 / 1024.0);
                println!("Time: {:?}", elapsed);
                println!("Average speed: {:.2} MB/s ({:.1} Mbps)", speed, speed_mbps);
                println!("Packets sent: {}", flooder.packet_count());

                // Performance analysis
                if elapsed.as_secs() > 0 {
                    let gb_time = elapsed.as_secs_f64() * (1024.0 * 1024.0) / (bytes_received as f64 / 1024.0 / 1024.0);
                    println!("\n🚀 PERFORMANCE ANALYSIS:");
                    println!("   Estimated 1GB time: {:.1} seconds ({:.1} minutes)", gb_time, gb_time / 60.0);
                    println!("   Gigabit saturation: {:.1}%", (speed_mbps / 1000.0) * 100.0);
                }
            }
            Err(e) => {
                println!("Error accepting connection: {}", e);
            }
        }
    }
}

fn run_client(host: &str, port: u16) {
    println!("Connecting to {}:{}...", host, port);

    match TcpStream::connect(format!("{}:{}", host, port)) {
        Ok(mut stream) => {
            println!("Connected to server - MAXIMUM SPEED MODE!");

            // MAXIMUM PERFORMANCE CONFIGURATION
            let mut flooder = AdaptiveFlooder::new(1000, 1000000); // 1K-1M pkts/sec
            let start_time = Instant::now();
            let mut bytes_sent = 0;
            let mut bytes_received = 0;
            let mut last_report = Instant::now();

            // Test with 100MB to get good performance estimate
            let test_size = 1024 * 1024 * 100; // 100MB
            let test_data = vec![0u8; test_size];
            let mut remaining_data = test_data.len();
            let mut offset = 0;

            println!("🚀 Starting 100MB transfer at MAXIMUM SPEED...");

            // Send data in large chunks with minimal delay
            while remaining_data > 0 {
                let chunk_size = std::cmp::min(65536, remaining_data); // 64KB chunks

                if flooder.should_send(true) {
                    match stream.write(&test_data[offset..offset + chunk_size]) {
                        Ok(n) => {
                            bytes_sent += n;
                            remaining_data -= n;
                            offset += n;

                            // Read echo back
                            let mut buffer = [0; 65536];
                            match stream.read(&mut buffer) {
                                Ok(n) => bytes_received += n,
                                Err(_) => break,
                            }

                            // High-frequency progress reporting
                            let now = Instant::now();
                            if now - last_report >= Duration::from_millis(200) {
                                let elapsed = now - start_time;
                                let speed = bytes_sent as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
                                let speed_mbps = speed * 8.0;
                                let percent = bytes_sent as f64 / test_size as f64 * 100.0;
                                println!("TX: {:.1}% ({:.2} MB sent, {:.2} MB/s, {:.1} Mbps)",
                                        percent, bytes_sent as f64 / 1024.0 / 1024.0, speed, speed_mbps);
                                last_report = now;
                            }
                        }
                        Err(e) => {
                            println!("Error writing to server: {}", e);
                            break;
                        }
                    }
                }

                // Minimal sleep for maximum throughput
                thread::sleep(Duration::from_micros(100));
            }

            let elapsed = start_time.elapsed();
            let speed = bytes_sent as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
            let speed_mbps = speed * 8.0;

            println!("\n🎉 TEST COMPLETE!");
            println!("Bytes sent: {} ({:.2} MB)", bytes_sent, bytes_sent as f64 / 1024.0 / 1024.0);
            println!("Bytes received: {} ({:.2} MB)", bytes_received, bytes_received as f64 / 1024.0 / 1024.0);
            println!("Time: {:?}", elapsed);
            println!("Average speed: {:.2} MB/s ({:.1} Mbps)", speed, speed_mbps);
            println!("Packets sent: {}", flooder.packet_count());

            // Performance analysis
            let gb_time = elapsed.as_secs_f64() * 10.0; // 100MB * 10 = 1GB
            println!("\n🚀 PERFORMANCE ANALYSIS:");
            println!("   Estimated 1GB time: {:.1} seconds ({:.1} minutes)", gb_time, gb_time / 60.0);
            println!("   Estimated completion speed: {:.2} MB/s", 1024.0 / (gb_time / 1024.0));
            println!("   Gigabit saturation: {:.1}%", (speed_mbps / 1000.0) * 100.0);

            if speed_mbps > 900.0 {
                println!("   🎯 NEAR GIGABIT SPEED ACHIEVED!");
            } else if speed_mbps > 500.0 {
                println!("   📈 GOOD PERFORMANCE - Half gigabit+");
            } else {
                println!("   ⚠️  Network bottleneck detected");
            }
        }
        Err(e) => {
            println!("Failed to connect to server: {}", e);
        }
    }
}