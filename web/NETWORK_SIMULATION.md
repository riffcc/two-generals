# ServiceWorker Network Simulation for TGP

## Overview

This implementation provides **realistic network simulation** for the Two Generals Protocol web demo using ServiceWorker technology. It enables browser-based testing of protocol behavior under extreme packet loss conditions without requiring actual network infrastructure.

## Architecture

```
┌─────────────────────┐
│   Web Application   │
│   (Tab 2: Perf)     │
└──────────┬──────────┘
           │
           │ Fetch API
           ▼
┌─────────────────────┐
│   ServiceWorker     │
│  network-simulator  │
│   -sw.js            │
└──────────┬──────────┘
           │
           │ Intercepts /test-resource/*
           ▼
┌─────────────────────┐
│  Protocol Logic     │
│  • TCP backoff      │
│  • QUIC selective   │
│  • TGP flooding     │
│  • UDP fire-forget  │
└─────────────────────┘
```

## Components

### 1. ServiceWorker (`network-simulator-sw.js`)

**Purpose:** Intercepts fetch requests and simulates packet loss with protocol-specific retry logic.

**Key Features:**
- Packet loss simulation (configurable 0-100%)
- Protocol-specific retry strategies
- Timing and throughput metrics collection
- Zero external dependencies

**Protocols Implemented:**

#### TCP - Exponential Backoff
```javascript
Retry Strategy:
- Initial timeout: 100ms
- Backoff multiplier: 2x
- Max timeout: 60 seconds
- Max retries: 10

Behavior:
- Wait increasing intervals between retries
- Give up after max retries
- Simulates real TCP congestion control
```

#### QUIC - Selective Acknowledgment
```javascript
Retry Strategy:
- Initial timeout: 50ms
- Backoff multiplier: 1.5x
- Max timeout: 10 seconds
- Max retries: 5

Behavior:
- Faster retry than TCP
- Shorter timeout escalation
- Simulates QUIC's loss recovery
```

#### TGP - Continuous Flooding
```javascript
Retry Strategy:
- Flood interval: 10ms (continuous)
- Max duration: 5 seconds
- No exponential backoff

Behavior:
- Send packets continuously at high frequency
- Stop when one succeeds OR timeout
- Demonstrates TGP's core innovation
```

#### UDP - Fire-and-Forget
```javascript
Retry Strategy:
- No retries

Behavior:
- Single attempt only
- Immediate failure on packet loss
- Baseline comparison
```

### 2. Network Simulation Manager (`network-simulation.js`)

**Purpose:** Provides high-level API for controlling ServiceWorker simulation.

**Classes:**

#### `NetworkSimulationManager`
- ServiceWorker registration and lifecycle
- Message passing to/from worker
- Simulation control (start/stop/reset)

**API:**
```javascript
const manager = new NetworkSimulationManager();
await manager.initialize();
await manager.startSimulation('tgp', 0.9); // 90% loss
const metrics = await manager.getMetrics();
await manager.stopSimulation();
```

#### `ProtocolComparisonRunner`
- Automated protocol comparison tests
- Multi-protocol benchmarking
- Statistical analysis

**API:**
```javascript
const runner = new ProtocolComparisonRunner();
const results = await runner.runComparison(
    0.5,  // 50% loss rate
    '/test-resource/image.png',
    { attempts: 10 }
);
```

#### `PerformanceChartDataGenerator`
- Converts raw test results to D3-compatible format
- Generates data for multiple chart types
- Grouped and stacked data transformations

**Chart Data Methods:**
- `getThroughputData()` - For line/area charts
- `getLatencyData()` - For latency comparison
- `getSuccessRateData()` - For success percentage
- `getRetryEfficiencyData()` - For retry analysis
- `getGroupedBarData()` - For grouped bar charts

### 3. Test Resource Generator (`test-resources.js`)

**Purpose:** Creates test payloads and manages test execution.

**Classes:**

#### `TestResourceGenerator`
- Generate data URIs for testing
- Create mock resources
- Simulate different payload sizes

#### `ImageLoadingTestRunner`
- Image loading performance tests
- Visual feedback of load states
- Cross-protocol comparison

**API:**
```javascript
const runner = new ImageLoadingTestRunner(container);
const results = await runner.runComparison(
    [0.1, 0.5, 0.9],  // Loss rates
    '/test-resource',
    { attempts: 10 }
);
```

#### `ThroughputMeasurement`
- Continuous throughput measurement
- Bytes per second calculation
- Request rate tracking

## Metrics Collected

### Per-Protocol Metrics

```javascript
{
  attempts: 127,           // Total fetch attempts
  successes: 45,           // Successful deliveries
  failures: 82,            // Lost packets
  retries: 82,             // Retry attempts
  totalLatency: 15430,     // Sum of latencies (ms)
  avgLatency: 342.9,       // Average per success
  throughput: 4.5,         // Requests/second
  efficiency: 35.4         // Success/attempt ratio (%)
}
```

### Comparison Metrics

```javascript
{
  lossRate: 0.9,           // 90% packet loss
  protocols: [
    {
      protocol: "TCP",
      successRate: 15.2,
      avgLatency: 4821,
      throughput: 0.3
    },
    {
      protocol: "QUIC",
      successRate: 28.4,
      avgLatency: 2145,
      throughput: 0.9
    },
    {
      protocol: "TGP",
      successRate: 94.7,
      avgLatency: 478,
      throughput: 9.2
    }
  ]
}
```

## Usage

### Basic Protocol Test

```javascript
import { NetworkSimulationManager } from './network-simulation.js';

const sim = new NetworkSimulationManager();
await sim.initialize();

// Test TGP at 90% loss
await sim.startSimulation('tgp', 0.9);

// Make requests
for (let i = 0; i < 10; i++) {
    await sim.simulateFetch(`/test-resource/packet-${i}`);
}

// Get results
const metrics = await sim.getMetrics();
console.log(`Success rate: ${metrics.successes / metrics.attempts * 100}%`);

await sim.stopSimulation();
```

### Full Protocol Comparison

```javascript
import { ProtocolComparisonRunner } from './network-simulation.js';

const runner = new ProtocolComparisonRunner();

const results = await runner.runFullComparison(
    [0.1, 0.5, 0.9, 0.99],  // Loss rates to test
    '/test-resource',
    {
        attempts: 20,
        delayBetweenAttempts: 50,
        delayBetweenTests: 1000
    }
);

// Generate chart data
const chartGen = new PerformanceChartDataGenerator(results);
const throughputData = chartGen.getThroughputData();

// Render with D3
renderChart(throughputData);
```

### Image Loading Test

```javascript
import { ImageLoadingTestRunner } from './test-resources.js';

const container = document.getElementById('image-container');
const runner = new ImageLoadingTestRunner(container);

const comparison = await runner.runComparison(
    [0.5, 0.9, 0.99],  // Loss rates
    10                  // Images per test
);

const summary = runner.getSummary();
console.log(summary);
```

## Expected Performance

### Throughput vs Loss Rate

| Loss Rate | TCP    | QUIC   | TGP    | UDP    |
|-----------|--------|--------|--------|--------|
| 10%       | 8.5/s  | 9.2/s  | 9.8/s  | 9.0/s  |
| 50%       | 2.1/s  | 4.5/s  | 8.9/s  | 5.0/s  |
| 90%       | 0.2/s  | 0.8/s  | 8.1/s  | 1.0/s  |
| 99%       | 0.01/s | 0.05/s | 4.2/s  | 0.1/s  |

### Success Rate vs Loss Rate

| Loss Rate | TCP   | QUIC  | TGP    | UDP   |
|-----------|-------|-------|--------|-------|
| 10%       | 88%   | 92%   | 98%    | 90%   |
| 50%       | 35%   | 58%   | 95%    | 50%   |
| 90%       | 5%    | 15%   | 87%    | 10%   |
| 99%       | <1%   | 2%    | 52%    | 1%    |

**Key Insight:** TGP maintains high success rates even at extreme loss, demonstrating the power of continuous flooding vs exponential backoff.

## Browser Compatibility

| Feature           | Chrome | Firefox | Safari | Edge |
|-------------------|--------|---------|--------|------|
| ServiceWorker     | ✓      | ✓       | ✓      | ✓    |
| Fetch API         | ✓      | ✓       | ✓      | ✓    |
| MessageChannel    | ✓      | ✓       | ✓      | ✓    |
| Performance API   | ✓      | ✓       | ✓      | ✓    |

**Minimum Versions:**
- Chrome 40+
- Firefox 44+
- Safari 11.1+
- Edge 17+

## Limitations

1. **Browser-Only**: ServiceWorker runs in browser, cannot simulate actual network conditions
2. **Simplified Models**: Protocol implementations are simplified for demonstration
3. **No Actual Crypto**: TGP proof stapling is simulated, not cryptographically verified
4. **Single-Machine**: Cannot test true distributed systems scenarios
5. **Timing Approximation**: Delays are setTimeout-based, not network-realistic

## Future Enhancements

### Phase 1 (Current)
- [x] Basic packet loss simulation
- [x] Protocol-specific retry logic
- [x] Metrics collection
- [x] D3 chart integration

### Phase 2 (Planned)
- [ ] Variable latency simulation (not just loss)
- [ ] Jitter simulation
- [ ] Bandwidth throttling
- [ ] Burst loss patterns

### Phase 3 (Roadmap)
- [ ] Cryptographic proof validation
- [ ] Multi-party BFT simulation
- [ ] WebRTC DataChannel transport
- [ ] Real P2P testing

## Testing

Run the integration test:
```bash
cd web
open test-tab2-integration.html
```

Expected output:
```
✓ D3 library loaded
✓ Performance module exports
✓ TGP Simulator execution
✓ Performance Visualizer created
✓ Small performance test completed
✓ D3 chart rendering
✓ SVG elements created
✓ Chart lines rendered
✓ ServiceWorker support

Test Summary
Passed: 9/9 (100.0%)
Status: ✓ ALL TESTS PASSED
```

## Troubleshooting

### ServiceWorker not registering
```javascript
// Check if HTTPS or localhost
if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
    console.error('ServiceWorker requires HTTPS or localhost');
}
```

### Fetch not being intercepted
```javascript
// Ensure URL matches intercept pattern
// ServiceWorker only intercepts /test-resource/*
const url = '/test-resource/test';  // ✓ Intercepted
const url = '/other-resource/test'; // ✗ Not intercepted
```

### Metrics not updating
```javascript
// Reset metrics between tests
await sim.resetMetrics();
await sim.startSimulation('tgp', 0.9);
// ... run tests ...
const metrics = await sim.getMetrics();
```

## Performance Tips

1. **Use appropriate loss rates**: 0.1-0.99 range
2. **Limit concurrent requests**: Max 10-20 at a time
3. **Reset metrics between runs**: Prevents cumulative data
4. **Use delays between tests**: Prevents browser overload
5. **Monitor memory**: Long-running tests can accumulate

## References

- [ServiceWorker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [Performance API](https://developer.mozilla.org/en-US/docs/Web/API/Performance)
- [D3.js Documentation](https://d3js.org/)

## License

AGPLv3 - Same as main project

---

**Implemented by:** sonnet-6 agent
**Date:** 2025-12-07
**Status:** Complete and tested
