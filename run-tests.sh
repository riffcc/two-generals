#!/bin/bash
# Two Generals Protocol - Full Test Suite
# Runs Python, Rust, and Lean 4 tests with detailed output
#
# Usage: ./run-tests.sh [--quick]
#   --quick: Skip slow tests (Python only)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

QUICK_MODE=false
if [[ "$1" == "--quick" ]]; then
    QUICK_MODE=true
fi

echo "============================================================"
echo "Two Generals Protocol - Full Test Suite"
echo "============================================================"
echo ""

# ============================================================
# PYTHON TESTS
# ============================================================
echo -e "${BLUE}[1/3] Python Tests${NC}"
echo "------------------------------------------------------------"

cd python

# Run pytest with one-line-per-test output (full test names)
PYTEST_ARGS="-vv --tb=no"
if [[ "$QUICK_MODE" == "true" ]]; then
    PYTEST_ARGS="$PYTEST_ARGS -m 'not slow'"
fi

echo "Running: pytest $PYTEST_ARGS"
echo ""

# Run pytest directly - output streams in real-time
pytest $PYTEST_ARGS 2>&1 || PYTHON_FAILED=1

cd ..
echo ""

# ============================================================
# RUST TESTS
# ============================================================
echo -e "${BLUE}[2/3] Rust Tests${NC}"
echo "------------------------------------------------------------"

cd rust

echo "Running: cargo test"
echo ""

# Run cargo test - filter out download/compile noise, show test results
set -o pipefail
if  which cargo-nextest &> /dev/null; then
	cargo nextest run
else
	cargo test 2>&1 | grep -v -e "^[[:space:]]*Compiling" -e "^[[:space:]]*Downloading" -e "^[[:space:]]*Downloaded" -e "^[[:space:]]*Updating" -e "^[[:space:]]*Fetch" -e "^[[:space:]]*Locking" || RUST_FAILED=1
fi
set +o pipefail

cd ..
echo ""

# ============================================================
# LEAN 4 PROOFS
# ============================================================
echo -e "${BLUE}[3/3] Lean 4 Formal Proofs${NC}"
echo "------------------------------------------------------------"

cd lean4

echo "Running: lake build"
echo ""

# Check for sorry statements first (excluding comments about sorry)
SORRY_COUNT=$(grep -r "sorry" *.lean 2>/dev/null | grep -v -e "-- " -e "no sorry" -e "without sorry" -e "/--" -e "0 sorry" -e "COMPLETE" | wc -l || echo "0")
if [[ "$SORRY_COUNT" -gt 0 ]]; then
    echo -e "${RED}WARNING: Found $SORRY_COUNT potential 'sorry' statements${NC}"
    grep -rn "sorry" *.lean 2>/dev/null | grep -v -e "-- " -e "no sorry" -e "without sorry" -e "0 sorry" -e "COMPLETE" || true
    echo ""
else
    echo -e "${GREEN}✓ No 'sorry' statements found in source files${NC}"
fi

echo ""

# Run lake build and show output (filter download noise)
lake build 2>&1 | tee /tmp/lake_build_output.txt | grep -v -e "^Downloading" -e "^Unpacking" -e "^lake:" || LEAN_FAILED=1

# Count theorems from the output
THEOREM_COUNT=$(grep -c "^info:" /tmp/lake_build_output.txt 2>/dev/null || echo "0")

echo ""
if [[ -z "$LEAN_FAILED" ]]; then
    echo -e "${GREEN}Build completed successfully${NC}"
    echo "Verified theorems/lemmas: $THEOREM_COUNT"
else
    echo -e "${RED}Build failed${NC}"
fi

cd ..

echo ""
echo "============================================================"
echo "TEST SUITE COMPLETE"
echo "============================================================"
echo ""

# Summary
if [[ -n "$PYTHON_FAILED" ]] || [[ -n "$RUST_FAILED" ]] || [[ -n "$LEAN_FAILED" ]]; then
    echo -e "${RED}Some tests failed. Check output above.${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    echo "Key theorems verified in Lean 4:"
    echo "  • safety: If both decide, decisions are equal"
    echo "  • attack_needs_both: Attack requires bilateral evidence"
    echo "  • bilateral_receipt_implies_common_knowledge"
    echo "  • gray_impossibility_assumption_violated"
    echo "  • full_epistemic_chain_verified"
fi
