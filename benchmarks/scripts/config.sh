#!/bin/bash

# TGP-Piper Benchmark Configuration
# This file defines default parameters for all benchmarks

# ============================================
# Global Settings
# ============================================

# Default file sizes for different scenarios
export TGP_BENCH_FILE_SIZE_LOCALHOST="1G"
export TGP_BENCH_FILE_SIZE_LAN="1G"
export TGP_BENCH_FILE_SIZE_PERTH="100M"

# Number of benchmark runs
export TGP_BENCH_RUNS=5
export TGP_BENCH_WARMUP_RUNS=2

# Network settings
export TGP_BENCH_PORT=8000
export TGP_BENCH_PERTH_HOST="barbara.per.riff.cc"
export TGP_BENCH_LAN_HOST="tealc.local"

# Timeout values (in seconds)
export TGP_BENCH_TIMEOUT_LOCALHOST=300
export TGP_BENCH_TIMEOUT_LAN=600
export TGP_BENCH_TIMEOUT_PERTH=1800

# Verbosity level (0=quiet, 1=normal, 2=verbose, 3=debug)
export TGP_BENCH_VERBOSITY=1

# Data directories
export TGP_BENCH_DATA_DIR="$(dirname "$0")/../data"
export TGP_BENCH_RESULTS_DIR="$(dirname "$0")/../results"
export TGP_BENCH_VIS_DIR="$(dirname "$0")/../visualization"

# ============================================
# TGP-Piper Binary Settings
# ============================================

# Path to TGP-Piper binary
export TGP_PIPER_BIN="$(dirname "$0")/../../rust/target/release/tgp-piper"

# If binary doesn't exist, try debug build
if [ ! -f "$TGP_PIPER_BIN" ]; then
    export TGP_PIPER_BIN="$(dirname "$0")/../../rust/target/debug/tgp-piper"
fi

# ============================================
# PipePiper Baseline Settings
# ============================================

# Path to PipePiper binary (for comparison)
export PIPER_BIN="$(which ppr 2>/dev/null || echo '/usr/local/bin/ppr')"

# ============================================
# Network Simulation Settings
# ============================================

# Default network conditions for testing
export TGP_BENCH_SIM_LATENCY="0ms"
export TGP_BENCH_SIM_JITTER="0ms"
export TGP_BENCH_SIM_LOSS="0%"

# ============================================
# Data Collection Settings
# ============================================

# System metrics collection interval
export TGP_BENCH_METRICS_INTERVAL="0.1"

# Enable/disable specific metrics
export TGP_BENCH_COLLECT_CPU=true
export TGP_BENCH_COLLECT_MEMORY=true
export TGP_BENCH_COLLECT_NETWORK=true
export TGP_BENCH_COLLECT_DISK=false

# ============================================
# Visualization Settings
# ============================================

export TGP_BENCH_PLOT_FORMAT="png"
export TGP_BENCH_PLOT_DPI=300
export TGP_BENCH_PLOT_STYLE="seaborn"

# ============================================
# Helper Functions
# ============================================

# Create data directory for a specific run
create_data_dir() {
    local scenario=$1
    local run_id=$2
    local dir="$TGP_BENCH_DATA_DIR/$scenario/$run_id"

    mkdir -p "$dir"
    echo "$dir"
}

# Generate timestamp for run
generate_timestamp() {
    date +"%Y%m%d-%H%M%S"
}

# Check if binary exists
check_binary() {
    local bin=$1
    local name=$2

    if [ ! -f "$bin" ]; then
        echo "Error: $name binary not found at $bin"
        return 1
    fi

    if [ ! -x "$bin" ]; then
        echo "Error: $bin is not executable"
        return 1
    fi

    return 0
}

# Validate file size
validate_file_size() {
    local size=$1

    case "$size" in
        *[0-9]G) return 0 ;;
        *[0-9]M) return 0 ;;
        *[0-9]K) return 0 ;;
        *[0-9]) return 0 ;;
        *)
            echo "Error: Invalid file size '$size'. Use format like 1G, 100M, 10K"
            return 1
            ;;
    esac
}

# ============================================
# Initialize Configuration
# ============================================

# Source this file to load configuration
# Example: source "$(dirname "$0")/config.sh"
