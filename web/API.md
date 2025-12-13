# Two Generals Protocol (TGP) - Web Visualizer API Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Animation Controls](#animation-controls)
5. [Protocol Simulation](#protocol-simulation)
6. [Visualizations](#visualizations)
7. [Usage Examples](#usage-examples)
8. [Integration Guide](#integration-guide)
9. [API Reference](#api-reference)

---

## Overview

The TGP Web Visualizer is a comprehensive, interactive educational tool that demonstrates the Two Generals Protocol through multiple visualization techniques. It uses D3.js for rendering, modular ES6 architecture, and provides both standalone and embeddable components.

### Key Features

- **Interactive Protocol Simulation**: Step-by-step visualization of proof escalation (C → D → T → Q)
- **Performance Comparison**: Real-time benchmarks comparing TGP against TCP, QUIC, and UDP
- **Educational Explainer**: Multi-section tutorial with animations showing why TGP works
- **Protocol of Theseus Test**: Visual demonstration of deterministic coordination under extreme packet loss
- **Accessibility**: Full WCAG 2.1 AA compliance with keyboard navigation and screen reader support

### Technology Stack

- **D3.js v7**: Data-driven visualizations
- **Vite**: Module bundling and development server
- **ES6 Modules**: Clean, tree-shakeable architecture
- **CSS Custom Properties**: Theme-able design system
- **No framework dependencies**: Pure JavaScript for maximum portability

---

## Architecture

### Module Structure

```
web/
├── index.html              # Main entry point
├── visualizer.js           # Main controller and Tab 3 (Interactive Visualizer)
├── tabs.js                 # Tab navigation system
├── explainer.js            # Tab 1 (Problem & Solution explainer)
├── performance.js          # Tab 2 (Performance comparison)
├── why-it-works.js         # Tab 1 Sections 5-8 (Why it works)
├── style.css               # Global styles and design system
├── components/
│   ├── index.js            # Barrel export for all components
│   ├── animation-controls.js  # Reusable animation speed controls
│   ├── types.js            # Shared types and utilities
│   ├── protocol-party.js   # Single party protocol logic
│   ├── protocol-simulation.js  # Full simulation orchestration
│   ├── packet-visualizer.js    # Packet flow visualization
│   ├── battlefield.js      # Section 1: Battlefield scene
│   ├── infinite-regress.js # Section 2: Infinite regress
│   └── proof-merging.js    # Section 3: Proof merging animation
└── dist/                   # Production build output
```

### Design Patterns

1. **Event-Driven Architecture**: Components communicate via custom events
2. **Factory Pattern**: Component factories for easy instantiation
3. **Observer Pattern**: Simulation state changes trigger UI updates
4. **Strategy Pattern**: Different protocol simulators share common interface

---

## Core Components

### 1. TabController

Manages navigation between the three main tabs.

```javascript
import { TabController } from './tabs.js';

// Initialize automatically on DOM load
const controller = new TabController('.tab-container');

// Programmatic navigation
controller.switchTo(1); // Switch to tab index 1 (Performance)
controller.getActiveIndex(); // Returns current tab index
```

**Events**:
- `tabchange`: Fires when tab changes, includes `{ index, tabId }` in detail

**Keyboard Navigation**:
- Arrow keys: Navigate between tabs
- Home/End: Jump to first/last tab
- Tab: Move focus to tab panel

---

### 2. UIController (Main Visualizer)

The primary controller for Tab 3: Interactive Visualizer.

```javascript
import { UIController } from './visualizer.js';

// Auto-initializes on DOM ready
const controller = new UIController();

// Control the simulation
controller.start();  // Start protocol
controller.reset();  // Reset to initial state
controller.runTheseusTest();  // Run batch test
```

**Sub-components**:
- `ProtocolSimulation`: Core protocol logic
- `PacketVisualizer`: D3.js packet flow animation
- `ProofNestingVisualizer`: Proof embedding visualization

---

### 3. ExplainerController (Tab 1)

Orchestrates the educational sections.

```javascript
import { ExplainerController } from './explainer.js';

const explainer = new ExplainerController();
explainer.init();

// Available visualizations
explainer.battlefield.startScenario('dilemma');
explainer.infiniteRegress.runDemo();
explainer.proofMerging.showStep(2);
explainer.phaseWalkthrough.nextPhase();
```

**Sections**:
1. **BattlefieldScene**: Animated Two Generals dilemma
2. **InfiniteRegressViz**: ACK chain visualization
3. **ProofMergingAnimation**: Step-by-step proof construction
4. **PhaseWalkthrough**: Interactive phase explanation

---

### 4. PerformanceController (Tab 2)

Runs performance benchmarks and visualizes results.

```javascript
import { PerformanceController, PerformanceTestHarness } from './performance.js';

const perfController = new PerformanceController();
perfController.init();

// Run custom test
const harness = new PerformanceTestHarness();
const results = await harness.runComparison({
    lossRates: [0, 10, 50, 90, 99],
    trialsPerRate: 10,
    maxTicks: 100000,
    protocols: ['TGP', 'TCP', 'QUIC', 'UDP']
});
```

**Protocol Simulators**:
- `TGPSimulator`: Proof escalation with continuous flooding
- `TCPSimulator`: Traditional ACK-based retry
- `QUICSimulator`: Modern UDP with selective ACK
- `UDPSimulator`: Fire-and-forget baseline

---

## Animation Controls

Reusable speed controls for all animations.

```javascript
import { createAnimationControls } from './components/animation-controls.js';

const controls = createAnimationControls({
    container: document.getElementById('my-container'),
    defaultSpeed: 1.0,
    minSpeed: 0.25,
    maxSpeed: 2.0,
    step: 0.25,
    showStepControls: true,

    onSpeedChange: (speed) => {
        console.log('Speed changed to:', speed);
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
        myAnimation.step(direction); // +1 or -1
    }
});

// API
controls.setSpeed(1.5);
controls.setPlaying(true);
controls.getSpeed(); // 1.5
controls.isPlaying(); // true
controls.destroy(); // Remove from DOM
```

---

## Protocol Simulation

### ProtocolParty

Represents one party in the TGP protocol.

```javascript
import { ProtocolParty, Phase } from './components/index.js';

const alice = new ProtocolParty('Alice', true); // true = isAlice
alice.start(); // Create initial commitment

// Phase progression
alice.phase; // Phase.COMMITMENT (1)
const message = alice.getOutgoingMessage(); // { type: 'C', proof: {...} }

// Receive counterparty message
const bobMessage = { type: 'D', proof: {...} };
const advanced = alice.receiveMessage(bobMessage); // Returns true if phase advanced

// Decision logic
const decision = alice.getDecision(deadlineExpired); // 'ATTACK' | 'ABORT' | 'PENDING'
alice.canAttack(); // true if phase >= QUAD

// Proof artifacts
alice.proofArtifacts.forEach(artifact => {
    console.log(`${artifact.label}: ${artifact.description}`);
});
```

**Phases**:
```javascript
Phase.INIT = 0
Phase.COMMITMENT = 1  // C
Phase.DOUBLE = 2      // D
Phase.TRIPLE = 3      // T
Phase.QUAD = 4        // Q
Phase.COMPLETE = 5
```

**Proof Embedding**:
- Receiving higher-level proofs automatically extracts embedded lower-level proofs
- This implements the bilateral construction property

### ProtocolSimulation

Full two-party simulation with lossy channel.

```javascript
import { ProtocolSimulation } from './components/index.js';

const sim = new ProtocolSimulation(0.5); // 50% loss rate

// Event listeners
sim.on('start', () => console.log('Simulation started'));
sim.on('tick', (tick) => console.log('Tick:', tick));
sim.on('phaseAdvance', ({ party, phase }) => {
    console.log(`${party} advanced to phase ${phase}`);
});
sim.on('packetSent', (packet) => console.log('Packet sent:', packet));
sim.on('packetArrived', (packet) => console.log('Packet arrived:', packet));
sim.on('complete', ({ outcome, alice, bob }) => {
    console.log('Outcome:', outcome);
});

// Control
sim.start();
sim.step(); // Single simulation tick
sim.reset();

// State
const stats = sim.getStats();
// {
//     tick: 45,
//     packetsSent: 90,
//     packetsLost: 45,
//     packetsDelivered: 45,
//     actualLossRate: "50.0"
// }
```

### Running Protocol of Theseus Test

```javascript
import { runTheseusTest } from './components/index.js';

const results = await runTheseusTest({
    lossRates: [0, 10, 25, 50, 75, 90, 95, 99, 99.9, 99.99],
    trialsPerRate: 10,
    maxTicks: 10000000,
    onProgress: ({ completed, total, lossRate }) => {
        console.log(`${completed}/${total} at ${lossRate}% loss`);
    }
});

// Results structure
results.forEach(({ lossRate, trials }) => {
    const symmetric = trials.filter(t => t.symmetric).length;
    console.log(`${lossRate}%: ${symmetric}/${trials.length} symmetric`);
});
```

---

## Visualizations

### PacketVisualizer

D3.js visualization of packet flow across lossy channel.

```javascript
import { PacketVisualizer } from './components/index.js';

const viz = new PacketVisualizer('#packet-svg');

// Add packet
viz.addPacket({
    id: 1,
    msg: { type: 'C', proof: {...} },
    direction: 'alice-to-bob',
    progress: 0,
    isLost: false,
    startTick: 0
});

// Update packet position
viz.updatePacket({ id: 1, progress: 0.5 });

// Remove packet (with animation)
viz.removePacket({ id: 1, isLost: false });

// Clear all
viz.clear();
```

### BattlefieldScene

Animated battlefield visualization showing the Two Generals dilemma.

```javascript
import { BattlefieldScene } from './explainer.js';

const battlefield = new BattlefieldScene('#battlefield-scene');
battlefield.init();

// Run scenarios
battlefield.startScenario('dilemma');
battlefield.startScenario('alice_alone');
battlefield.startScenario('both_attack');

// Send messengers
battlefield.sendMessenger(true, 0.6); // fromAlice=true, lossRate=0.6

// Update narrative
battlefield.updateNarrative(
    'Alice attacks alone - DISASTER!',
    'Without Bob\'s army, Alice\'s forces are overwhelmed.'
);

// Control
battlefield.stop();
battlefield.reset();
```

### ProofMergingAnimation

Step-by-step proof embedding animation.

```javascript
import { ProofMergingAnimation } from './explainer.js';

const merging = new ProofMergingAnimation('#proof-merging');
merging.init();

// Navigation
merging.nextStep();
merging.prevStep();
merging.showStep(2); // Jump to specific step

// Auto-play
merging.startAutoPlay();
merging.stopAutoPlay();
merging.reset();
```

### BilateralConstructionGraph

Dependency graph showing mutual constructibility.

```javascript
import { BilateralConstructionGraph } from './why-it-works.js';

const graph = new BilateralConstructionGraph('bilateral-construction-graph');
// Automatically initializes with animation controls

// The animation steps through proof dependencies
// Controls are built-in via createAnimationControls()
```

---

## Usage Examples

### Example 1: Embedded Protocol Visualizer

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="my-visualizer">
        <svg id="packet-vis" width="800" height="300"></svg>
        <div id="controls"></div>
        <div id="stats"></div>
    </div>

    <script type="module">
        import { ProtocolSimulation } from './components/index.js';
        import { PacketVisualizer } from './components/index.js';

        // Create simulation
        const sim = new ProtocolSimulation(0.5);
        const viz = new PacketVisualizer('#packet-vis');

        // Wire up events
        sim.on('start', () => {
            sim.isRunning = true;
        });

        sim.on('packetSent', (packet) => {
            viz.addPacket(packet);
        });

        sim.on('tick', () => {
            sim.packets.forEach(p => viz.updatePacket(p));
            document.getElementById('stats').innerHTML = `
                Tick: ${sim.getStats().tick}<br>
                Packets: ${sim.getStats().packetsSent}<br>
                Loss: ${sim.getStats().actualLossRate}%
            `;
        });

        sim.on('packetArrived', (packet) => {
            viz.removePacket(packet);
        });

        // Start button
        document.getElementById('controls').innerHTML = `
            <button onclick="window.sim.start()">Start</button>
            <button onclick="window.sim.reset(); window.viz.clear()">Reset</button>
        `;

        window.sim = sim;
        window.viz = viz;
    </script>
</body>
</html>
```

### Example 2: Custom Performance Test

```javascript
import {
    TGPSimulator,
    TCPSimulator,
    PerformanceTestHarness
} from './performance.js';

// Create custom test harness
const harness = new PerformanceTestHarness();

// Run test with specific parameters
const results = await harness.runComparison({
    lossRates: [10, 50, 90],
    trialsPerRate: 5,
    maxTicks: 50000,
    protocols: ['TGP', 'TCP']
});

// Extract data
const tgpData = results.protocols.find(p => p.name === 'TGP');
tgpData.data.forEach(point => {
    console.log(`Loss ${point.lossRate}%:`);
    console.log(`  Success Rate: ${point.successRate}%`);
    console.log(`  Symmetry: ${point.symmetryRate}%`);
    console.log(`  Avg Round Trips: ${point.avgRoundTrips}`);
});
```

### Example 3: Standalone Explainer Section

```html
<div id="infinite-regress-demo"></div>

<script type="module">
    import { InfiniteRegressViz } from './explainer.js';

    const demo = new InfiniteRegressViz('#infinite-regress-demo');
    demo.init();

    // Auto-start demo
    setTimeout(() => demo.runDemo(), 1000);

    // Add reset button
    document.querySelector('#infinite-regress-demo').insertAdjacentHTML(
        'beforeend',
        '<button onclick="window.regressDemo.reset()">Reset</button>'
    );
    window.regressDemo = demo;
</script>
```

### Example 4: Interactive Phase Tutorial

```javascript
import { PhaseWalkthrough } from './explainer.js';

const tutorial = new PhaseWalkthrough('#phase-tutorial');
tutorial.init();

// Step through phases programmatically
async function runAutoTutorial() {
    for (let i = 0; i < tutorial.phases.length; i++) {
        tutorial.showPhase(i);
        await new Promise(resolve => setTimeout(resolve, 3000));
    }
}

// Or let user control
tutorial.startPlay(); // Auto-advance
tutorial.stopPlay();
tutorial.nextPhase();
tutorial.prevPhase();
```

---

## Integration Guide

### Quick Start

1. **Include dependencies**:
```html
<script src="https://d3js.org/d3.v7.min.js"></script>
<link rel="stylesheet" href="style.css">
```

2. **Import components**:
```javascript
import { ProtocolSimulation, PacketVisualizer } from './components/index.js';
```

3. **Initialize**:
```javascript
const sim = new ProtocolSimulation(0.5);
const viz = new PacketVisualizer('#my-svg');
sim.on('packetSent', packet => viz.addPacket(packet));
sim.start();
```

### Build for Production

```bash
cd web/
npm install
npm run build
# Output in dist/ folder
```

### Embedding Components

Components can be embedded in external sites:

```html
<!-- Minimal embedding -->
<div id="tgp-embed"></div>
<script type="module" src="https://example.com/tgp/visualizer.js"></script>
<script>
    // Components auto-initialize on window.tgpComponents
    window.tgpComponents.battlefield.startScenario('dilemma');
</script>
```

### Customization

**CSS Custom Properties**:
```css
:root {
    --bg-primary: #0d1117;
    --text-primary: #f0f6fc;
    --accent-blue: #58a6ff;
    --accent-green: #3fb950;
    --accent-red: #f85149;
    --accent-purple: #a371f7;
    --accent-orange: #f0883e;
    --accent-yellow: #d29922;
}
```

**Theme Override**:
```css
.dark-theme {
    --bg-primary: #000000;
    --text-primary: #ffffff;
}

.light-theme {
    --bg-primary: #ffffff;
    --text-primary: #000000;
}
```

---

## API Reference

### Core Types

```typescript
enum Phase {
    INIT = 0,
    COMMITMENT = 1,
    DOUBLE = 2,
    TRIPLE = 3,
    QUAD = 4,
    COMPLETE = 5
}

enum Decision {
    PENDING = 'PENDING',
    ATTACK = 'ATTACK',
    ABORT = 'ABORT'
}

interface Proof {
    party: string;
    signature: string;
    hash: string;
    // Embedded proofs vary by level
}

interface Commitment extends Proof {
    message: string;
}

interface DoubleProof extends Proof {
    ownCommitment: Commitment;
    otherCommitment: Commitment;
}

interface TripleProof extends Proof {
    ownDouble: DoubleProof;
    otherDouble: DoubleProof;
}

interface QuadProof extends Proof {
    ownTriple: TripleProof;
    otherTriple: TripleProof;
}

interface Message {
    type: 'C' | 'D' | 'T' | 'Q';
    proof: Proof;
}

interface Packet {
    id: number;
    msg: Message;
    direction: 'alice-to-bob' | 'bob-to-alice';
    progress: number; // 0 to 1
    isLost: boolean;
    startTick: number;
}

interface SimulationStats {
    tick: number;
    packetsSent: number;
    packetsLost: number;
    packetsDelivered: number;
    actualLossRate: string; // Percentage
}

interface TestResult {
    lossRate: number;
    ticks: number;
    alicePhase: Phase;
    bobPhase: Phase;
    aliceDecision: Decision;
    bobDecision: Decision;
    symmetric: boolean;
    outcome: 'ATTACK' | 'ABORT' | 'ASYMMETRIC';
    fastForwarded: boolean;
}
```

### Utility Functions

```javascript
import {
    phaseName,           // (phase: Phase) => string
    generateSignature,   // () => string (8 hex chars)
    generateHash,        // () => string (16 hex chars)
    formatNumber,        // (num: number) => string (with commas)
    formatPercent,       // (num: number) => string (with %)
    createEventEmitter,  // () => EventEmitter
    debounce,           // (fn: Function, ms: number) => Function
    throttle            // (fn: Function, ms: number) => Function
} from './components/types.js';
```

### Performance Metrics

```typescript
interface PerformanceAggregated {
    trials: number;
    avgMessagesSent: number;
    avgMessagesDelivered: number;
    avgRoundTrips: number;
    avgDuration: number; // milliseconds
    successRate: number; // percentage
    symmetryRate: number; // percentage (TGP always 100%)
    completionRate: number; // percentage
}

interface ComparisonData {
    protocols: Array<{
        name: 'TGP' | 'TCP' | 'QUIC' | 'UDP';
        data: Array<PerformanceAggregated & { lossRate: number }>;
    }>;
    lossRates: number[];
}
```

---

## Accessibility

All components support:

- **Keyboard Navigation**: Full keyboard control (Arrow keys, Tab, Enter, Space)
- **ARIA Labels**: Proper roles and labels for screen readers
- **Focus Management**: Visible focus indicators
- **Reduced Motion**: Respects `prefers-reduced-motion` media query
- **Color Contrast**: WCAG AAA compliant (7:1 ratio minimum)
- **Screen Reader Announcements**: Live regions for dynamic content

### Keyboard Shortcuts

- **Tab Navigation**: Arrow Left/Right, Home, End
- **Animation Controls**: Space (play/pause), R (reset)
- **Sliders**: Arrow Left/Right (adjust value)
- **Buttons**: Enter or Space (activate)

---

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari 14+, Chrome Mobile 90+)

### Polyfills

Not required - uses only native ES6+ features supported by target browsers.

---

## Performance Considerations

### Bundle Size
- **Main bundle**: ~160KB (minified)
- **CSS**: ~40KB (minified)
- **D3.js**: 250KB (CDN)
- **Total**: ~450KB

### Optimization Tips

1. **Lazy load tabs**: Only initialize visualizations when tab is active
2. **Throttle animations**: Use `requestAnimationFrame` for smooth 60fps
3. **Debounce resize events**: Prevent excessive SVG recalculations
4. **Batch DOM updates**: Use D3's data joins efficiently
5. **Reduce motion**: Skip animations when `prefers-reduced-motion: reduce`

---

## Troubleshooting

### Common Issues

**Q: Visualizations not rendering**
- Check that D3.js is loaded before modules
- Ensure SVG container exists in DOM
- Check browser console for errors

**Q: Performance slow with many particles**
- Reduce packet flooding rate
- Lower simulation speed
- Use `will-change: transform` CSS

**Q: Tab switching broken**
- Verify tab IDs match hash values
- Check that tab panes have `active` class logic
- Ensure `TabController` is initialized

**Q: WASM not loading**
- WASM is optional - JS simulation is fallback
- Build WASM: `cd wasm && wasm-pack build --target web`
- Check browser WASM support

---

## License

AGPLv3 - See LICENSE file for details.

---

## Credits

- **Author**: Wings@riff.cc (Riff Labs)
- **Keeper**: Lief (The Forge)
- **D3.js**: Mike Bostock and contributors
- **Theory**: Based on academic work solving the Two Generals Problem

---

**e cinere surgemus** 🔥
