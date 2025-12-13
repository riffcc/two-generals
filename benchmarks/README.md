# TGP-Piper Benchmarking Infrastructure

## 📊 Overview

This directory contains comprehensive benchmarking infrastructure for TGP-Piper, designed to measure performance across different network scenarios:

- **Localhost** - Baseline performance on the same machine
- **LAN** - Local area network performance (low latency, high bandwidth)
- **Perth** - Intercontinental performance (high latency, potential packet loss)

## 📁 Directory Structure

```
benchmarks/
├── scripts/              # Benchmark execution scripts
│   ├── localhost.sh      # Localhost benchmark script
│   ├── lan.sh            # LAN benchmark script
│   ├── perth.sh          # Perth benchmark script
│   ├── collect.sh        # Data collection automation
│   └── analyze.py        # Data analysis script
├── data/                # Raw benchmark data storage
│   ├── localhost/        # Localhost results
│   ├── lan/              # LAN results
��   └── perth/            # Perth results
├── results/             # Processed results and reports
│   ├── summary.csv       # Aggregated results
│   └── comparison.md     # Performance comparison
├── visualization/       # Visualization outputs
│   ├── plots/            # Generated plots
│   └── dashboard.html    # Interactive dashboard
└── README.md             # This file
```

## 🚀 Quick Start

### 1. Run Localhost Benchmark

```bash
cd /mnt/castle/garage/two-generals-public/benchmarks
./scripts/localhost.sh
```

### 2. Run LAN Benchmark

```bash
./scripts/lan.sh <remote_host>
```

### 3. Run Perth Benchmark

```bash
./scripts/perth.sh
```

### 4. Generate Visualizations

```bash
python3 scripts/analyze.py
python3 scripts/visualize.py
```

## 📈 Benchmark Metrics

Each benchmark collects the following metrics:

### Connection Metrics
- **Connection Time** - Time to establish TGP coordination
- **Handshake Rounds** - Number of proof exchanges required
- **Bilateral Receipt Time** - Time to achieve bilateral receipt

### Transfer Metrics
- **Throughput** - MB/s transfer rate
- **Latency** - End-to-end transfer time
- **CPU Usage** - System CPU utilization
- **Memory Usage** - Memory footprint
- **Packet Loss Rate** - Network loss percentage
- **Retry Count** - Number of retransmissions

### Adaptive Flood Metrics
- **Min Rate** - Minimum packets per second
- **Max Rate** - Maximum packets per second
- **Average Rate** - Average packets per second
- **Rate Adjustments** - Number of rate changes

## 🔧 Configuration

### Environment Variables

Configure benchmarks using environment variables:

```bash
export TGP_BENCH_FILE_SIZE="1G"      # Test file size (1G, 100M, 10M)
export TGP_BENCH_RUNS="5"            # Number of runs per test
export TGP_BENCH_PORT="8000"         # Port to use
export TGP_BENCH_PERTH_HOST="barbara.per.riff.cc"  # Perth server
```

### Benchmark Parameters

Edit `scripts/config.sh` to customize:

- File sizes for different tests
- Number of warmup runs
- Number of measurement runs
- Timeout values
- Verbosity levels

## 📊 Benchmark Scenarios

### 1. Localhost Benchmark

**Purpose**: Establish baseline performance with minimal network interference

**Configuration**:
- File size: 1GB
- Runs: 5 iterations
- No artificial latency/loss

**Expected Results**:
- Connection time: < 1ms
- Throughput: 900-1100 MB/s
- Packet loss: 0%

### 2. LAN Benchmark

**Purpose**: Measure performance on local network with real-world conditions

**Configuration**:
- File size: 1GB
- Runs: 5 iterations
- Optional artificial latency: 1-5ms
- Optional packet loss: 0-1%

**Expected Results**:
- Connection time: 0.5-2ms
- Throughput: 500-900 MB/s
- Packet loss: < 1%

### 3. Perth Benchmark

**Purpose**: Test intercontinental performance with high latency

**Configuration**:
- File size: 100MB (smaller due to latency)
- Runs: 3 iterations
- Expected latency: 100-300ms
- Expected packet loss: 0-5%

**Expected Results**:
- Connection time: 10-20ms
- Throughput: 40-80 MB/s
- Packet loss: 0-5%

## 📈 Data Collection

### Raw Data Format

Each benchmark run generates a JSON file with complete telemetry:

```json
{
  "timestamp": "2025-12-11T12:00:00Z",
  "scenario": "localhost",
  "run": 1,
  "file_size": "1G",
  "connection": {
    "time_ms": 0.45,
    "handshake_rounds": 4,
    "bilateral_receipt_time_ms": 0.38
  },
  "transfer": {
    "duration_ms": 950,
    "throughput_mbps": 1080,
    "cpu_usage_percent": 45,
    "memory_usage_mb": 120,
    "packet_loss_percent": 0,
    "retry_count": 0
  },
  "flood": {
    "min_rate_pps": 10,
    "max_rate_pps": 100000,
    "avg_rate_pps": 45000,
    "rate_adjustments": 12
  }
}
```

### Data Processing

The `analyze.py` script processes raw data to generate:

- **Aggregated CSV** - All runs in tabular format
- **Statistics** - Mean, median, stddev for each metric
- **Comparison Report** - TGP-Piper vs PipePiper baseline
- **Trend Analysis** - Performance across different scenarios

## 📊 Visualization

### Plot Types

1. **Throughput Comparison** - Bar chart comparing scenarios
2. **Connection Time** - Line chart showing improvement
3. **Latency vs Throughput** - Scatter plot
4. **Adaptive Rate** - Time series of rate adjustments
5. **Packet Loss Tolerance** - Box plot of performance at different loss rates

### Generate Visualizations

```bash
python3 scripts/visualize.py
```

Outputs are saved to `visualization/plots/` as PNG and SVG files.

## 🔄 Comparison with PipePiper

The benchmarking infrastructure includes baseline comparison with PipePiper:

```bash
# Run PipePiper baseline
./scripts/baseline-piper.sh

# Compare results
python3 scripts/compare.py
```

This generates a comparison report showing:
- Speedup factors
- Efficiency improvements
- Loss tolerance gains

## 🛠️ Requirements

### Software Dependencies

- Python 3.8+
- Rust (for TGP-Piper binary)
- PipePiper (for baseline comparison)
- GNU Plotutils or matplotlib
- jq (for JSON processing)
- bc (for calculations)

### Install Dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip jq bc plotutils
pip3 install matplotlib pandas numpy
```

## 📝 Usage Examples

### Full Benchmark Suite

```bash
# Run all benchmarks
./scripts/run-all.sh

# Generate all reports
./scripts/generate-reports.sh

# Open visualization dashboard
python3 -m http.server 8000 --directory visualization
```

### Custom Benchmark

```bash
# Run custom benchmark with specific parameters
TGP_BENCH_FILE_SIZE="500M" TGP_BENCH_RUNS="3" \
  ./scripts/localhost.sh custom-run
```

## 📊 Expected Performance Gains

Based on TGP_PIPER_DESIGN.md:

| Metric | PipePiper | TGP-Piper | Improvement |
|--------|-----------|-----------|-------------|
| Connection Time | 50-100ms | 10-20ms | 5-10× faster |
| Throughput (local) | 800 MB/s | 900-1100 MB/s | 10-30% better |
| Throughput (Perth) | 20-50 MB/s | 40-80 MB/s | 2× better |
| Packet Loss Tolerance | 10% max | 70%+ | Revolutionary |
| CPU Efficiency | Moderate | Low | Better |

## 🔬 Advanced Features

### Network Simulation

Simulate various network conditions:

```bash
# Add latency and packet loss using tc
./scripts/setup-network-simulation.sh --latency=50ms --loss=2%

# Run benchmark with simulated conditions
./scripts/localhost.sh simulated-50ms-2loss

# Clean up
./scripts/cleanup-network-simulation.sh
```

### Continuous Benchmarking

Set up cron jobs for regular performance monitoring:

```bash
# Edit crontab
crontab -e

# Add daily benchmark
0 3 * * * cd /mnt/castle/garage/two-generals-public/benchmarks && ./scripts/localhost.sh daily-$(date +\%Y-\%m-\%d) > /dev/null 2>&1
```

## 📈 Performance Regression Testing

Track performance over time:

```bash
# Compare current vs previous runs
python3 scripts/regression.py --baseline 2025-12-01 --current 2025-12-11

# Alert on significant regressions
./scripts/alert-on-regression.sh --threshold 10%
```

## 📚 Documentation

- [TGP_PIPER_DESIGN.md](../TGP_PIPER_DESIGN.md) - Architecture design
- [ADAPTIVE_TGP_DESIGN.md](../ADAPTIVE_TGP_DESIGN.md) - Adaptive flooding details
- [paper/](../paper/) - Formal verification and research papers

## 🛡️ Safety Notes

1. **Disk Space**: Benchmarks generate large test files (1GB+). Ensure sufficient disk space.
2. **Network Bandwidth**: LAN benchmarks consume significant bandwidth. Run during off-peak hours.
3. **CPU Load**: Benchmarks max out CPU cores. Monitor system temperature.
4. **Data Retention**: Raw data is preserved. Clean up periodically with `./scripts/cleanup.sh`.

## 🎯 Future Enhancements

- Real-time monitoring dashboard
- Automated regression detection
- Integration with CI/CD pipeline
- Cross-platform testing (Windows, macOS)
- Containerized benchmark environment

---

**Maintainer**: Claude Code Benchmarking System
**Last Updated**: 2025-12-11
**License**: MIT
