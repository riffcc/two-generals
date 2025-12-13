use adaptive_flooding::AdaptiveFlooder;
use std::time::{Duration, Instant};
use std::io::{Read, Write};
use std::net::{TcpStream, TcpListener};
use std::thread;

fn main() {
    println!("1GB Transfer Speed Test");
    println!("=======================\n");

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
        println!("  gb_test server [port]           - Run as server");
        println!("  gb_test client [host] [port]    - Run as client");
    }
}

fn run_server(port: u16) {
    println!("Starting 1GB server on port {}...", port);

    let listener = TcpListener::bind(format!("0.0.0.0:{}", port)).expect("Failed to bind");
    println!("Server listening on 0.0.0.0:{}", port);

    for stream in listener.incoming() {
        match stream {
            Ok(mut stream) => {
                println!("New connection: {}", stream.peer_addr().unwrap());

                // Optimized for high throughput
                let mut flooder = AdaptiveFlooder::new(100, 100000); // 100-100K pkts/sec
                let start_time = Instant::now();
                let mut bytes_received = 0;
                let mut last_report = Instant::now();

                // Read data from client with larger buffer
                let mut buffer = [0; 8192]; // 8KB buffer for better throughput
                loop {
                    match stream.read(&mut buffer) {
                        Ok(0) => {
                            println!("Client disconnected");
                            break;
                        }
                        Ok(n) => {
                            bytes_received += n;

                            // Echo back to client with high rate
                            if flooder.should_send(true) {
                                stream.write_all(&buffer[..n]).unwrap();
                                stream.flush().unwrap();
                            }

                            // Progress reporting
                            let now = Instant::now();
                            if now - last_report >= Duration::from_secs(1) {
                                let elapsed = now - start_time;
                                let speed = bytes_received as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
                                println!("Progress: {:.2} MB received, {:.2} MB/s",
                                        bytes_received as f64 / 1024.0 / 1024.0, speed);
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

                println!("\nConnection closed");
                println!("Total bytes received: {} ({:.2} MB)", bytes_received, bytes_received as f64 / 1024.0 / 1024.0);
                println!("Time: {:?}", elapsed);
                println!("Average speed: {:.2} MB/s", speed);
                println!("Packets sent: {}", flooder.packet_count());

                // Estimate for 1GB
                if bytes_received > 0 {
                    let gb_time = elapsed.as_secs_f64() * (1024.0 * 1024.0) / (bytes_received as f64 / 1024.0 / 1024.0);
                    println!("\nEstimated time for 1GB: {:.1} seconds ({:.1} minutes)", gb_time, gb_time / 60.0);
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
            println!("Connected to server");

            // Optimized for high throughput
            let mut flooder = AdaptiveFlooder::new(100, 100000); // 100-100K pkts/sec
            let start_time = Instant::now();
            let mut bytes_sent = 0;
            let mut bytes_received = 0;
            let mut last_report = Instant::now();

            // Test data - 100MB for realistic testing (1GB would take too long for demo)
            let test_size = 1024 * 1024 * 100; // 100MB
            let test_data = vec![0u8; test_size];
            let mut remaining_data = test_data.len();
            let mut offset = 0;

            println!("Starting 100MB transfer test...");

            // Send data in larger chunks
            while remaining_data > 0 {
                let chunk_size = std::cmp::min(8192, remaining_data); // 8KB chunks

                if flooder.should_send(true) {
                    match stream.write(&test_data[offset..offset + chunk_size]) {
                        Ok(n) => {
                            bytes_sent += n;
                            remaining_data -= n;
                            offset += n;

                            // Read echo back
                            let mut buffer = [0; 8192];
                            match stream.read(&mut buffer) {
                                Ok(n) => bytes_received += n,
                                Err(_) => break,
                            }

                            // Progress reporting
                            let now = Instant::now();
                            if now - last_report >= Duration::from_secs(1) {
                                let elapsed = now - start_time;
                                let speed = bytes_sent as f64 / elapsed.as_secs_f64() / 1024.0 / 1024.0;
                                let percent = bytes_sent as f64 / test_size as f64 * 100.0;
                                println!("Progress: {:.1}% ({:.2} MB sent, {:.2} MB/s)",
                                        percent, bytes_sent as f64 / 1024.0 / 1024.0, speed);
                                last_report = now;
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
            println!("Average speed: {:.2} MB/s", speed);
            println!("Packets sent: {}", flooder.packet_count());

            // Estimate for 1GB
            let gb_time = elapsed.as_secs_f64() * 10.0; // 100MB * 10 = 1GB
            println!("\nEstimated time for 1GB: {:.1} seconds ({:.1} minutes)", gb_time, gb_time / 60.0);
            println!("Estimated completion: {} MB/s", 1024.0 / (gb_time / 1024.0));
        }
        Err(e) => {
            println!("Failed to connect to server: {}", e);
        }
    }
}