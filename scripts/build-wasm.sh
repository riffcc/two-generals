#!/usr/bin/env bash
# Build WASM module for TGP web visualizer
# Usage: ./scripts/build-wasm.sh [--release]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WASM_DIR="$PROJECT_ROOT/wasm"
WEB_DIR="$PROJECT_ROOT/web"
OUT_DIR="$WEB_DIR/pkg"

# Check for wasm-pack
if ! command -v wasm-pack &> /dev/null; then
    echo "Error: wasm-pack not found. Install with: cargo install wasm-pack"
    exit 1
fi

# Parse arguments
BUILD_MODE="--dev"
if [[ "${1:-}" == "--release" ]]; then
    BUILD_MODE="--release"
    echo "Building in release mode..."
else
    echo "Building in development mode..."
fi

# Build WASM module
echo "Building WASM module..."
cd "$WASM_DIR"
wasm-pack build --target web --out-dir "$OUT_DIR" $BUILD_MODE

echo ""
echo "WASM build complete!"
echo "Output: $OUT_DIR"
echo ""
echo "Files created:"
ls -la "$OUT_DIR"/*.{js,wasm} 2>/dev/null || echo "  (no output files)"
echo ""
echo "To use in web visualizer:"
echo "  cd $WEB_DIR && npm run dev"
