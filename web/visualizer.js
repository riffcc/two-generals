/**
 * Two Generals Protocol - Interactive Visualizer
 *
 * D3.js-powered visualization showing:
 * - Proof escalation (C -> D -> T -> Q)
 * - Packet flow animation with loss simulation
 * - Protocol of Theseus test results
 * - Proof nesting/embedding visualization
 * - Bilateral construction property demonstration
 *
 * Supports both pure JS simulation and WASM bindings when available.
 *
 * Key Visual Elements:
 * 1. Packet animation across the lossy channel
 * 2. Proof stack showing C → D → T → Q progression
 * 3. Escalation diagram with progress bars
 * 4. Protocol of Theseus grid test (100 simulations)
 */

import * as d3 from 'd3';

// =============================================================================
// WASM Integration Layer
// =============================================================================

let wasmModule = null;
let useWasm = false;

/**
 * Attempt to load WASM module, falling back to JS simulation.
 *
 * The WASM module provides:
 * - Higher performance for batch simulations
 * - Cryptographically correct signatures (Ed25519)
 * - Exact match with Rust implementation
 *
 * When WASM is not available, we use a pure JS simulation that
 * accurately models the protocol behavior without crypto.
 */
async function initWasm() {
    // Check if WASM module exists before trying to import
    // This avoids console errors in development
    try {
        const response = await fetch('./pkg/two_generals_wasm.js', { method: 'HEAD' });
        if (!response.ok) {
            console.log('WASM module not built yet, using JS simulation');
            console.log('To build WASM: cd ../wasm && wasm-pack build --target web --out-dir ../web/pkg');
            useWasm = false;
            return false;
        }
    } catch (e) {
        console.log('WASM module not available, using JS simulation');
        useWasm = false;
        return false;
    }

    try {
        // Dynamically import the WASM module
        const wasm = await import('./pkg/two_generals_wasm.js');
        await wasm.default();
        wasmModule = wasm;
        useWasm = true;
        console.log('TGP WASM module loaded successfully');
        return true;
    } catch (e) {
        console.log('WASM initialization failed, using JS simulation:', e.message);
        useWasm = false;
        return false;
    }
}

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
    /**
     * Represents one party in the TGP protocol.
     *
     * The protocol progresses through phases:
     * C -> D -> T -> Q -> Complete
     *
     * Key insight: Each phase embeds proofs from previous phases,
     * creating the bilateral construction property where Q_A's existence
     * proves Q_B is constructible.
     */
    constructor(name, isAlice) {
        this.name = name;
        this.isAlice = isAlice;
        this.phase = Phase.INIT;
        // Own proofs constructed at each level
        this.commitment = null;      // C_X
        this.doubleProof = null;     // D_X = Sign(C_X || C_Y || "Both committed")
        this.tripleProof = null;     // T_X = Sign(D_X || D_Y || "Both have double")
        this.quadProof = null;       // Q_X = Sign(T_X || T_Y || "Fixpoint achieved")
        // Counterparty proofs received
        this.otherCommitment = null;
        this.otherDoubleProof = null;
        this.otherTripleProof = null;
        this.messageQueue = [];
        this.proofArtifacts = [];
        // Track embedded proofs for visualization
        this.embeddedProofs = new Set();
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

    /**
     * Receive and process a message with PROPER PROOF EMBEDDING.
     *
     * CRITICAL PROTOCOL FEATURE: Higher proofs embed all lower proofs!
     * - D contains: C_A, C_B
     * - T contains: D_A, D_B (which contain C_A, C_B)
     * - Q contains: T_A, T_B (which contain everything)
     *
     * This means: If I receive T_Y, I can extract C_Y and D_Y from it!
     * The simulation must respect this to avoid false asymmetric outcomes.
     */
    receiveMessage(msg) {
        if (!msg) return false;

        let advanced = false;

        // PROOF EMBEDDING: Extract all embedded proofs from higher-level messages
        // This is CRITICAL for bilateral construction property!
        if (msg.type === 'Q' && msg.proof) {
            // Q contains T, which contains D, which contains C
            if (msg.proof.otherTriple) {
                this.processEmbeddedTriple(msg.proof.otherTriple);
            }
            if (msg.proof.ownTriple) {
                this.processEmbeddedTriple(msg.proof.ownTriple);
            }
        }

        if (msg.type === 'T' && msg.proof) {
            // T contains D, which contains C
            this.processEmbeddedTriple(msg.proof);
        }

        if (msg.type === 'D' && msg.proof) {
            // D contains C
            this.processEmbeddedDouble(msg.proof);
        }

        // After extracting embedded proofs, try to advance through phases!
        // This is critical for the bilateral construction property.
        // Capture if we advanced - this ensures UI updates even when switch cases don't trigger
        advanced = this.tryAdvanceToQuad() || advanced;

        // Now process the message itself
        switch (msg.type) {
            case 'C':
                if (!this.otherCommitment) {
                    this.otherCommitment = msg.proof;
                    this.tryAdvanceToDouble();
                    advanced = true;
                }
                break;

            case 'D':
                if (!this.otherDoubleProof && msg.proof) {
                    this.otherDoubleProof = msg.proof;
                    this.tryAdvanceToTriple();
                    advanced = true;
                }
                break;

            case 'T':
                if (!this.otherTripleProof && msg.proof) {
                    this.otherTripleProof = msg.proof;
                    this.embeddedProofs.add('T_other');
                    this.tryAdvanceToQuad();
                    advanced = true;
                }
                break;

            case 'Q':
                if (this.phase === Phase.QUAD) {
                    this.phase = Phase.COMPLETE;
                    advanced = true;
                }
                break;
        }

        return advanced;
    }

    /**
     * Extract embedded proofs from a Triple proof.
     * T contains D_X and D_Y, each of which contains C_X and C_Y.
     *
     * CRITICAL: Must check party field before setting "other" proofs!
     * When Alice receives T_B:
     *   - T_B.ownDouble = D_B (Bob's) ← This is "other" for Alice
     *   - T_B.otherDouble = D_A (Alice's own) ← NOT "other" for Alice!
     */
    processEmbeddedTriple(triple) {
        if (!triple) return;

        // Extract embedded doubles, always process for commitment extraction
        if (triple.ownDouble) {
            this.processEmbeddedDouble(triple.ownDouble);
            // If the triple is from other party, their ownDouble is their double proof
            if (!this.otherDoubleProof && triple.ownDouble.party !== this.name) {
                this.otherDoubleProof = triple.ownDouble;
                this.embeddedProofs.add('D_other_from_T_own');
            }
        }
        if (triple.otherDouble) {
            this.processEmbeddedDouble(triple.otherDouble);
            // CRITICAL: Only set as other's double if it's actually from the other party!
            // This was the bug: we were setting our own proof as "other's"
            if (!this.otherDoubleProof && triple.otherDouble.party !== this.name) {
                this.otherDoubleProof = triple.otherDouble;
                this.embeddedProofs.add('D_other_from_T_other');
            }
        }

        // If this is the other party's triple, we can use it directly
        if (triple.party !== this.name && !this.otherTripleProof) {
            this.otherTripleProof = triple;
            this.embeddedProofs.add('T_other_embedded');
        }
    }

    /**
     * Extract embedded proofs from a Double proof.
     * D contains C_X and C_Y.
     */
    processEmbeddedDouble(double) {
        if (!double) return;

        // Extract embedded commitments
        if (double.otherCommitment && !this.otherCommitment) {
            // The other party's commitment might be in here
            if (double.otherCommitment.party !== this.name) {
                this.otherCommitment = double.otherCommitment;
                this.embeddedProofs.add('C_other_from_D');
            }
        }
        if (double.ownCommitment && double.ownCommitment.party !== this.name) {
            // This D was created by the other party, so ownCommitment is theirs
            if (!this.otherCommitment) {
                this.otherCommitment = double.ownCommitment;
                this.embeddedProofs.add('C_other_from_D');
            }
        }
    }

    /**
     * Try to advance to Double phase if we have the required proofs.
     * @returns {boolean} true if phase advanced
     */
    tryAdvanceToDouble() {
        if (this.phase === Phase.COMMITMENT && this.otherCommitment && !this.doubleProof) {
            this.doubleProof = this.createDoubleProof();
            this.phase = Phase.DOUBLE;
            this.proofArtifacts.push({
                type: 'double',
                label: `D_${this.isAlice ? 'A' : 'B'}`,
                description: 'Contains both commitments'
            });
            return true;
        }
        return false;
    }

    /**
     * Try to advance to Triple phase if we have the required proofs.
     * @returns {boolean} true if phase advanced
     */
    tryAdvanceToTriple() {
        let didAdvance = false;
        // First, ensure we're caught up from Commitment to Double
        if (this.phase === Phase.COMMITMENT && this.otherCommitment) {
            didAdvance = this.tryAdvanceToDouble() || didAdvance;
        }
        // Now try to advance to Triple
        if (this.phase === Phase.DOUBLE && this.otherDoubleProof && !this.tripleProof) {
            this.tripleProof = this.createTripleProof();
            this.phase = Phase.TRIPLE;
            this.proofArtifacts.push({
                type: 'triple',
                label: `T_${this.isAlice ? 'A' : 'B'}`,
                description: 'Contains both double proofs'
            });
            didAdvance = true;
        }
        return didAdvance;
    }

    /**
     * Try to advance to Quad phase if we have the required proofs.
     * @returns {boolean} true if phase advanced
     */
    tryAdvanceToQuad() {
        let didAdvance = false;
        // Ensure we're caught up on previous phases first
        didAdvance = this.tryAdvanceToTriple() || didAdvance;

        if (this.phase === Phase.TRIPLE && this.otherTripleProof && !this.quadProof) {
            this.quadProof = this.createQuadProof();
            this.phase = Phase.QUAD;
            this.proofArtifacts.push({
                type: 'quad',
                label: `Q_${this.isAlice ? 'A' : 'B'}`,
                description: 'Epistemic fixpoint achieved! (Q proves mutual constructibility)'
            });
            didAdvance = true;
        }
        return didAdvance;
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
        // CRITICAL: Party decides ATTACK as soon as they construct Q (Phase.QUAD)
        // NOT when they receive the other party's Q
        // This is the core of the bilateral construction property:
        // If I can construct Q_A, then Q_B is constructible
        return this.phase >= Phase.QUAD;
    }

    /**
     * Make the final decision based on protocol state and deadline.
     *
     * PROTOCOL RULES (from paper Algorithm 1):
     * - Upon constructing Q_X: decide ATTACK
     * - Upon deadline expires without Q: decide ABORT
     *
     * This is the key to symmetric outcomes:
     * - Both reach Q → Both ATTACK
     * - Neither reach Q → Both ABORT (deadline)
     * - One reaches Q → Bilateral construction guarantees the other can too,
     *   but if deadline is too short, both should ABORT
     */
    getDecision(deadlineExpired) {
        if (this.phase >= Phase.QUAD) {
            return 'ATTACK';
        }
        if (deadlineExpired) {
            return 'ABORT';
        }
        return 'PENDING';
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
// Proof Nesting Visualizer
// =============================================================================

class ProofNestingVisualizer {
    /**
     * Visualizes the bilateral construction property using D3.js.
     *
     * Shows how each proof level embeds the previous:
     * - C: Standalone commitment
     * - D: Contains C_A and C_B
     * - T: Contains D_A and D_B (which contain all C's)
     * - Q: Contains T_A and T_B (which contain all D's and C's)
     *
     * The visual demonstrates why Q is self-certifying:
     * having Q means having the entire proof tree.
     */
    constructor(svgSelector) {
        this.svg = d3.select(svgSelector);
        this.width = 800;
        this.height = 400;
        this.currentLevel = 0;

        this.colors = {
            alice: '#58a6ff',
            bob: '#3fb950',
            commitment: '#d29922',
            double: '#a371f7',
            triple: '#f0883e',
            quad: '#56d364',
            text: '#f0f6fc',
            muted: '#8b949e',
            bg: '#21262d'
        };

        this.setupSVG();
    }

    setupSVG() {
        this.svg.selectAll('*').remove();

        // Background
        this.svg.append('rect')
            .attr('width', this.width)
            .attr('height', this.height)
            .attr('fill', '#161b22')
            .attr('rx', 12);

        // Title
        this.svg.append('text')
            .attr('x', this.width / 2)
            .attr('y', 30)
            .attr('text-anchor', 'middle')
            .attr('fill', this.colors.text)
            .attr('font-size', '16px')
            .attr('font-weight', 'bold')
            .text('Proof Embedding Structure');

        // Create groups for each proof level
        this.proofGroup = this.svg.append('g')
            .attr('transform', 'translate(0, 50)');

        this.drawInitialState();
    }

    drawInitialState() {
        // Draw the nested box structure showing proof embedding
        const centerX = this.width / 2;
        const baseY = 50;

        // Q level (outermost)
        this.drawNestedBox({
            x: centerX - 350,
            y: baseY,
            width: 700,
            height: 280,
            label: 'Q (Quaternary Proof)',
            color: this.colors.quad,
            opacity: 0.1,
            id: 'q-box'
        });

        // T level
        this.drawNestedBox({
            x: centerX - 320,
            y: baseY + 30,
            width: 640,
            height: 220,
            label: 'T (Triple Proof)',
            color: this.colors.triple,
            opacity: 0.15,
            id: 't-box'
        });

        // D level
        this.drawNestedBox({
            x: centerX - 280,
            y: baseY + 60,
            width: 560,
            height: 160,
            label: 'D (Double Proof)',
            color: this.colors.double,
            opacity: 0.2,
            id: 'd-box'
        });

        // C level boxes (Alice and Bob side by side)
        this.drawProofBox({
            x: centerX - 250,
            y: baseY + 100,
            width: 200,
            height: 80,
            label: 'C_A',
            sublabel: 'Alice\'s Commitment',
            color: this.colors.alice,
            id: 'c-alice'
        });

        this.drawProofBox({
            x: centerX + 50,
            y: baseY + 100,
            width: 200,
            height: 80,
            label: 'C_B',
            sublabel: 'Bob\'s Commitment',
            color: this.colors.bob,
            id: 'c-bob'
        });

        // Add arrows showing embedding
        this.drawEmbeddingArrows();

        // Add legend
        this.drawLegend();

        // Add bilateral construction annotation
        this.drawBilateralAnnotation();
    }

    drawNestedBox({ x, y, width, height, label, color, opacity, id }) {
        const group = this.proofGroup.append('g')
            .attr('id', id);

        group.append('rect')
            .attr('x', x)
            .attr('y', y)
            .attr('width', width)
            .attr('height', height)
            .attr('rx', 8)
            .attr('fill', color)
            .attr('fill-opacity', opacity)
            .attr('stroke', color)
            .attr('stroke-width', 2)
            .attr('stroke-dasharray', '4,4');

        group.append('text')
            .attr('x', x + 10)
            .attr('y', y + 20)
            .attr('fill', color)
            .attr('font-size', '12px')
            .attr('font-weight', 'bold')
            .text(label);
    }

    drawProofBox({ x, y, width, height, label, sublabel, color, id }) {
        const group = this.proofGroup.append('g')
            .attr('id', id)
            .attr('class', 'proof-box');

        group.append('rect')
            .attr('x', x)
            .attr('y', y)
            .attr('width', width)
            .attr('height', height)
            .attr('rx', 6)
            .attr('fill', color)
            .attr('fill-opacity', 0.3)
            .attr('stroke', color)
            .attr('stroke-width', 2);

        group.append('text')
            .attr('x', x + width / 2)
            .attr('y', y + height / 2 - 8)
            .attr('text-anchor', 'middle')
            .attr('fill', this.colors.text)
            .attr('font-size', '18px')
            .attr('font-weight', 'bold')
            .text(label);

        group.append('text')
            .attr('x', x + width / 2)
            .attr('y', y + height / 2 + 12)
            .attr('text-anchor', 'middle')
            .attr('fill', this.colors.muted)
            .attr('font-size', '11px')
            .text(sublabel);
    }

    drawEmbeddingArrows() {
        const centerX = this.width / 2;

        // Arrow from D to C's
        const arrowGroup = this.proofGroup.append('g')
            .attr('class', 'embedding-arrows');

        // Add curved paths showing embedding
        const pathData = [
            { from: 'D', to: 'C_A + C_B', path: `M${centerX} 110 Q${centerX} 140 ${centerX - 50} 160` },
            { from: 'T', to: 'D_A + D_B', path: `M${centerX} 80 Q${centerX - 100} 100 ${centerX - 120} 125` },
            { from: 'Q', to: 'T_A + T_B', path: `M${centerX} 50 Q${centerX - 150} 70 ${centerX - 200} 95` }
        ];
    }

    drawLegend() {
        const legendX = 30;
        const legendY = 310;
        const items = [
            { color: this.colors.quad, label: 'Q: Epistemic Fixpoint' },
            { color: this.colors.triple, label: 'T: Triple Proof' },
            { color: this.colors.double, label: 'D: Double Proof' },
            { color: this.colors.commitment, label: 'C: Commitment' }
        ];

        const legend = this.proofGroup.append('g')
            .attr('class', 'legend');

        items.forEach((item, i) => {
            const g = legend.append('g')
                .attr('transform', `translate(${legendX + i * 180}, ${legendY})`);

            g.append('rect')
                .attr('width', 16)
                .attr('height', 16)
                .attr('rx', 3)
                .attr('fill', item.color)
                .attr('fill-opacity', 0.5)
                .attr('stroke', item.color);

            g.append('text')
                .attr('x', 22)
                .attr('y', 12)
                .attr('fill', this.colors.muted)
                .attr('font-size', '11px')
                .text(item.label);
        });
    }

    drawBilateralAnnotation() {
        const annotation = this.proofGroup.append('g')
            .attr('class', 'bilateral-annotation');

        annotation.append('text')
            .attr('x', this.width / 2)
            .attr('y', 345)
            .attr('text-anchor', 'middle')
            .attr('fill', this.colors.quad)
            .attr('font-size', '12px')
            .attr('font-weight', 'bold')
            .text('Q_A ↔ Q_B: Bilateral Receipt Pair');

        annotation.append('text')
            .attr('x', this.width / 2)
            .attr('y', 360)
            .attr('text-anchor', 'middle')
            .attr('fill', this.colors.muted)
            .attr('font-size', '10px')
            .text('Each half cryptographically proves the other is constructible');
    }

    highlightLevel(level) {
        // Animate highlighting a specific proof level
        const levelIds = ['c-alice', 'c-bob', 'd-box', 't-box', 'q-box'];
        const targetIds = level === 0 ? ['c-alice', 'c-bob'] :
                          level === 1 ? ['d-box'] :
                          level === 2 ? ['t-box'] :
                          level === 3 ? ['q-box'] : [];

        // Dim all boxes
        levelIds.forEach(id => {
            this.svg.select(`#${id}`).transition()
                .duration(300)
                .attr('opacity', 0.3);
        });

        // Highlight target boxes
        targetIds.forEach(id => {
            this.svg.select(`#${id}`).transition()
                .duration(300)
                .attr('opacity', 1);
        });
    }

    reset() {
        // Reset all boxes to full opacity
        ['c-alice', 'c-bob', 'd-box', 't-box', 'q-box'].forEach(id => {
            this.svg.select(`#${id}`).transition()
                .duration(300)
                .attr('opacity', 1);
        });
    }
}

// =============================================================================
// UI Controller
// =============================================================================

class UIController {
    constructor() {
        this.simulation = new ProtocolSimulation();
        this.packetViz = new PacketVisualizer('#packet-svg');
        this.nestingViz = new ProofNestingVisualizer('#nesting-svg');
        this.animationFrame = null;
        this.lastTime = 0;
        this.tickInterval = 100; // ms per tick

        this.bindEvents();
        this.bindSimulationEvents();
        this.updateUI();
    }

    bindEvents() {
        // Loss rate slider - supports extreme loss rates up to 99.9999%
        const lossSlider = document.getElementById('loss-rate');
        const lossValue = document.getElementById('loss-value');

        const updateLossRate = (value) => {
            // Map slider 0-100 to loss rate with logarithmic scaling for high end
            let lossRate;
            if (value <= 90) {
                lossRate = value;
            } else {
                // Exponential scaling from 90% to 99.9999%
                const remaining = value - 90; // 0-10
                const nines = remaining; // Number of 9s after decimal
                lossRate = 100 - Math.pow(10, -nines / 2);
            }
            const displayValue = lossRate >= 99.9 ? lossRate.toFixed(Math.max(0, Math.ceil(Math.log10(1 / (100 - lossRate))))) : lossRate.toFixed(1);
            lossValue.textContent = `${displayValue}%`;
            this.simulation.lossRate = lossRate / 100;
            this.currentLossRate = lossRate;
        };

        lossSlider.addEventListener('input', (e) => {
            updateLossRate(parseFloat(e.target.value));
        });

        // Loss rate preset buttons
        document.querySelectorAll('.loss-preset').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const lossRate = parseFloat(e.target.dataset.loss);
                this.simulation.lossRate = lossRate / 100;
                this.currentLossRate = lossRate;
                lossValue.textContent = `${lossRate}%`;
                // Update slider position approximately
                if (lossRate <= 90) {
                    lossSlider.value = lossRate;
                } else {
                    lossSlider.value = 90 + (100 - lossRate < 0.0001 ? 10 : -2 * Math.log10(100 - lossRate));
                }
            });
        });

        // Speed slider - exponential: 1x, 5x, 50x, 500x, 5000x
        const speedSlider = document.getElementById('speed');
        const speedValue = document.getElementById('speed-value');
        const speedLevels = [1, 5, 50, 500, 5000];

        speedSlider.addEventListener('input', (e) => {
            const idx = parseInt(e.target.value);
            const speed = speedLevels[idx] || 1;
            speedValue.textContent = `${speed}x`;
            this.simulation.speed = speed;
            this.tickInterval = 100 / Math.min(speed, 50); // Cap tick interval floor
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

        // Trials slider
        const trialsSlider = document.getElementById('trials-per-rate');
        const trialsValue = document.getElementById('trials-value');
        if (trialsSlider) {
            trialsSlider.addEventListener('input', (e) => {
                trialsValue.textContent = e.target.value;
            });
        }
    }

    bindSimulationEvents() {
        this.simulation.on('start', () => {
            document.getElementById('start-btn').disabled = true;
            this.updatePhases();
        });

        this.simulation.on('reset', () => {
            document.getElementById('start-btn').disabled = false;
            this.packetViz.clear();
            this.nestingViz.reset();
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
            // Highlight the corresponding level in the nesting diagram
            this.nestingViz.highlightLevel(data.phase - 1);
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
        const failureDetails = document.getElementById('failure-details');
        const progress = document.getElementById('theseus-progress');
        const button = document.getElementById('run-theseus');
        const trialsPerRate = parseInt(document.getElementById('trials-per-rate')?.value || '3');

        button.disabled = true;
        resultsContainer.innerHTML = '';
        if (failureDetails) {
            failureDetails.style.display = 'none';
            failureDetails.innerHTML = '';
        }

        // Create header with legend
        const header = document.createElement('div');
        header.className = 'theseus-header';
        header.innerHTML = `
            <div class="theseus-legend">
                <span class="legend-item"><span class="legend-color pending"></span> Pending</span>
                <span class="legend-item"><span class="legend-color attack"></span> ATTACK (both)</span>
                <span class="legend-item"><span class="legend-color retreat"></span> RETREAT (both)</span>
                <span class="legend-item"><span class="legend-color alice-only"></span> Alice attacked alone</span>
                <span class="legend-item"><span class="legend-color bob-only"></span> Bob attacked alone</span>
            </div>
            <div class="theseus-scale">
                <span>0%</span>
                <span>→</span>
                <span>99.9999% loss</span>
            </div>
        `;
        resultsContainer.appendChild(header);

        // Build loss rate test range from 0% to 99.9999%
        const lossRates = [];
        // 0-90% in 10% steps
        for (let i = 0; i <= 90; i += 10) lossRates.push(i);
        // 90-99% in 1% steps
        for (let i = 91; i <= 99; i++) lossRates.push(i);
        // 99-99.9% in 0.1% steps
        for (let i = 99.1; i <= 99.9; i += 0.1) lossRates.push(parseFloat(i.toFixed(1)));
        // Extreme loss rates
        lossRates.push(99.99, 99.999, 99.9999);

        // Create grid - always 10 columns wide for consistent aesthetics
        const grid = document.createElement('div');
        grid.className = 'theseus-grid-parallel';
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = 'repeat(10, 1fr)';
        grid.style.gap = '2px';
        resultsContainer.appendChild(grid);

        // Create all cells upfront
        const allCells = [];
        for (let r = 0; r < lossRates.length; r++) {
            const rowCells = [];
            for (let t = 0; t < trialsPerRate; t++) {
                const cell = document.createElement('div');
                cell.className = 'theseus-cell';
                cell.style.aspectRatio = '1';
                cell.dataset.tooltip = `${lossRates[r]}% loss - Trial ${t + 1}\nRunning...`;
                grid.appendChild(cell);
                rowCells.push(cell);
            }
            allCells.push(rowCells);
        }

        const totalTests = lossRates.length * trialsPerRate;
        let completed = 0;
        let symmetric = 0;
        let asymmetric = 0;
        let aborts = 0;
        let attacks = 0;
        const failures = [];
        let totalTicks = 0;
        let minTicks = Infinity;
        let maxTicks = 0;

        // Run all simulations in parallel batches
        const BATCH_SIZE = 5; // Run 5 loss rates in parallel

        for (let batchStart = 0; batchStart < lossRates.length; batchStart += BATCH_SIZE) {
            const batchEnd = Math.min(batchStart + BATCH_SIZE, lossRates.length);
            const batchPromises = [];

            for (let r = batchStart; r < batchEnd; r++) {
                const lossRatePercent = lossRates[r];
                const lossRate = lossRatePercent / 100;

                // Run all trials for this loss rate in parallel
                for (let t = 0; t < trialsPerRate; t++) {
                    const promise = this.runSingleSimulation(lossRate).then(result => {
                        completed++;
                        progress.textContent = `Running ${completed}/${totalTests}... (${lossRatePercent}% loss)`;

                        const cell = allCells[r][t];

                        if (result.symmetric) {
                            symmetric++;
                            if (result.outcome === 'ATTACK') {
                                attacks++;
                                cell.classList.add('attack');
                            } else {
                                aborts++;
                                cell.classList.add('retreat');
                            }
                        } else {
                            asymmetric++;
                            // Distinguish which party attacked alone
                            if (result.aliceDecision === 'ATTACK' && result.bobDecision !== 'ATTACK') {
                                cell.classList.add('alice-only');
                            } else if (result.bobDecision === 'ATTACK' && result.aliceDecision !== 'ATTACK') {
                                cell.classList.add('bob-only');
                            } else {
                                cell.classList.add('asymmetric');
                            }
                            failures.push({
                                lossRate: lossRatePercent,
                                trial: t + 1,
                                result,
                                cell
                            });
                        }

                        totalTicks += result.ticks;
                        minTicks = Math.min(minTicks, result.ticks);
                        maxTicks = Math.max(maxTicks, result.ticks);

                        // Update cell tooltip with detailed stats
                        const outcomeText = result.symmetric
                            ? `✓ ${result.outcome} (symmetric)`
                            : `✗ Alice:${result.aliceDecision} Bob:${result.bobDecision} (ASYMMETRIC!)`;
                        const phaseName = (p) => ['INIT', 'C', 'D', 'T', 'Q', 'COMPLETE'][p] || '?';
                        cell.dataset.tooltip = [
                            `Loss Rate: ${lossRatePercent}%`,
                            `Trial: ${t + 1}`,
                            `Outcome: ${outcomeText}`,
                            `Ticks: ${result.ticks.toLocaleString()}`,
                            `Alice: Phase ${phaseName(result.alicePhase)} → ${result.aliceDecision}`,
                            `Bob: Phase ${phaseName(result.bobPhase)} → ${result.bobDecision}`,
                            result.fastForwarded ? '⚡ Fast-forwarded (both reached Q)' : ''
                        ].filter(Boolean).join('\n');

                        return result;
                    });
                    batchPromises.push(promise);
                }
            }

            // Wait for batch to complete
            await Promise.all(batchPromises);
        }

        progress.textContent = '';

        // Show detailed summary
        const summary = document.createElement('div');
        summary.className = 'theseus-summary';
        const avgTicks = (totalTicks / totalTests).toFixed(1);
        summary.innerHTML = `
            <div class="summary-row">
                <strong>Results:</strong> ${attacks} ATTACK, ${aborts} RETREAT, ${asymmetric} asymmetric failures
            </div>
            <div class="summary-row">
                <strong>Convergence:</strong> avg ${avgTicks} ticks (min: ${minTicks}, max: ${maxTicks})
            </div>
            <div class="summary-row outcome">
                ${asymmetric === 0
                    ? '<span class="pass">✓ Protocol of Theseus: PASSED</span><br><em>Zero asymmetric outcomes across ' + totalTests + ' trials (0% → 99.9999% loss)</em>'
                    : '<span class="fail">✗ Protocol of Theseus: FAILED</span><br><em>' + asymmetric + ' asymmetric outcome(s) detected - see analysis below</em>'}
            </div>
            <div class="summary-row insight">
                <strong>Key Insight:</strong> With 10M tick deadline and proof embedding, the bilateral construction<br>
                property guarantees symmetric outcomes. Any failure indicates a simulation bug, not protocol failure.
            </div>
        `;
        resultsContainer.appendChild(summary);

        // Show failure analysis if any asymmetric outcomes
        if (failures.length > 0 && failureDetails) {
            failureDetails.style.display = 'block';
            failureDetails.innerHTML = `
                <h3>⚠️ Asymmetric Failure Analysis</h3>
                <p>The following trials produced asymmetric outcomes. This should be IMPOSSIBLE with a correct implementation.</p>
                <div class="failure-list">
                    ${failures.map(f => `
                        <div class="failure-item">
                            <strong>${f.lossRate}% loss - Trial ${f.trial}</strong>
                            <ul>
                                <li>Alice: Phase ${f.result.alicePhase} → Decision: ${f.result.aliceDecision}</li>
                                <li>Bob: Phase ${f.result.bobPhase} → Decision: ${f.result.bobDecision}</li>
                                <li>Ticks: ${f.result.ticks} / 10,000,000</li>
                                <li>Fast-forwarded: ${f.result.fastForwarded ? 'Yes' : 'No'}</li>
                            </ul>
                            <p class="failure-analysis">
                                ${this.analyzeFailure(f.result)}
                            </p>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        button.disabled = false;
    }

    /**
     * Analyze why an asymmetric outcome occurred.
     * This should NEVER happen with correct protocol implementation.
     */
    analyzeFailure(result) {
        const { alicePhase, bobPhase, aliceDecision, bobDecision, ticks } = result;

        if (aliceDecision === 'ATTACK' && bobDecision === 'ABORT') {
            if (alicePhase >= 4 && bobPhase < 4) {
                return `BUG: Alice reached QUAD (phase ${alicePhase}) but Bob stuck at phase ${bobPhase}. ` +
                       `This violates bilateral construction - if Alice has Q_A, she must have T_B, ` +
                       `which means Bob reached TRIPLE and could construct Q_B. Check proof embedding logic.`;
            }
        }

        if (bobDecision === 'ATTACK' && aliceDecision === 'ABORT') {
            if (bobPhase >= 4 && alicePhase < 4) {
                return `BUG: Bob reached QUAD (phase ${bobPhase}) but Alice stuck at phase ${alicePhase}. ` +
                       `This violates bilateral construction - if Bob has Q_B, he must have T_A, ` +
                       `which means Alice reached TRIPLE and could construct Q_A. Check proof embedding logic.`;
            }
        }

        if (ticks >= 10000000) {
            return `Deadline reached (10M ticks). Both parties should ABORT symmetrically, ` +
                   `but got Alice:${aliceDecision} Bob:${bobDecision}. Check getDecision() logic.`;
        }

        return `Unknown failure mode. Alice: phase ${alicePhase} → ${aliceDecision}, ` +
               `Bob: phase ${bobPhase} → ${bobDecision}. Investigate simulation state.`;
    }

    /**
     * Run a single TGP simulation with correct protocol semantics.
     * OPTIMIZED: Runs synchronously in batches for speed.
     *
     * CRITICAL PROTOCOL RULES:
     * 1. Each party decides ATTACK upon constructing their Q (Phase.QUAD)
     * 2. Each party decides ABORT if deadline expires without Q
     * 3. The bilateral construction property guarantees:
     *    - If Alice can construct Q_A, Bob can construct Q_B (given fair-lossy)
     *    - Therefore: both reach Q → both ATTACK (symmetric)
     *    - Neither reach Q → both ABORT (symmetric)
     *    - IMPOSSIBLE: one ATTACK, one ABORT (would violate bilateral property)
     */
    runSingleSimulation(lossRate) {
        return new Promise((resolve) => {
            const sim = new ProtocolSimulation(lossRate);
            sim.start();

            let ticks = 0;
            // Model: 1000 msgs/sec for 18 hours = 64,800,000 attempts
            // 10M ticks with batching gives plenty of margin for extreme loss rates
            const maxTicks = 10000000;

            // Run synchronously in batches for SPEED
            const BATCH_SIZE = 100; // Process 100 ticks at a time

            const runBatch = () => {
                for (let i = 0; i < BATCH_SIZE && ticks < maxTicks; i++) {
                    sim.step();
                    ticks++;

                    // EARLY TERMINATION: Once both reach QUAD, fast-forward!
                    const aliceCanAttack = sim.alice.canAttack();
                    const bobCanAttack = sim.bob.canAttack();

                    if (aliceCanAttack && bobCanAttack) {
                        resolve({
                            symmetric: true,
                            aliceDecision: 'ATTACK',
                            bobDecision: 'ATTACK',
                            alicePhase: sim.alice.phase,
                            bobPhase: sim.bob.phase,
                            ticks,
                            lossRate,
                            outcome: 'ATTACK',
                            fastForwarded: true
                        });
                        return true; // Done
                    }
                }
                return false; // Not done yet
            };

            // Run batches until done or deadline
            const runLoop = () => {
                if (runBatch()) return; // Early termination

                if (ticks >= maxTicks) {
                    // Deadline expired - both ABORT (symmetric)
                    const aliceDecision = sim.alice.getDecision(true);
                    const bobDecision = sim.bob.getDecision(true);
                    const symmetric = (aliceDecision === bobDecision);

                    resolve({
                        symmetric,
                        aliceDecision,
                        bobDecision,
                        alicePhase: sim.alice.phase,
                        bobPhase: sim.bob.phase,
                        ticks,
                        lossRate,
                        outcome: symmetric ? aliceDecision : 'ASYMMETRIC',
                        fastForwarded: false
                    });
                } else {
                    // Yield to browser, then continue
                    setTimeout(runLoop, 0);
                }
            };

            runLoop();
        });
    }
}

// =============================================================================
// Initialize
// =============================================================================

document.addEventListener('DOMContentLoaded', async () => {
    // Attempt to load WASM module (optional enhancement)
    await initWasm();

    // Initialize the UI controller
    window.controller = new UIController();

    // Update UI to show which engine is being used
    const engineIndicator = document.createElement('div');
    engineIndicator.className = 'engine-indicator';
    engineIndicator.innerHTML = useWasm
        ? '<span class="wasm">🔥 WASM Engine</span>'
        : '<span class="js">⚡ JS Engine</span>';
    document.querySelector('.controls').appendChild(engineIndicator);
});
