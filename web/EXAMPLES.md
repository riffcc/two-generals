# TGP Web Visualizer - Usage Examples

Practical examples showing how to use each component of the Two Generals Protocol web demo.

---

## Table of Contents

1. [Protocol Simulation Examples](#protocol-simulation-examples)
2. [Visualization Examples](#visualization-examples)
3. [Performance Comparison Examples](#performance-comparison-examples)
4. [Animation Control Examples](#animation-control-examples)
5. [Custom Integration Examples](#custom-integration-examples)
6. [Testing Examples](#testing-examples)

---

## Protocol Simulation Examples

### Example 1: Basic Two-Party Simulation

```javascript
import { ProtocolSimulation } from './components/index.js';

// Create simulation with 50% packet loss
const sim = new ProtocolSimulation(0.5);

// Listen to events
sim.on('start', () => {
    console.log('Protocol started');
});

sim.on('phaseAdvance', ({ party, phase }) => {
    console.log(`${party} advanced to phase ${phase}`);
});

sim.on('complete', ({ outcome, alice, bob }) => {
    console.log(`Outcome: ${outcome}`);
    console.log(`Alice: Phase ${alice.phase}, Decision: ${alice.decision}`);
    console.log(`Bob: Phase ${bob.phase}, Decision: ${bob.decision}`);
});

// Start the simulation
sim.start();
```

**Output:**
```
Protocol started
Alice advanced to phase 1
Bob advanced to phase 1
Alice advanced to phase 2
Bob advanced to phase 2
...
Outcome: ATTACK
Alice: Phase 4, Decision: ATTACK
Bob: Phase 4, Decision: ATTACK
```

### Example 2: Step-by-Step Execution

```javascript
import { ProtocolSimulation } from './components/index.js';

const sim = new ProtocolSimulation(0.3);

// Manual stepping
while (!sim.isComplete()) {
    sim.step();

    const stats = sim.getStats();
    console.log(`Tick ${stats.tick}: ${stats.packetsDelivered} packets delivered`);

    // Check phases
    if (sim.alice.phase === 4 && sim.bob.phase === 4) {
        console.log('Both parties reached QUAD!');
        break;
    }
}
```

### Example 3: Protocol of Theseus Test

```javascript
import { runTheseusTest } from './components/index.js';

const results = await runTheseusTest({
    lossRates: [0, 25, 50, 75, 90, 95, 99],
    trialsPerRate: 10,
    maxTicks: 100000,

    onProgress: ({ completed, total, lossRate }) => {
        console.log(`${completed}/${total}: Testing ${lossRate}% loss...`);
    }
});

// Analyze results
results.forEach(({ lossRate, trials }) => {
    const symmetric = trials.filter(t => t.symmetric).length;
    const attacks = trials.filter(t => t.outcome === 'ATTACK').length;

    console.log(`${lossRate}%:`);
    console.log(`  Symmetric: ${symmetric}/${trials.length}`);
    console.log(`  Attacks: ${attacks}/${trials.length}`);
});
```

---

## Visualization Examples

### Example 4: Packet Flow Visualization

```html
<svg id="packet-viz" width="800" height="300"></svg>

<script type="module">
import { PacketVisualizer } from './components/index.js';

const viz = new PacketVisualizer('#packet-viz');

// Add packet
viz.addPacket({
    id: 1,
    msg: { type: 'C', proof: { /* ... */ } },
    direction: 'alice-to-bob',
    progress: 0,
    isLost: false,
    startTick: 0
});

// Update packet position (called in animation loop)
function animate() {
    viz.updatePacket({ id: 1, progress: progress });
    requestAnimationFrame(animate);
}
animate();

// Remove when delivered
viz.removePacket({ id: 1, isLost: false });
</script>
```

### Example 5: Battlefield Scene

```html
<div id="battlefield"></div>

<script type="module">
import { BattlefieldScene } from './explainer.js';

const battlefield = new BattlefieldScene('#battlefield');
battlefield.init();

// Run the dilemma scenario
battlefield.startScenario('dilemma');

// After 5 seconds, try alice attacking alone
setTimeout(() => {
    battlefield.startScenario('alice_alone');
}, 5000);

// Reset and try coordinated attack
setTimeout(() => {
    battlefield.reset();
    battlefield.startScenario('both_attack');
}, 10000);
</script>
```

### Example 6: Proof Merging Animation

```html
<div id="proof-merging"></div>

<script type="module">
import { ProofMergingAnimation } from './explainer.js';

const merging = new ProofMergingAnimation('#proof-merging');
merging.init();

// Auto-play through all steps
merging.startAutoPlay();

// Or manual control
document.getElementById('next-btn').addEventListener('click', () => {
    merging.nextStep();
});

document.getElementById('prev-btn').addEventListener('click', () => {
    merging.prevStep();
});
</script>
```

---

## Performance Comparison Examples

### Example 7: Run Performance Test

```javascript
import { PerformanceTestHarness } from './performance.js';

const harness = new PerformanceTestHarness();

// Set up progress callback
harness.on('progress', ({ completed, total, protocol, lossRate }) => {
    console.log(`[${completed}/${total}] Testing ${protocol} at ${lossRate}% loss`);
});

// Run comparison
const results = await harness.runComparison({
    lossRates: [10, 50, 90],
    trialsPerRate: 5,
    maxTicks: 50000,
    protocols: ['TGP', 'TCP', 'QUIC', 'UDP']
});

// Extract TGP data
const tgpData = results.protocols.find(p => p.name === 'TGP');

tgpData.data.forEach(point => {
    console.log(`Loss ${point.lossRate}%:`);
    console.log(`  Success Rate: ${point.successRate}%`);
    console.log(`  Symmetry Rate: ${point.symmetryRate}%`);
    console.log(`  Avg Round Trips: ${point.avgRoundTrips.toFixed(0)}`);
});
```

**Output:**
```
Loss 10%:
  Success Rate: 100%
  Symmetry Rate: 100%
  Avg Round Trips: 12
Loss 50%:
  Success Rate: 98%
  Symmetry Rate: 100%
  Avg Round Trips: 45
Loss 90%:
  Success Rate: 87%
  Symmetry Rate: 100%
  Avg Round Trips: 523
```

### Example 8: Create Custom Protocol Simulator

```javascript
import { ProtocolSimulator } from './performance.js';

class MyCustomProtocol extends ProtocolSimulator {
    constructor(lossRate) {
        super('MyProtocol', lossRate);
        // Custom initialization
    }

    run(maxTicks = 10000) {
        this.startTime = performance.now();

        // Custom protocol logic
        for (let tick = 0; tick < maxTicks; tick++) {
            // Send messages
            if (this.sendMessage()) {
                // Message delivered
                this.completed = true;
                break;
            }
            this.roundTrips = tick + 1;
        }

        this.endTime = performance.now();
        return this.getStats();
    }
}

// Use it
const sim = new MyCustomProtocol(0.5);
const result = sim.run();
console.log(result);
```

### Example 9: Visualize Results with D3

```javascript
import * as d3 from 'd3';
import { PerformanceVisualizer } from './performance.js';

// Create visualizer
const viz = new PerformanceVisualizer('chart-container');

// Render data
viz.render(comparisonData);

// The visualizer automatically creates:
// - Success rate chart
// - Symmetry rate chart
// - Messages required chart
// - Completion time chart
// - Summary statistics
```

---

## Animation Control Examples

### Example 10: Add Animation Controls

```javascript
import { createAnimationControls } from './components/animation-controls.js';

const container = document.getElementById('my-animation');

const controls = createAnimationControls({
    container: container,
    defaultSpeed: 1.0,
    minSpeed: 0.25,
    maxSpeed: 2.0,
    step: 0.25,
    showStepControls: true,

    onSpeedChange: (speed) => {
        myAnimation.speed = speed;
    },

    onPlayPause: (isPlaying) => {
        if (isPlaying) {
            myAnimation.start();
        } else {
            myAnimation.pause();
        }
    },

    onReset: () => {
        myAnimation.reset();
    },

    onStep: (direction) => {
        myAnimation.step(direction);  // +1 or -1
    }
});

// Programmatic control
controls.setSpeed(1.5);
controls.setPlaying(true);
```

### Example 11: Custom Animation with Controls

```javascript
class MyAnimation {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.frame = 0;
        this.speed = 1.0;
        this.isPlaying = false;

        // Create controls
        this.controls = createAnimationControls({
            container: this.container,
            onSpeedChange: (speed) => { this.speed = speed; },
            onPlayPause: (playing) => {
                this.isPlaying = playing;
                if (playing) this.animate();
            },
            onReset: () => { this.reset(); }
        });
    }

    animate() {
        if (!this.isPlaying) return;

        this.frame += this.speed;
        this.render();

        requestAnimationFrame(() => this.animate());
    }

    render() {
        // Your animation logic here
        console.log(`Frame: ${this.frame}`);
    }

    reset() {
        this.frame = 0;
        this.render();
    }
}

const myAnim = new MyAnimation('my-container');
```

---

## Custom Integration Examples

### Example 12: Embed in External Website

```html
<!DOCTYPE html>
<html>
<head>
    <title>TGP Embedded Demo</title>
    <link rel="stylesheet" href="https://example.com/tgp/style.css">
</head>
<body>
    <div id="tgp-visualizer"></div>

    <script type="module">
        import { ProtocolSimulation, PacketVisualizer } from 'https://example.com/tgp/components/index.js';

        const sim = new ProtocolSimulation(0.5);
        const viz = new PacketVisualizer('#tgp-visualizer');

        sim.on('packetSent', packet => viz.addPacket(packet));
        sim.on('tick', () => {
            sim.packets.forEach(p => viz.updatePacket(p));
        });

        sim.start();
    </script>
</body>
</html>
```

### Example 13: React Integration

```jsx
import React, { useEffect, useRef } from 'react';
import { ProtocolSimulation } from './components/index.js';

function TGPSimulator({ lossRate }) {
    const simRef = useRef(null);
    const [stats, setStats] = React.useState(null);

    useEffect(() => {
        const sim = new ProtocolSimulation(lossRate);
        simRef.current = sim;

        sim.on('tick', () => {
            setStats(sim.getStats());
        });

        sim.start();

        return () => {
            sim.reset();
        };
    }, [lossRate]);

    return (
        <div>
            <h2>Protocol Stats</h2>
            {stats && (
                <div>
                    <p>Tick: {stats.tick}</p>
                    <p>Packets Sent: {stats.packetsSent}</p>
                    <p>Loss Rate: {stats.actualLossRate}%</p>
                </div>
            )}
        </div>
    );
}
```

### Example 14: Vue Integration

```vue
<template>
  <div>
    <svg ref="visualization"></svg>
    <button @click="start">Start</button>
    <button @click="reset">Reset</button>
  </div>
</template>

<script>
import { ProtocolSimulation, PacketVisualizer } from './components/index.js';

export default {
  data() {
    return {
      sim: null,
      viz: null
    };
  },

  mounted() {
    this.sim = new ProtocolSimulation(0.5);
    this.viz = new PacketVisualizer(this.$refs.visualization);

    this.sim.on('packetSent', packet => {
      this.viz.addPacket(packet);
    });
  },

  methods: {
    start() {
      this.sim.start();
    },

    reset() {
      this.sim.reset();
      this.viz.clear();
    }
  }
};
</script>
```

---

## Testing Examples

### Example 15: Unit Test for Protocol Logic

```javascript
import { ProtocolParty, Phase } from './components/index.js';

describe('ProtocolParty', () => {
    test('starts at COMMITMENT phase', () => {
        const alice = new ProtocolParty('Alice', true);
        alice.start();
        expect(alice.phase).toBe(Phase.COMMITMENT);
    });

    test('advances to DOUBLE when receiving commitment', () => {
        const alice = new ProtocolParty('Alice', true);
        alice.start();

        const bobCommitment = {
            type: 'C',
            proof: { /* mock proof */ }
        };

        const advanced = alice.receiveMessage(bobCommitment);
        expect(advanced).toBe(true);
        expect(alice.phase).toBe(Phase.DOUBLE);
    });

    test('reaches QUAD and can attack', () => {
        const alice = new ProtocolParty('Alice', true);
        // ... simulate receiving all proofs
        expect(alice.phase).toBe(Phase.QUAD);
        expect(alice.canAttack()).toBe(true);
    });
});
```

### Example 16: Integration Test for UI

```javascript
import { fireEvent, screen } from '@testing-library/dom';
import { UIController } from './visualizer.js';

test('protocol starts when start button clicked', async () => {
    const controller = new UIController();
    controller.init();

    const startBtn = screen.getByText('Start');
    fireEvent.click(startBtn);

    // Wait for first phase advance
    await screen.findByText(/Alice.*Phase 1/);

    expect(controller.sim.isRunning).toBe(true);
});
```

### Example 17: Performance Benchmark

```javascript
import { ProtocolSimulation } from './components/index.js';

function benchmarkProtocol(lossRate, trials = 100) {
    const times = [];

    for (let i = 0; i < trials; i++) {
        const sim = new ProtocolSimulation(lossRate);
        const start = performance.now();

        sim.run(10000);

        const duration = performance.now() - start;
        times.push(duration);
    }

    const avg = times.reduce((sum, t) => sum + t, 0) / trials;
    const min = Math.min(...times);
    const max = Math.max(...times);

    console.log(`Loss Rate: ${lossRate * 100}%`);
    console.log(`  Avg: ${avg.toFixed(2)}ms`);
    console.log(`  Min: ${min.toFixed(2)}ms`);
    console.log(`  Max: ${max.toFixed(2)}ms`);
}

benchmarkProtocol(0.5);
```

---

## Complete Working Example

### Example 18: Full Page Integration

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TGP Demo</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>Two Generals Protocol Demo</h1>

        <!-- Controls -->
        <div class="controls">
            <label>
                Loss Rate: <span id="loss-display">50%</span>
                <input type="range" id="loss-rate" min="0" max="100" value="50">
            </label>
            <button id="start-btn">Start</button>
            <button id="reset-btn">Reset</button>
        </div>

        <!-- Visualization -->
        <svg id="packet-viz" width="800" height="300"></svg>

        <!-- Stats -->
        <div id="stats"></div>

        <!-- Outcome -->
        <div id="outcome"></div>
    </div>

    <script type="module">
        import { ProtocolSimulation, PacketVisualizer } from './components/index.js';

        // Elements
        const lossRateSlider = document.getElementById('loss-rate');
        const lossDisplay = document.getElementById('loss-display');
        const startBtn = document.getElementById('start-btn');
        const resetBtn = document.getElementById('reset-btn');
        const statsDiv = document.getElementById('stats');
        const outcomeDiv = document.getElementById('outcome');

        // State
        let sim = null;
        let viz = null;

        // Initialize
        function init() {
            const lossRate = parseInt(lossRateSlider.value) / 100;

            sim = new ProtocolSimulation(lossRate);
            viz = new PacketVisualizer('#packet-viz');

            sim.on('start', () => {
                outcomeDiv.textContent = 'Running...';
            });

            sim.on('tick', () => {
                updateStats();
                sim.packets.forEach(p => viz.updatePacket(p));
            });

            sim.on('packetSent', packet => {
                viz.addPacket(packet);
            });

            sim.on('packetArrived', packet => {
                viz.removePacket(packet);
            });

            sim.on('complete', ({ outcome, alice, bob }) => {
                outcomeDiv.innerHTML = `
                    <h2>Outcome: ${outcome}</h2>
                    <p>Alice: Phase ${alice.phase}, Decision: ${alice.decision}</p>
                    <p>Bob: Phase ${bob.phase}, Decision: ${bob.decision}</p>
                `;
            });
        }

        function updateStats() {
            const stats = sim.getStats();
            statsDiv.innerHTML = `
                <div>Tick: ${stats.tick}</div>
                <div>Packets Sent: ${stats.packetsSent}</div>
                <div>Packets Delivered: ${stats.packetsDelivered}</div>
                <div>Loss Rate: ${stats.actualLossRate}%</div>
            `;
        }

        // Event handlers
        lossRateSlider.addEventListener('input', (e) => {
            lossDisplay.textContent = `${e.target.value}%`;
        });

        startBtn.addEventListener('click', () => {
            if (!sim) init();
            sim.start();
        });

        resetBtn.addEventListener('click', () => {
            if (sim) sim.reset();
            if (viz) viz.clear();
            init();
            statsDiv.textContent = '';
            outcomeDiv.textContent = '';
        });

        // Initialize on load
        init();
    </script>
</body>
</html>
```

---

## Next Steps

- See [API.md](./API.md) for complete API reference
- See [README.md](../README.md) for project overview
- See [tests/README.md](./tests/README.md) for testing guide

---

## License

AGPLv3 - See LICENSE file for details.

---

**e cinere surgemus** 🔥
