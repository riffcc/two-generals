/**
 * Two Generals Protocol - Interactive Visualizer
 *
 * D3.js-powered visualization showing:
 * - Proof escalation (C -> D -> T -> Q)
 * - Packet flow animation with loss simulation
 * - Protocol of Theseus test results
 */

import * as d3 from 'd3';

// =============================================================================
// Protocol State Types
// =============================================================================

const Phase = {
    INIT: 0,
    COMMITMENT: 1,
    DOUBLE: 2,
    TRIPLE: 3,
    QUAD: 4,
    COMPLETE: 5
};

const phaseName = (phase) => {
    switch (phase) {
        case Phase.INIT: return 'INIT';
        case Phase.COMMITMENT: return 'C';
        case Phase.DOUBLE: return 'D';
        case Phase.TRIPLE: return 'T';
        case Phase.QUAD: return 'Q';
        case Phase.COMPLETE: return 'COMPLETE';
        default: return 'UNKNOWN';
    }
};

// =============================================================================
// Simulated Protocol Party
// =============================================================================

class ProtocolParty {
    constructor(name, isAlice) {
        this.name = name;
        this.isAlice = isAlice;
        this.phase = Phase.INIT;
        this.commitment = null;
        this.otherCommitment = null;
        this.doubleProof = null;
        this.otherDoubleProof = null;
        this.tripleProof = null;
        this.otherTripleProof = null;
        this.quadProof = null;
        this.messageQueue = [];
        this.proofArtifacts = [];
    }

    start() {
        if (this.phase === Phase.INIT) {
            this.commitment = this.createCommitment();
            this.phase = Phase.COMMITMENT;
            this.proofArtifacts.push({
                type: 'commitment',
                label: `C_${this.isAlice ? 'A' : 'B'}`,
                description: 'Signed commitment to attack'
            });
        }
    }

    createCommitment() {
        return {
            party: this.name,
            message: 'I will attack at dawn if you agree',
            signature: this.generateSignature(),
            hash: this.generateHash()
        };
    }

    generateSignature() {
        return Array.from({ length: 8 }, () =>
            Math.floor(Math.random() * 16).toString(16)
        ).join('');
    }

    generateHash() {
        return Array.from({ length: 16 }, () =>
            Math.floor(Math.random() * 16).toString(16)
        ).join('');
    }

    getOutgoingMessage() {
        switch (this.phase) {
            case Phase.COMMITMENT:
                return { type: 'C', proof: this.commitment };
            case Phase.DOUBLE:
                return { type: 'D', proof: this.doubleProof };
            case Phase.TRIPLE:
                return { type: 'T', proof: this.tripleProof };
            case Phase.QUAD:
                return { type: 'Q', proof: this.quadProof };
            default:
                return null;
        }
    }

    receiveMessage(msg) {
        if (!msg) return false;

        switch (msg.type) {
            case 'C':
                if (this.phase === Phase.COMMITMENT && !this.otherCommitment) {
                    this.otherCommitment = msg.proof;
                    this.doubleProof = this.createDoubleProof();
                    this.phase = Phase.DOUBLE;
                    this.proofArtifacts.push({
                        type: 'double',
                        label: `D_${this.isAlice ? 'A' : 'B'}`,
                        description: 'Contains both commitments'
                    });
                    return true;
                }
                break;

            case 'D':
                if (this.phase === Phase.DOUBLE && !this.otherDoubleProof) {
                    this.otherDoubleProof = msg.proof;
                    this.tripleProof = this.createTripleProof();
                    this.phase = Phase.TRIPLE;
                    this.proofArtifacts.push({
                        type: 'triple',
                        label: `T_${this.isAlice ? 'A' : 'B'}`,
                        description: 'Contains both double proofs'
                    });
                    return true;
                }
                break;

            case 'T':
                if (this.phase === Phase.TRIPLE && !this.otherTripleProof) {
                    this.otherTripleProof = msg.proof;
                    this.quadProof = this.createQuadProof();
                    this.phase = Phase.QUAD;
                    this.proofArtifacts.push({
                        type: 'quad',
                        label: `Q_${this.isAlice ? 'A' : 'B'}`,
                        description: 'Epistemic fixpoint achieved!'
                    });
                    return true;
                }
                break;

            case 'Q':
                if (this.phase === Phase.QUAD) {
                    this.phase = Phase.COMPLETE;
                    return true;
                }
                break;
        }
        return false;
    }

    createDoubleProof() {
        return {
            party: this.name,
            ownCommitment: this.commitment,
            otherCommitment: this.otherCommitment,
            signature: this.generateSignature(),
            hash: this.generateHash()
        };
    }

    createTripleProof() {
        return {
            party: this.name,
            ownDouble: this.doubleProof,
            otherDouble: this.otherDoubleProof,
            signature: this.generateSignature(),
            hash: this.generateHash()
        };
    }

    createQuadProof() {
        return {
            party: this.name,
            ownTriple: this.tripleProof,
            otherTriple: this.otherTripleProof,
            signature: this.generateSignature(),
            hash: this.generateHash()
        };
    }

    isComplete() {
        return this.phase === Phase.COMPLETE;
    }

    canAttack() {
        return this.phase >= Phase.QUAD;
    }
}

// =============================================================================
// Protocol Simulation
// =============================================================================

class ProtocolSimulation {
    constructor(lossRate = 0.5) {
        this.lossRate = lossRate;
        this.alice = new ProtocolParty('Alice', true);
        this.bob = new ProtocolParty('Bob', false);
        this.tick = 0;
        this.packetsSent = 0;
        this.packetsLost = 0;
        this.packetsDelivered = 0;
        this.isRunning = false;
        this.speed = 1;
        this.packets = [];
        this.callbacks = {};
    }

    on(event, callback) {
        this.callbacks[event] = callback;
    }

    emit(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event](data);
        }
    }

    start() {
        this.alice.start();
        this.bob.start();
        this.isRunning = true;
        this.emit('start');
    }

    reset() {
        this.alice = new ProtocolParty('Alice', true);
        this.bob = new ProtocolParty('Bob', false);
        this.tick = 0;
        this.packetsSent = 0;
        this.packetsLost = 0;
        this.packetsDelivered = 0;
        this.isRunning = false;
        this.packets = [];
        this.emit('reset');
    }

    step() {
        if (!this.isRunning) return;

        this.tick++;

        // Alice sends to Bob
        const aliceMsg = this.alice.getOutgoingMessage();
        if (aliceMsg) {
            this.sendPacket(aliceMsg, 'alice-to-bob');
        }

        // Bob sends to Alice
        const bobMsg = this.bob.getOutgoingMessage();
        if (bobMsg) {
            this.sendPacket(bobMsg, 'bob-to-alice');
        }

        // Process packets in flight
        this.processPackets();

        // Check for completion
        if (this.alice.isComplete() && this.bob.isComplete()) {
            this.isRunning = false;
            this.emit('complete', {
                outcome: 'ATTACK',
                alice: this.alice,
                bob: this.bob
            });
        }

        this.emit('tick', this.tick);
    }

    sendPacket(msg, direction) {
        this.packetsSent++;
        const isLost = Math.random() < this.lossRate;

        const packet = {
            id: this.packetsSent,
            msg,
            direction,
            progress: 0,
            isLost,
            startTick: this.tick
        };

        this.packets.push(packet);
        this.emit('packetSent', packet);

        if (isLost) {
            this.packetsLost++;
        }
    }

    processPackets() {
        const arrivedPackets = [];
        const inFlightPackets = [];

        for (const packet of this.packets) {
            packet.progress += 0.2 * this.speed;

            if (packet.progress >= 1) {
                arrivedPackets.push(packet);
            } else {
                inFlightPackets.push(packet);
            }
        }

        this.packets = inFlightPackets;

        for (const packet of arrivedPackets) {
            if (!packet.isLost) {
                this.packetsDelivered++;
                if (packet.direction === 'alice-to-bob') {
                    const advanced = this.bob.receiveMessage(packet.msg);
                    if (advanced) {
                        this.emit('phaseAdvance', { party: 'bob', phase: this.bob.phase });
                    }
                } else {
                    const advanced = this.alice.receiveMessage(packet.msg);
                    if (advanced) {
                        this.emit('phaseAdvance', { party: 'alice', phase: this.alice.phase });
                    }
                }
            }
            this.emit('packetArrived', packet);
        }
    }

    getStats() {
        return {
            tick: this.tick,
            packetsSent: this.packetsSent,
            packetsLost: this.packetsLost,
            packetsDelivered: this.packetsDelivered,
            actualLossRate: this.packetsSent > 0
                ? (this.packetsLost / this.packetsSent * 100).toFixed(1)
                : 0
        };
    }
}

// =============================================================================
// D3.js Visualization
// =============================================================================

class PacketVisualizer {
    constructor(svgSelector) {
        this.svg = d3.select(svgSelector);
        this.width = 400;
        this.height = 200;
        this.packets = new Map();

        this.setupSVG();
    }

    setupSVG() {
        // Clear existing
        this.svg.selectAll('*').remove();

        // Add gradient for channel
        const defs = this.svg.append('defs');

        const gradient = defs.append('linearGradient')
            .attr('id', 'channel-gradient')
            .attr('x1', '0%')
            .attr('x2', '100%');

        gradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', '#58a6ff')
            .attr('stop-opacity', 0.2);

        gradient.append('stop')
            .attr('offset', '50%')
            .attr('stop-color', '#21262d');

        gradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', '#3fb950')
            .attr('stop-opacity', 0.2);

        // Background
        this.svg.append('rect')
            .attr('width', this.width)
            .attr('height', this.height)
            .attr('fill', 'url(#channel-gradient)');

        // Channel lines
        this.svg.append('line')
            .attr('x1', 20)
            .attr('y1', 70)
            .attr('x2', 380)
            .attr('y2', 70)
            .attr('stroke', '#58a6ff')
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '5,5')
            .attr('opacity', 0.5);

        this.svg.append('line')
            .attr('x1', 20)
            .attr('y1', 130)
            .attr('x2', 380)
            .attr('y2', 130)
            .attr('stroke', '#3fb950')
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '5,5')
            .attr('opacity', 0.5);

        // Labels
        this.svg.append('text')
            .attr('x', 200)
            .attr('y', 55)
            .attr('text-anchor', 'middle')
            .attr('fill', '#58a6ff')
            .attr('font-size', '12px')
            .text('Alice → Bob');

        this.svg.append('text')
            .attr('x', 200)
            .attr('y', 155)
            .attr('text-anchor', 'middle')
            .attr('fill', '#3fb950')
            .attr('font-size', '12px')
            .text('Bob → Alice');

        // Packet container
        this.packetGroup = this.svg.append('g')
            .attr('class', 'packets');
    }

    addPacket(packet) {
        const y = packet.direction === 'alice-to-bob' ? 70 : 130;
        const startX = packet.direction === 'alice-to-bob' ? 20 : 380;
        const endX = packet.direction === 'alice-to-bob' ? 380 : 20;

        const color = packet.direction === 'alice-to-bob' ? '#58a6ff' : '#3fb950';

        const group = this.packetGroup.append('g')
            .attr('class', 'packet')
            .attr('data-id', packet.id);

        // Packet shape
        group.append('rect')
            .attr('x', -8)
            .attr('y', -8)
            .attr('width', 16)
            .attr('height', 16)
            .attr('rx', 3)
            .attr('fill', color)
            .attr('opacity', packet.isLost ? 0.3 : 1);

        // Packet label
        group.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', 4)
            .attr('fill', '#fff')
            .attr('font-size', '10px')
            .attr('font-weight', 'bold')
            .text(packet.msg.type);

        // Initial position
        const x = startX + (endX - startX) * packet.progress;
        group.attr('transform', `translate(${x}, ${y})`);

        this.packets.set(packet.id, { group, startX, endX, y, packet });
    }

    updatePacket(packet) {
        const data = this.packets.get(packet.id);
        if (!data) return;

        const x = data.startX + (data.endX - data.startX) * packet.progress;
        data.group.attr('transform', `translate(${x}, ${data.y})`);

        if (packet.isLost && packet.progress > 0.5) {
            data.group.select('rect')
                .transition()
                .duration(200)
                .attr('opacity', 0);
        }
    }

    removePacket(packet) {
        const data = this.packets.get(packet.id);
        if (!data) return;

        if (packet.isLost) {
            // Fade out lost packets
            data.group.transition()
                .duration(300)
                .attr('opacity', 0)
                .remove();
        } else {
            // Pop delivered packets
            data.group.transition()
                .duration(200)
                .attr('transform', `translate(${data.endX}, ${data.y}) scale(1.5)`)
                .attr('opacity', 0)
                .remove();
        }

        this.packets.delete(packet.id);
    }

    clear() {
        this.packetGroup.selectAll('.packet').remove();
        this.packets.clear();
    }
}

// =============================================================================
// UI Controller
// =============================================================================

class UIController {
    constructor() {
        this.simulation = new ProtocolSimulation();
        this.packetViz = new PacketVisualizer('#packet-svg');
        this.animationFrame = null;
        this.lastTime = 0;
        this.tickInterval = 100; // ms per tick

        this.bindEvents();
        this.bindSimulationEvents();
        this.updateUI();
    }

    bindEvents() {
        // Loss rate slider
        const lossSlider = document.getElementById('loss-rate');
        const lossValue = document.getElementById('loss-value');
        lossSlider.addEventListener('input', (e) => {
            const value = parseInt(e.target.value);
            lossValue.textContent = `${value}%`;
            this.simulation.lossRate = value / 100;
        });

        // Speed slider
        const speedSlider = document.getElementById('speed');
        const speedValue = document.getElementById('speed-value');
        speedSlider.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            speedValue.textContent = `${value}x`;
            this.simulation.speed = value;
            this.tickInterval = 100 / value;
        });

        // Start button
        document.getElementById('start-btn').addEventListener('click', () => {
            if (!this.simulation.isRunning) {
                this.start();
            }
        });

        // Reset button
        document.getElementById('reset-btn').addEventListener('click', () => {
            this.reset();
        });

        // Theseus test button
        document.getElementById('run-theseus').addEventListener('click', () => {
            this.runTheseusTest();
        });
    }

    bindSimulationEvents() {
        this.simulation.on('start', () => {
            document.getElementById('start-btn').disabled = true;
            this.updatePhases();
        });

        this.simulation.on('reset', () => {
            document.getElementById('start-btn').disabled = false;
            this.packetViz.clear();
            this.updateUI();
            this.resetOutcome();
            this.resetProofs();
            this.resetEscalation();
        });

        this.simulation.on('tick', () => {
            this.updateStats();
        });

        this.simulation.on('packetSent', (packet) => {
            this.packetViz.addPacket(packet);
        });

        this.simulation.on('packetArrived', (packet) => {
            this.packetViz.removePacket(packet);
        });

        this.simulation.on('phaseAdvance', (data) => {
            this.updatePhases();
            this.updateProofs(data.party);
            this.updateEscalation(data.party, data.phase);
        });

        this.simulation.on('complete', (data) => {
            cancelAnimationFrame(this.animationFrame);
            document.getElementById('start-btn').disabled = false;
            this.showOutcome(data.outcome);
        });
    }

    start() {
        this.simulation.start();
        this.lastTime = performance.now();
        this.animate();
    }

    animate() {
        const now = performance.now();
        const delta = now - this.lastTime;

        if (delta >= this.tickInterval) {
            this.simulation.step();

            // Update packet positions
            for (const packet of this.simulation.packets) {
                this.packetViz.updatePacket(packet);
            }

            this.lastTime = now;
        }

        if (this.simulation.isRunning) {
            this.animationFrame = requestAnimationFrame(() => this.animate());
        }
    }

    reset() {
        cancelAnimationFrame(this.animationFrame);
        this.simulation.reset();
    }

    updateUI() {
        this.updateStats();
        this.updatePhases();
    }

    updateStats() {
        const stats = this.simulation.getStats();
        document.getElementById('packets-sent').textContent = stats.packetsSent;
        document.getElementById('packets-lost').textContent = stats.packetsLost;
        document.getElementById('packets-delivered').textContent = stats.packetsDelivered;
        document.getElementById('elapsed-time').textContent = `${(stats.tick * 0.1).toFixed(2)}s`;
        document.getElementById('total-packets').textContent = stats.packetsSent;
        document.getElementById('actual-loss').textContent = `${stats.actualLossRate}%`;
    }

    updatePhases() {
        document.getElementById('alice-phase').textContent = phaseName(this.simulation.alice.phase);
        document.getElementById('bob-phase').textContent = phaseName(this.simulation.bob.phase);

        // Update status
        const aliceStatus = document.getElementById('alice-status');
        const bobStatus = document.getElementById('bob-status');

        if (this.simulation.alice.isComplete()) {
            aliceStatus.textContent = 'ATTACK';
            aliceStatus.classList.add('active');
        } else if (this.simulation.isRunning) {
            aliceStatus.textContent = 'Flooding...';
            aliceStatus.classList.add('active');
        } else {
            aliceStatus.textContent = 'Waiting';
            aliceStatus.classList.remove('active');
        }

        if (this.simulation.bob.isComplete()) {
            bobStatus.textContent = 'ATTACK';
            bobStatus.classList.add('active');
        } else if (this.simulation.isRunning) {
            bobStatus.textContent = 'Flooding...';
            bobStatus.classList.add('active');
        } else {
            bobStatus.textContent = 'Waiting';
            bobStatus.classList.remove('active');
        }
    }

    updateProofs(party) {
        const containerId = party === 'alice' ? 'alice-proofs' : 'bob-proofs';
        const container = document.getElementById(containerId);
        const partyObj = party === 'alice' ? this.simulation.alice : this.simulation.bob;

        container.innerHTML = '';
        for (const artifact of partyObj.proofArtifacts) {
            const div = document.createElement('div');
            div.className = `proof-artifact ${artifact.type}`;
            div.innerHTML = `<strong>${artifact.label}</strong>: ${artifact.description}`;
            container.appendChild(div);
        }
    }

    resetProofs() {
        document.getElementById('alice-proofs').innerHTML = '';
        document.getElementById('bob-proofs').innerHTML = '';
    }

    updateEscalation(party, phase) {
        const prefix = party === 'alice' ? 'alice' : 'bob';

        if (phase >= Phase.COMMITMENT) {
            document.getElementById(`${prefix}-c`).classList.add('complete');
        }
        if (phase >= Phase.DOUBLE) {
            document.getElementById(`${prefix}-d`).classList.add('complete');
        }
        if (phase >= Phase.TRIPLE) {
            document.getElementById(`${prefix}-t`).classList.add('complete');
        }
        if (phase >= Phase.QUAD) {
            document.getElementById(`${prefix}-q`).classList.add('complete');
        }
    }

    resetEscalation() {
        const bars = document.querySelectorAll('.bar');
        bars.forEach(bar => bar.classList.remove('complete'));
    }

    showOutcome(outcome) {
        const display = document.getElementById('outcome');
        display.className = 'outcome-display';

        if (outcome === 'ATTACK') {
            display.classList.add('attack');
            display.innerHTML = 'MUTUAL ATTACK - Both generals attack together!';
        } else if (outcome === 'ABORT') {
            display.classList.add('abort');
            display.innerHTML = 'MUTUAL ABORT - Safe failure, no one attacks.';
        } else {
            display.classList.add('error');
            display.innerHTML = 'ERROR - Asymmetric outcome detected!';
        }
    }

    resetOutcome() {
        const display = document.getElementById('outcome');
        display.className = 'outcome-display';
        display.innerHTML = '<span class="pending">Awaiting protocol completion...</span>';
    }

    async runTheseusTest() {
        const resultsContainer = document.getElementById('theseus-results');
        const progress = document.getElementById('theseus-progress');
        const button = document.getElementById('run-theseus');

        button.disabled = true;
        resultsContainer.innerHTML = '';

        // Create grid
        const grid = document.createElement('div');
        grid.className = 'theseus-grid';
        resultsContainer.appendChild(grid);

        const cells = [];
        for (let i = 0; i < 100; i++) {
            const cell = document.createElement('div');
            cell.className = 'theseus-cell';
            grid.appendChild(cell);
            cells.push(cell);
        }

        let symmetric = 0;
        let asymmetric = 0;

        // Run simulations at various loss rates
        for (let i = 0; i < 100; i++) {
            progress.textContent = `Running simulation ${i + 1}/100...`;

            // Vary loss rate from 0% to 98%
            const lossRate = (i / 100) * 0.98;
            const result = await this.runSingleSimulation(lossRate);

            if (result.symmetric) {
                symmetric++;
                cells[i].classList.add('symmetric');
            } else {
                asymmetric++;
                cells[i].classList.add('asymmetric');
            }

            // Small delay for visual effect
            await new Promise(r => setTimeout(r, 10));
        }

        progress.textContent = '';

        // Show summary
        const summary = document.createElement('div');
        summary.className = 'theseus-summary';
        summary.innerHTML = `
            <strong>Results:</strong> ${symmetric} symmetric (${(symmetric)}%), ${asymmetric} asymmetric (${asymmetric}%)
            <br>
            ${asymmetric === 0
                ? '<span style="color: #3fb950;">Protocol of Theseus: PASSED - No asymmetric outcomes!</span>'
                : '<span style="color: #f85149;">WARNING: Asymmetric outcomes detected!</span>'}
        `;
        resultsContainer.appendChild(summary);

        button.disabled = false;
    }

    runSingleSimulation(lossRate) {
        return new Promise((resolve) => {
            const sim = new ProtocolSimulation(lossRate);
            sim.start();

            let ticks = 0;
            const maxTicks = 500;

            const runTick = () => {
                sim.step();
                ticks++;

                // Check completion
                const aliceComplete = sim.alice.isComplete();
                const bobComplete = sim.bob.isComplete();

                if ((aliceComplete && bobComplete) || ticks >= maxTicks) {
                    // Determine symmetry
                    const symmetric = (aliceComplete === bobComplete);
                    resolve({
                        symmetric,
                        aliceComplete,
                        bobComplete,
                        ticks,
                        lossRate
                    });
                } else {
                    setTimeout(runTick, 0);
                }
            };

            runTick();
        });
    }
}

// =============================================================================
// Initialize
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    window.controller = new UIController();
});
