# TGP-Piper Benchmarking - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Install Dependencies

```bash
cd /mnt/castle/garage/two-generals-public/benchmarks
sudo ./setup.sh
```

### 2. Build TGP-Piper (when ready)

```bash
cd /mnt/castle/garage/two-generals-public/rust
cargo build --release
```

### 3. Run Benchmarks

#### Localhost Benchmark
```bash
cd /mnt/castle/garage/two-generals-public/benchmarks
./scripts/localhost.sh
```

#### LAN Benchmark
```bash
./scripts/lan.sh <remote_host>
```

#### Perth Benchmark
```bash
./scripts/perth.sh
```

#### All Benchmarks
```bash
./scripts/run-all.sh
```

### 4. Analyze Results

```bash
# Analyze specific run
python3 scripts/analyze.py data/<scenario>/<run_id>

# Generate visualizations
python3 scripts/visualize.py data/<scenario>/<run_id>

# Compare with baseline
python3 scripts/compare.py <run_id>
```

### 5. View Dashboard

```bash
# Open the generated HTML dashboard
firefox results/<run_id>/dashboard.html
```

## 📊 Example Workflow

```bash
# 1. Run localhost benchmark
./scripts/localhost.sh quick-test

# 2. Analyze results
python3 scripts/analyze.py data/localhost/quick-test

# 3. Generate visualizations
python3 scripts/visualize.py data/localhost/quick-test

# 4. View results
cat data/localhost/quick-test/summary.txt
```

## 🎯 Key Files

- **README.md** - Complete documentation
- **scripts/config.sh** - Configuration settings
- **scripts/localhost.sh** - Localhost benchmark
- **scripts/lan.sh** - LAN benchmark
- **scripts/perth.sh** - Intercontinental benchmark
- **scripts/analyze.py** - Data analysis
- **scripts/visualize.py** - Visualization generation
- **baseline/piper_baseline.json** - PipePiper baseline data

## 📈 Expected Results

| Metric | PipePiper | TGP-Piper | Improvement |
|--------|-----------|-----------|-------------|
| Connection Time | 50-100ms | 10-20ms | **5-10× faster** |
| Throughput (local) | 800 MB/s | 900-1100 MB/s | **10-30% better** |
| Throughput (Perth) | 20-50 MB/s | 40-80 MB/s | **2× better** |
| Packet Loss Tolerance | 10% max | 70%+ | **Revolutionary** |

## 🛠️ Customization

Edit `scripts/config.sh` or use environment variables:

```bash
# Custom file size
export TGP_BENCH_FILE_SIZE="500M"

# Custom runs
export TGP_BENCH_RUNS=3

# Run benchmark
./scripts/localhost.sh custom-run
```

## 📚 Documentation

- [Full README](README.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [TGP-Piper Design](../../TGP_PIPER_DESIGN.md)

---

**Need help?** Check the full documentation or run:
```bash
./test-infrastructure.sh
```

To verify your setup.
