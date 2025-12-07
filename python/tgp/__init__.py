"""
Two Generals Protocol (TGP) - Pure Epistemic Implementation

A deterministically failsafe solution to the Coordinated Attack Problem
using cryptographic proof stapling and bilateral construction properties.
"""

__version__ = "0.1.0"
__author__ = "Riff Labs"
__license__ = "AGPLv3"

from .types import (
    Commitment,
    DoubleProof,
    TripleProof,
    QuadProof,
    Party,
    Message,
    Decision,
    ProtocolOutcome,
    ProtocolPhase,
    BilateralReceipt,
    # V3 FULL SOLVE types
    QuadConfirmation,
    QuadConfirmationFinal,
    FinalReceipt,
    ProtocolPhaseV3,
)
from .crypto import KeyPair, PublicKey
from .protocol import (
    TwoGenerals,
    ProtocolState,
    ProtocolMessage,
    run_protocol_simulation,
    # V3 FULL SOLVE
    TwoGeneralsV3,
    run_protocol_simulation_v3,
)

# Network transport abstractions
from .network import (
    Transport,
    AsyncTransport,
    InMemoryChannel,
    InMemoryTransport,
    ChannelPair,
    UDPEndpoint,
    UDPTransport,
    FloodingConfig,
    FloodingEngine,
    NetworkStats,
    serialize_message,
    deserialize_message,
    run_simulation,
)

__all__ = [
    # Core types (epistemic ladder)
    "Commitment",
    "DoubleProof",
    "TripleProof",
    "QuadProof",
    "Party",
    "Message",
    "Decision",
    "ProtocolOutcome",
    "ProtocolPhase",
    "BilateralReceipt",
    # V3 FULL SOLVE types (confirmation layer)
    "QuadConfirmation",
    "QuadConfirmationFinal",
    "FinalReceipt",
    "ProtocolPhaseV3",
    # Crypto
    "KeyPair",
    "PublicKey",
    # Protocol (base + V3)
    "TwoGenerals",
    "ProtocolState",
    "ProtocolMessage",
    "run_protocol_simulation",
    "TwoGeneralsV3",
    "run_protocol_simulation_v3",
    # Network transport
    "Transport",
    "AsyncTransport",
    "InMemoryChannel",
    "InMemoryTransport",
    "ChannelPair",
    "UDPEndpoint",
    "UDPTransport",
    "FloodingConfig",
    "FloodingEngine",
    "NetworkStats",
    "serialize_message",
    "deserialize_message",
    "run_simulation",
]