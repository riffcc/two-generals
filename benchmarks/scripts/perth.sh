#!/bin/bash

# TGP-Piper Perth Benchmark
# Measures intercontinental performance to Australia

set -euo pipefail

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Parse command line arguments
REMOTE_HOST="${TGP_BENCH_PERTH_HOST}"
RUN_ID="${1:-perth-$(generate_timestamp)}"
FILE_SIZE="${TGP_BENCH_FILE_SIZE_PERTH}"
RUNS="${TGP_BENCH_RUNS}"
WARMUP_RUNS="${TGP_BENCH_WARMUP_RUNS}"

# Create data directory
DATA_DIR="$(create_data_dir "perth" "$RUN_ID")"

# Check if TGP-Piper binary exists
if ! check_binary "$TGP_PIPER_BIN" "TGP-Piper"; then
    echo "Please build TGP-Piper first: cd ../../rust && cargo build --release"
    exit 1
fi

echo "=========================================="
echo "TGP-Piper Perth Benchmark"
echo "=========================================="
echo "Remote Host: $REMOTE_HOST"
echo "Run ID: $RUN_ID"
echo "File Size: $FILE_SIZE"
echo "Warmup Runs: $WARMUP_RUNS"
echo "Measurement Runs: $RUNS"
echo "Data Directory: $DATA_DIR"
echo "=========================================="
echo

# Create test file
create_test_file() {
    local size=$1
    local file="$DATA_DIR/testfile"

    echo "Creating test file: $size"
    dd if=/dev/zero of="$file" bs="$size" count=1 status=none
    echo "Test file created: $(du -h "$file" | cut -f1)"
}

# Check if remote host is reachable
check_remote_host() {
    local host=$1

    echo "Checking if $host is reachable..."
    if ! ping -c 1 -W 5 "$host" &>/dev/null; then
        echo "Warning: Cannot reach $host via ping (ICMP may be blocked)"
        echo "Attempting SSH connection test..."
        if ! timeout 10 ssh -o ConnectTimeout=5 "$host" echo "OK" &>/dev/null; then
            echo "Error: Cannot reach $host"
            echo "Please ensure the remote host is online and reachable"
            exit 1
        fi
    fi
    echo "$host is reachable"
}

# Measure network conditions
measure_network_conditions() {
    local host=$1
    local output_file="$DATA_DIR/network_conditions.txt"

    echo "Measuring network conditions to $host..."
    echo "Network Conditions Report - $(date)" > "$output_file"
    echo "==========================================" >> "$output_file"

    # Ping test
    echo "" >> "$output_file"
    echo "Ping Test:" >> "$output_file"
    ping -c 10 "$host" >> "$output_file" 2>&1 || echo "Ping failed" >> "$output_file"

    # Traceroute
    echo "" >> "$output_file"
    echo "Traceroute:" >> "$output_file"
    traceroute "$host" >> "$output_file" 2>&1 || echo "Traceroute failed" >> "$output_file"

    # MTR (if available)
    if command -v mtr &>/dev/null; then
        echo "" >> "$output_file"
        echo "MTR Report:" >> "$output_file"
        mtr --report "$host" >> "$output_file" 2>&1 || echo "MTR failed" >> "$output_file"
    fi

    cat "$output_file"
}

# Run single benchmark
run_benchmark() {
    local run_num=$1
    local output_file="$DATA_DIR/run_$run_num.json"
    local log_file="$DATA_DIR/run_$run_num.log"

    echo "Running benchmark $run_num/$RUNS..."

    # Start server on remote host
    echo "Starting TGP-Piper server on $REMOTE_HOST..."
    ssh "$REMOTE_HOST" "\$TGP_PIPER_BIN receive --port $TGP_BENCH_PORT \
        --metrics-interval $TGP_BENCH_METRICS_INTERVAL > /tmp/tgp_server.log 2>&1 &"

    # Give server time to start (longer for intercontinental)
    sleep 5

    # Run client and capture metrics
    echo "Starting TGP-Piper client..."
    local start_time=$(date +%s%N)
    timeout "$TGP_BENCH_TIMEOUT_PERTH" \
        $TGP_PIPER_BIN send --host "$REMOTE_HOST" --port "$TGP_BENCH_PORT" \
        --file "$DATA_DIR/testfile" --json-output > "$output_file" 2>&1
    local end_time=$(date +%s%N)

    # Calculate duration
    local duration_ms=$(( (end_time - start_time) / 1000000 ))

    # Stop server on remote host
    ssh "$REMOTE_HOST" "killall tgp-piper 2>/dev/null || true"

    # Copy server logs
    scp "$REMOTE_HOST:/tmp/tgp_server.log" "$log_file" 2>/dev/null || true

    echo "Benchmark $run_num completed in ${duration_ms}ms"
}

# Main execution
main() {
    # Check remote host
    check_remote_host "$REMOTE_HOST"

    # Measure network conditions
    measure_network_conditions "$REMOTE_HOST"

    # Create test file
    create_test_file "$FILE_SIZE"

    # Warmup runs
    echo "Running warmup..."
    for ((i=1; i<=$WARMUP_RUNS; i++)); do
        echo "Warmup run $i/$WARMUP_RUNS"
        run_benchmark "warmup_$i" > /dev/null 2>&1
    done
    echo "Warmup complete"
    echo

    # Measurement runs
    echo "Running measurement benchmarks..."
    for ((i=1; i<=$RUNS; i++)); do
        run_benchmark "$i"
    done

    # Generate summary
    echo
    echo "Generating summary..."
    python3 "$SCRIPT_DIR/analyze.py" "$DATA_DIR" > "$DATA_DIR/summary.txt"
    cat "$DATA_DIR/summary.txt"

    echo
    echo "=========================================="
    echo "Benchmark complete!"
    echo "Results saved to: $DATA_DIR"
    echo "=========================================="
}

# Run main function
main
