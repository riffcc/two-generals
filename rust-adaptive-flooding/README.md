# Adaptive Flooding Protocol for TGP

This crate implements an adaptive flooding layer for the Two Generals Protocol (TGP). Instead of constant flooding, nodes can dynamically adjust flood rates based on data transfer needs, network conditions, and application requirements.

## Key Features

- **Drip Mode**: Slow to near-zero packets when idle (1-10 pkts/sec)
- **Burst Mode**: Instantly ramp to max speed when needed (10K-100K+ pkts/sec)
- **Symmetric Control**: Both parties can independently modulate
- **Proof Stapling Preserved**: Adaptive rate doesn't break bilateral construction

## Design

The adaptive flooding layer wraps the core TGP protocol and modulates the send rate based on application feedback. The core insight is that flood rate affects *when* proofs arrive, not *what* they contain, so bilateral construction is preserved.

### Rate Modulation Algorithm

The controller uses:
- **Exponential ramp-up** when data is needed (fast response)
- **Linear ramp-down** when idle (smooth decay)

### Flood Rate Modes

| Mode | Rate (pkts/sec) | Use Case |
|------|----------------|----------|
| Drip | 1-10 | Idle connection, keep-alive |
| Low | 100-1K | Small data trickle |
| Medium | 1K-10K | Normal transfer |
| Burst | 10K-100K | High-priority data |
| Max | 100K+ | Emergency flood |

## Usage

### Basic Example

```rust
use adaptive_flooding::{AdaptiveFlooder, AdaptiveTGP};
use two_generals::{crypto::KeyPair, types::Party};

// Create key pairs
let alice_kp = KeyPair::generate();
let bob_kp = KeyPair::generate();

// Create adaptive TGP instances
let mut adaptive_alice = AdaptiveTGP::new(
    Party::Alice,
    alice_kp.clone(),
    bob_kp.public_key().clone(),
    1,    // min_rate: 1 pkt/sec
    1000, // max_rate: 1000 pkts/sec
);

let mut adaptive_bob = AdaptiveTGP::new(
    Party::Bob,
    bob_kp,
    alice_kp.public_key().clone(),
    1,
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
    std::thread::sleep(std::time::Duration::from_millis(1));
}

assert!(adaptive_alice.is_complete());
assert!(adaptive_bob.is_complete());
```

### Standalone Flooder

```rust
use adaptive_flooding::AdaptiveFlooder;

let mut flooder = AdaptiveFlooder::new(1, 1000);

// Check if we should send a packet
if flooder.should_send(true) { // true = data pending
    // Send packet here
    println!("Sending packet at rate: {}", flooder.current_rate());
}

// Get current statistics
println!("Current rate: {} pkts/sec", flooder.current_rate());
println!("Total packets sent: {}", flooder.packet_count());
```

## Integration with TGP

The `AdaptiveTGP` struct wraps the core `TwoGenerals` protocol and adds adaptive rate control:

```rust
// The adaptive protocol respects the flood rate when sending messages
let messages = adaptive_tgp.get_messages_to_send();

// The rate is controlled by the data_pending flag
adaptive_tgp.set_data_pending(true);  // Ramp up to max rate
adaptive_tgp.set_data_pending(false); // Ramp down to min rate
```

## Testing

Run the test suite:

```bash
cargo test
```

## Implementation Details

### AdaptiveFloodController

Manages the rate modulation logic:
- `min_rate`: Minimum packets per second (drip mode)
- `max_rate`: Maximum packets per second (burst mode)
- `current_rate`: Current flood rate
- `ramp_up`: Acceleration rate (10% of max per second)
- `ramp_down`: Deceleration rate (linear decay to min)

### AdaptiveFlooder

Tracks timing and controls when packets should be sent:
- Uses `Instant` for precise timing
- Calculates intervals based on current rate
- Maintains packet count statistics

### AdaptiveTGP

Integrates adaptive flooding with TGP:
- Wraps `TwoGenerals` protocol
- Respects flood rate when sending messages
- Provides access to underlying protocol state

## Formal Properties

The adaptive flooding preserves the key TGP properties:

1. **Bilateral Construction**: If Q_A exists at any rate, Q_B is constructible
2. **Convergence**: Protocol still completes eventually under fair channel
3. **Symmetric Outcomes**: Both parties either ATTACK or ABORT together

The rate modulation is safe and bounded:
- `min_rate ≤ current_rate ≤ max_rate` for all time
- Rate changes are smooth (no abrupt transitions)

## Performance

The adaptive flooding adds minimal overhead:
- Timing calculation: O(1)
- Rate modulation: O(1)
- Memory: Constant (no dynamic allocation)

## License

AGPL-3.0
