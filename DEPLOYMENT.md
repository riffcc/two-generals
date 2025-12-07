# TGP Deployment Guide

Deploy Two Generals Protocol nodes across distributed infrastructure.

## Quick Start

```bash
# Clone and install
git clone https://github.com/riff-labs/two-generals-public.git
cd two-generals-public/python
pip install -e .

# Generate keypairs
python -m tgp.cli keygen --output alice.key
python -m tgp.cli keygen --output bob.key

# Run demo locally
python -m tgp.cli demo --loss 0.5 --rounds 100
```

## Prerequisites

- Python 3.10+
- Dependencies: `cryptography>=41.0.0`, `cbor2>=5.6.0`
- UDP port 8000 (or custom) open between nodes
- Network connectivity between all nodes

## Installation

### From Source (Recommended for Development)

```bash
# On each node
git clone https://github.com/riff-labs/two-generals-public.git
cd two-generals-public/python
pip install -e ".[dev]"
```

### From PyPI (When Published)

```bash
pip install tgp
```

## Multi-Node Deployment

### Example: Three-Node Setup

Deploy TGP nodes across:
- **New York**: 10.8.1.37
- **London**: 10.7.1.37
- **Perth**: learn.per.riff.cc

### Step 1: Generate Keypairs

On your local machine, generate keypairs for all nodes:

```bash
cd two-generals-public/python

# Generate keypairs for each location
python -m tgp.cli keygen --output keys/newyork.key
python -m tgp.cli keygen --output keys/london.key
python -m tgp.cli keygen --output keys/perth.key

# View public keys
python -m tgp.cli show-key keys/newyork.key
python -m tgp.cli show-key keys/london.key
python -m tgp.cli show-key keys/perth.key
```

### Step 2: Distribute Keys

Copy keys to each node:

```bash
# To New York (10.8.1.37)
scp keys/newyork.key root@10.8.1.37:/opt/tgp/
scp keys/london.pub keys/perth.pub root@10.8.1.37:/opt/tgp/

# To London (10.7.1.37)
scp keys/london.key root@10.7.1.37:/opt/tgp/
scp keys/newyork.pub keys/perth.pub root@10.7.1.37:/opt/tgp/

# To Perth (learn.per.riff.cc)
scp keys/perth.key root@learn.per.riff.cc:/opt/tgp/
scp keys/newyork.pub keys/london.pub root@learn.per.riff.cc:/opt/tgp/
```

### Step 3: Install TGP on Each Node

SSH to each node and install:

```bash
# On each node
ssh root@<node-ip>
cd /opt
git clone https://github.com/riff-labs/two-generals-public.git
cd two-generals-public/python
pip install -e .
```

### Step 4: Open Firewall Ports

On each node, ensure UDP 8000 is open:

```bash
# UFW
ufw allow 8000/udp

# iptables
iptables -A INPUT -p udp --dport 8000 -j ACCEPT

# firewalld
firewall-cmd --add-port=8000/udp --permanent
firewall-cmd --reload
```

### Step 5: Run Coordination Protocol

#### Two-Party Coordination (New York ↔ London)

**On New York (10.8.1.37) - Initiator:**
```bash
cd /opt/two-generals-public/python
python -m tgp.cli run \
    --role initiator \
    --key /opt/tgp/newyork.key \
    --peer-key /opt/tgp/london.pub \
    --local 0.0.0.0:8000 \
    --remote 10.7.1.37:8000 \
    --timeout 60 \
    --verbose
```

**On London (10.7.1.37) - Responder:**
```bash
cd /opt/two-generals-public/python
python -m tgp.cli run \
    --role responder \
    --key /opt/tgp/london.key \
    --peer-key /opt/tgp/newyork.pub \
    --local 0.0.0.0:8000 \
    --remote 10.8.1.37:8000 \
    --timeout 60 \
    --verbose
```

Expected output (both nodes):
```
Starting TGP node as initiator
  Local:  0.0.0.0:8000
  Remote: 10.7.1.37:8000
  Party:  ALICE
  Timeout: 60.0s
  -> Sent COMMITMENT (156 bytes)
  <- Recv COMMITMENT (156 bytes)
  -> Sent DOUBLE_PROOF (512 bytes)
  <- Recv DOUBLE_PROOF (512 bytes)
  -> Sent TRIPLE_PROOF (1280 bytes)
  <- Recv TRIPLE_PROOF (1280 bytes)
Protocol complete! State: COMPLETE

Result: ATTACK
```

#### Three-Party Coordination

For three parties, run multiple bilateral protocols or use the BFT extension (Part III):

```bash
# New York ↔ London
# (run commands above)

# London ↔ Perth
# On London:
python -m tgp.cli run \
    --role initiator \
    --key /opt/tgp/london.key \
    --peer-key /opt/tgp/perth.pub \
    --local 0.0.0.0:8001 \
    --remote learn.per.riff.cc:8000 \
    --timeout 60

# On Perth:
python -m tgp.cli run \
    --role responder \
    --key /opt/tgp/perth.key \
    --peer-key /opt/tgp/london.pub \
    --local 0.0.0.0:8000 \
    --remote 10.7.1.37:8001 \
    --timeout 60
```

## CLI Reference

### Commands

```bash
# Generate new keypair
python -m tgp.cli keygen --output <keyfile>

# Show public key
python -m tgp.cli show-key <keyfile>

# Run TGP node
python -m tgp.cli run \
    --role <initiator|responder> \
    --key <keypair-file> \
    --peer-key <peer-public-key-file> \
    --local <host:port> \
    --remote <host:port> \
    [--timeout <seconds>] \
    [--interval <seconds>] \
    [--verbose]

# Run local demo
python -m tgp.cli demo \
    [--loss <0.0-0.99>] \
    [--rounds <max-rounds>] \
    [--verbose]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--role` | Protocol role (initiator/responder) | Required |
| `--key` | Path to keypair file | Required |
| `--peer-key` | Path to peer's public key | Required |
| `--local` | Local endpoint (host:port) | Required |
| `--remote` | Remote endpoint (host:port) | Required |
| `--timeout` | Protocol timeout in seconds | 30 |
| `--interval` | Flood interval in seconds | 0.1 |
| `--verbose` | Enable verbose output | False |

## Troubleshooting

### "Connection refused" or timeout

1. Check firewall rules on both nodes
2. Verify UDP connectivity: `nc -u -v <remote-ip> 8000`
3. Ensure both nodes start within timeout window

### "Invalid peer key"

1. Verify public key file format (JSON with `public_key` field)
2. Re-copy public key from source

### Protocol stuck in COMMITMENT

1. Increase timeout (`--timeout 120`)
2. Check network latency
3. Reduce flood interval (`--interval 0.05`)

### Asymmetric outcomes

**This should never happen!** If it does:
1. Check clock synchronization (NTP)
2. Verify keypairs match expectations
3. Report as bug with full logs

## Security Considerations

1. **Protect private keys**: Store `.key` files securely (chmod 600)
2. **Distribute only public keys**: Never share `.key` files
3. **Use TLS for key exchange**: When distributing public keys over network
4. **Verify key fingerprints**: Out-of-band verification recommended

## Performance Tuning

### High-Latency Links (Satellite, Intercontinental)

```bash
python -m tgp.cli run \
    --timeout 120 \
    --interval 0.5 \
    ...
```

### Lossy Networks

TGP is designed for lossy networks. No special tuning needed - the continuous flooding handles packet loss automatically.

### High-Throughput (LAN)

```bash
python -m tgp.cli run \
    --interval 0.01 \
    ...
```

## Systemd Service

Create `/etc/systemd/system/tgp-node.service`:

```ini
[Unit]
Description=TGP Protocol Node
After=network.target

[Service]
Type=simple
User=tgp
WorkingDirectory=/opt/two-generals-public/python
ExecStart=/usr/bin/python3 -m tgp.cli run \
    --role responder \
    --key /opt/tgp/node.key \
    --peer-key /opt/tgp/peer.pub \
    --local 0.0.0.0:8000 \
    --remote peer.example.com:8000 \
    --timeout 300
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable tgp-node
systemctl start tgp-node
```

## Example Network Topology

```
                    ┌─────────────┐
                    │   Perth     │
                    │learn.per... │
                    │  UDP:8000   │
                    └──────┬──────┘
                           │
                           │ TGP
                           │
    ┌──────────────────────┴──────────────────────┐
    │                                              │
    │                                              │
┌───┴───────┐                              ┌───────┴───┐
│ New York  │◄────────── TGP ─────────────►│  London   │
│ 10.8.1.37 │                              │ 10.7.1.37 │
│ UDP:8000  │                              │ UDP:8000  │
└───────────┘                              └───────────┘
```

## Protocol Guarantees

- **Symmetric outcomes**: Both ATTACK or both ABORT - never asymmetric
- **Loss tolerance**: Works at 90%+ packet loss rates
- **Deterministic**: Same inputs produce same outputs
- **Self-certifying**: Q proof is proof of coordination

## Next Steps

- For BFT multiparty consensus, see `python/tgp/bft.py`
- For TCP-over-TGP transport, see roadmap in `CLAUDE.md`
- For Rust implementation, see `rust/` directory
