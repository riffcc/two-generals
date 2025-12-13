#!/bin/bash

# TGP-Piper Benchmark Infrastructure Test
# Validates that all components are working correctly

set -euo pipefail

SCRIPT_DIR="/mnt/castle/garage/two-generals-public/benchmarks/scripts"
BASE_DIR="/mnt/castle/garage/two-generals-public/benchmarks"

echo "=========================================="
echo "TGP-Piper Benchmark Infrastructure Test"
echo "=========================================="
echo

# Test 1: Configuration loading
echo "Test 1: Configuration loading..."
bash -c "source \"$SCRIPT_DIR/config.sh\" 2>/dev/null" && echo "✓ Configuration loads successfully"
echo

# Test 2: Python scripts syntax
echo "Test 2: Python scripts syntax..."
python3 -m py_compile "$SCRIPT_DIR/analyze.py" 2>/dev/null && echo "✓ analyze.py syntax OK"
python3 -m py_compile "$SCRIPT_DIR/visualize.py" 2>/dev/null && echo "✓ visualize.py syntax OK"
python3 -m py_compile "$SCRIPT_DIR/compare.py" 2>/dev/null && echo "✓ compare.py syntax OK"
python3 -m py_compile "$SCRIPT_DIR/generate_dashboard.py" 2>/dev/null && echo "✓ generate_dashboard.py syntax OK"
echo

# Test 3: Shell scripts syntax
echo "Test 3: Shell scripts syntax..."
bash -n "$SCRIPT_DIR/localhost.sh" 2>/dev/null && echo "✓ localhost.sh syntax OK"
bash -n "$SCRIPT_DIR/lan.sh" 2>/dev/null && echo "✓ lan.sh syntax OK"
bash -n "$SCRIPT_DIR/perth.sh" 2>/dev/null && echo "✓ perth.sh syntax OK"
bash -n "$SCRIPT_DIR/run-all.sh" 2>/dev/null && echo "✓ run-all.sh syntax OK"
bash -n "$SCRIPT_DIR/setup.sh" 2>/dev/null && echo "✓ setup.sh syntax OK"
echo

# Test 4: Directory structure
echo "Test 4: Directory structure..."
if [ -d "$BASE_DIR/data" ]; then
    echo "✓ data/ directory exists"
else
    echo "✗ data/ directory missing"
    exit 1
fi

if [ -d "$BASE_DIR/results" ]; then
    echo "✓ results/ directory exists"
else
    echo "✗ results/ directory missing"
    exit 1
fi

if [ -d "$BASE_DIR/visualization" ]; then
    echo "✓ visualization/ directory exists"
else
    echo "✗ visualization/ directory missing"
    exit 1
fi

if [ -d "$BASE_DIR/baseline" ]; then
    echo "✓ baseline/ directory exists"
else
    echo "✗ baseline/ directory missing"
    exit 1
fi
echo

# Test 5: Baseline data
echo "Test 5: Baseline data..."
if [ -f "$BASE_DIR/baseline/piper_baseline.json" ]; then
    echo "✓ Baseline JSON file exists"
    if python3 -c "import json; json.load(open('$BASE_DIR/baseline/piper_baseline.json'))" 2>/dev/null; then
        echo "✓ Baseline JSON is valid"
    else
        echo "✗ Baseline JSON is invalid"
        exit 1
    fi
else
    echo "✗ Baseline JSON file missing"
    exit 1
fi
echo

# Test 6: Python dependencies check
echo "Test 6: Python dependencies..."
if python3 -c "import matplotlib; import pandas; import numpy" 2>/dev/null; then
    echo "✓ All Python dependencies available"
else
    echo "⚠ Some Python dependencies may be missing"
    echo "  Run: pip3 install -r $SCRIPT_DIR/../requirements.txt"
fi
echo

# Test 7: Example output validation
echo "Test 7: Example output validation..."
if [ -f "$SCRIPT_DIR/example_output.json" ]; then
    echo "✓ Example output file exists"
    if python3 -c "import json; json.load(open('$SCRIPT_DIR/example_output.json'))" 2>/dev/null; then
        echo "✓ Example output JSON is valid"
    else
        echo "✗ Example output JSON is invalid"
        exit 1
    fi
else
    echo "✗ Example output file missing"
    exit 1
fi
echo

# Test 8: Documentation
echo "Test 8: Documentation..."
if [ -f "$BASE_DIR/README.md" ]; then
    echo "✓ README.md exists"
else
    echo "✗ README.md missing"
    exit 1
fi

if [ -f "$BASE_DIR/IMPLEMENTATION_SUMMARY.md" ]; then
    echo "✓ IMPLEMENTATION_SUMMARY.md exists"
else
    echo "✗ IMPLEMENTATION_SUMMARY.md missing"
    exit 1
fi
echo

# Test 9: Requirements file
echo "Test 9: Requirements file..."
if [ -f "$BASE_DIR/requirements.txt" ]; then
    echo "✓ requirements.txt exists"
else
    echo "✗ requirements.txt missing"
    exit 1
fi
echo

# Test 10: Script executability
echo "Test 10: Script executability..."
for script in localhost.sh lan.sh perth.sh run-all.sh; do
    if [ -x "$SCRIPT_DIR/$script" ]; then
        echo "✓ $script is executable"
    else
        echo "✗ $script is not executable"
        exit 1
    fi
done

# Check setup.sh in base directory
if [ -x "$BASE_DIR/setup.sh" ]; then
    echo "✓ setup.sh is executable"
else
    echo "✗ setup.sh is not executable"
    exit 1
fi
echo

echo "=========================================="
echo "All Tests Passed! ✓"
echo "=========================================="
echo
echo "Benchmarking infrastructure is ready to use."
echo
echo "Next steps:"
echo "  1. Build TGP-Piper: cd ../../rust && cargo build --release"
echo "  2. Run benchmarks: ./scripts/run-all.sh"
echo "  3. Analyze results: python3 scripts/analyze.py data/<scenario>/<run_id>"
echo "  4. Generate visualizations: python3 scripts/visualize.py data/<scenario>/<run_id>"
echo "  5. Compare with baseline: python3 scripts/compare.py <run_id>"
echo
echo "=========================================="
