use adaptive_flooding::AdaptiveFlooder;
use std::time::{Duration, Instant};
use std::io::{Read, Write};
use std::net::{TcpStream, TcpListener};
use std::thread;

fn main() {
    println!("Simple Speed Test");
    println!("==================\n");

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
        println!("  simple_test server [port]           - Run as server");
        println!("  simple_test client [host] [port]    - Run as client");
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

                let mut flooder = AdaptiveFlooder::new(10, 1000);
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

                            // Echo back to client
                            if flooder.should_send(true) {
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
    println!("Connecting to {}:{}...", host, port);

    match TcpStream::connect(format!("{}:{}", host, port)) {
        Ok(mut stream) => {
            println!("Connected to server");

            let mut flooder = AdaptiveFlooder::new(10, 1000);
            let start_time = Instant::now();
            let mut bytes_sent = 0;
            let mut bytes_received = 0;

            // Test data - 100KB of data
            let test_data = vec![0u8; 1024 * 100]; // 100KB
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
        }
        Err(e) => {
            println!("Failed to connect to server: {}", e);
        }
    }
}