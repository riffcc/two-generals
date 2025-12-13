#!/bin/bash

# TGP-Piper Benchmarking Setup
# Installs all required dependencies

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "TGP-Piper Benchmarking Setup"
echo "=========================================="
echo

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    jq \
    bc \
    plotutils \
    ping \
    traceroute \
    mtr \
    ssh \
    scp

echo "✓ System dependencies installed"
echo

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --user -r "$SCRIPT_DIR/requirements.txt"

echo "✓ Python dependencies installed"
echo

# Verify installation
echo "Verifying installation..."
python3 -c "import matplotlib; print('✓ matplotlib', matplotlib.__version__)"
python3 -c "import pandas; print('✓ pandas', pandas.__version__)"
python3 -c "import numpy; print('✓ numpy', numpy.__version__)"

echo
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
