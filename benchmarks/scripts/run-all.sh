#!/bin/bash

# TGP-Piper Benchmark Suite Runner
# Runs all benchmarks and generates comprehensive reports

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"

# Parse command line arguments
RUN_ID="${1:-full-run-$(generate_timestamp)}"

# Create root data directory
ROOT_DATA_DIR="$TGP_BENCH_DATA_DIR/$RUN_ID"
mkdir -p "$ROOT_DATA_DIR"

echo "=========================================="
echo "TGP-Piper Full Benchmark Suite"
echo "=========================================="
echo "Run ID: $RUN_ID"
echo "Data Directory: $ROOT_DATA_DIR"
echo "=========================================="
echo

# Run localhost benchmark
run_localhost() {
    echo "=========================================="
    echo "Running Localhost Benchmark"
    echo "=========================================="
    "$SCRIPT_DIR/localhost.sh" "$RUN_ID"
    echo
}

# Run LAN benchmark
run_lan() {
    echo "=========================================="
    echo "Running LAN Benchmark"
    echo "=========================================="
    "$SCRIPT_DIR/lan.sh" "$TGP_BENCH_LAN_HOST" "$RUN_ID"
    echo
}

# Run Perth benchmark
run_perth() {
    echo "=========================================="
    echo "Running Perth Benchmark"
    echo "=========================================="
    "$SCRIPT_DIR/perth.sh" "$RUN_ID"
    echo
}

# Generate comprehensive report
generate_report() {
    echo "=========================================="
    echo "Generating Comprehensive Report"
    echo "=========================================="

    local report_dir="$TGP_BENCH_RESULTS_DIR/$RUN_ID"
    mkdir -p "$report_dir"

    # Analyze each scenario
    for scenario in localhost lan perth; do
        if [ -d "$TGP_BENCH_DATA_DIR/$scenario/$RUN_ID" ]; then
            echo "Analyzing $scenario..."
            python3 "$SCRIPT_DIR/analyze.py" "$TGP_BENCH_DATA_DIR/$scenario/$RUN_ID"
            python3 "$SCRIPT_DIR/visualize.py" "$TGP_BENCH_DATA_DIR/$scenario/$RUN_ID"

            # Copy results to report directory
            cp -r "$TGP_BENCH_DATA_DIR/$scenario/$RUN_ID/statistics.json" "$report_dir/"
            cp -r "$TGP_BENCH_DATA_DIR/$scenario/$RUN_ID/summary.csv" "$report_dir/"
            cp -r "$TGP_BENCH_DATA_DIR/$scenario/$RUN_ID/summary.txt" "$report_dir/${scenario}_summary.txt"
            cp -r "$TGP_BENCH_DATA_DIR/$scenario/$RUN_ID/plots/" "$report_dir/${scenario}_plots/"
        fi
    done

    # Generate comparison report
    echo "Generating comparison report..."
    python3 "$SCRIPT_DIR/compare.py" "$RUN_ID" > "$report_dir/comparison.txt"

    # Generate HTML dashboard
    echo "Generating HTML dashboard..."
    python3 "$SCRIPT_DIR/generate_dashboard.py" "$RUN_ID" > "$report_dir/dashboard.html"

    echo "Report generated at: $report_dir"
}

# Main execution
main() {
    # Run all benchmarks
    run_localhost
    run_lan
    run_perth

    # Generate comprehensive report
    generate_report

    echo
    echo "=========================================="
    echo "Benchmark Suite Complete!"
    echo "=========================================="
    echo "Run ID: $RUN_ID"
    echo "Results: $TGP_BENCH_RESULTS_DIR/$RUN_ID"
    echo "=========================================="
}

# Run main function
main
