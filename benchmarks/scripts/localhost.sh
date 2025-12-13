#!/bin/bash

# TGP-Piper Localhost Benchmark
# Measures baseline performance on the same machine

set -euo pipefail

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Parse command line arguments
RUN_ID="${1:-localhost-$(generate_timestamp)}"
FILE_SIZE="${TGP_BENCH_FILE_SIZE_LOCALHOST}"
RUNS="${TGP_BENCH_RUNS}"
WARMUP_RUNS="${TGP_BENCH_WARMUP_RUNS}"

# Create data directory
DATA_DIR="$(create_data_dir "localhost" "$RUN_ID")"

# Check if TGP-Piper binary exists
if ! check_binary "$TGP_PIPER_BIN" "TGP-Piper"; then
    echo "Please build TGP-Piper first: cd ../../rust && cargo build --release"
    exit 1
fi

echo "=========================================="
echo "TGP-Piper Localhost Benchmark"
echo "=========================================="
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

# Run single benchmark
run_benchmark() {
    local run_num=$1
    local output_file="$DATA_DIR/run_$run_num.json"
    local log_file="$DATA_DIR/run_$run_num.log"

    echo "Running benchmark $run_num/$RUNS..."

    # Start server in background
    echo "Starting TGP-Piper server..."
    $TGP_PIPER_BIN receive --port "$TGP_BENCH_PORT" --metrics-interval "$TGP_BENCH_METRICS_INTERVAL" \
        > "$log_file" 2>&1 &
    local server_pid=$!

    # Give server time to start
    sleep 1

    # Run client and capture metrics
    echo "Starting TGP-Piper client..."
    local start_time=$(date +%s%N)
    $TGP_PIPER_BIN send --host localhost --port "$TGP_BENCH_PORT" \
        --file "$DATA_DIR/testfile" --json-output > "$output_file" 2>&1
    local end_time=$(date +%s%N)

    # Calculate duration
    local duration_ms=$(( (end_time - start_time) / 1000000 ))

    # Stop server
    kill $server_pid 2>/dev/null || true
    wait $server_pid 2>/dev/null || true

    echo "Benchmark $run_num completed in ${duration_ms}ms"
}

# Main execution
main() {
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
