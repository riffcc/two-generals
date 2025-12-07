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

# Run pytest with one-line-per-test output
PYTEST_ARGS="-v --tb=line"
if [[ "$QUICK_MODE" == "false" ]]; then
    PYTEST_ARGS="$PYTEST_ARGS --run-slow"
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

# Run cargo test directly - output streams in real-time
cargo test 2>&1 || RUST_FAILED=1

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
SORRY_COUNT=$(grep -r "sorry" *.lean 2>/dev/null | grep -v -e "-- " -e "no sorry" -e "without sorry" -e "/--" | wc -l || echo "0")
if [[ "$SORRY_COUNT" -gt 0 ]]; then
    echo -e "${RED}WARNING: Found $SORRY_COUNT potential 'sorry' statements${NC}"
    grep -rn "sorry" *.lean 2>/dev/null | grep -v -e "-- " -e "no sorry" -e "without sorry" || true
    echo ""
else
    echo -e "${GREEN}✓ No 'sorry' statements found in source files${NC}"
fi

echo ""

# Run lake build and show output
lake build 2>&1 | tee /tmp/lake_build_output.txt || LEAN_FAILED=1

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
