#!/usr/bin/env python3

"""
TGP-Piper Benchmark Data Analysis
Analyzes JSON output from benchmark runs and generates reports
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from statistics import mean, median, stdev
from typing import Dict, List, Any

class BenchmarkAnalyzer:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.runs = []
        self.scenario = self._detect_scenario()

    def _detect_scenario(self) -> str:
        """Detect benchmark scenario from directory path"""
        parts = str(self.data_dir).split('/')
        for part in parts:
            if part in ['localhost', 'lan', 'perth']:
                return part
        return 'unknown'

    def load_all_runs(self) -> None:
        """Load all JSON run files from data directory"""
        self.runs = []

        for file in sorted(self.data_dir.glob('run_*.json')):
            if file.name.startswith('run_warmup_'):
                continue  # Skip warmup runs

            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    self.runs.append(data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load {file}: {e}")

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate statistics across all runs"""
        if not self.runs:
            return {}

        stats = {
            'scenario': self.scenario,
            'total_runs': len(self.runs),
            'timestamp': datetime.now().isoformat(),
            'connection': {},
            'transfer': {},
            'flood': {}
        }

        # Connection metrics
        conn_times = [r['connection']['time_ms'] for r in self.runs]
        handshake_rounds = [r['connection']['handshake_rounds'] for r in self.runs]
        bilateral_times = [r['connection']['bilateral_receipt_time_ms'] for r in self.runs]

        stats['connection'] = {
            'time_ms': {
                'mean': mean(conn_times),
                'median': median(conn_times),
                'stdev': stdev(conn_times) if len(conn_times) > 1 else 0,
                'min': min(conn_times),
                'max': max(conn_times)
            },
            'handshake_rounds': {
                'mean': mean(handshake_rounds),
                'median': median(handshake_rounds),
                'stdev': stdev(handshake_rounds) if len(handshake_rounds) > 1 else 0,
                'min': min(handshake_rounds),
                'max': max(handshake_rounds)
            },
            'bilateral_receipt_time_ms': {
                'mean': mean(bilateral_times),
                'median': median(bilateral_times),
                'stdev': stdev(bilateral_times) if len(bilateral_times) > 1 else 0,
                'min': min(bilateral_times),
                'max': max(bilateral_times)
            }
        }

        # Transfer metrics
        durations = [r['transfer']['duration_ms'] for r in self.runs]
        throughputs = [r['transfer']['throughput_mbps'] for r in self.runs]
        cpu_usages = [r['transfer']['cpu_usage_percent'] for r in self.runs]
        memory_usages = [r['transfer']['memory_usage_mb'] for r in self.runs]
        packet_losses = [r['transfer']['packet_loss_percent'] for r in self.runs]
        retries = [r['transfer']['retry_count'] for r in self.runs]

        stats['transfer'] = {
            'duration_ms': {
                'mean': mean(durations),
                'median': median(durations),
                'stdev': stdev(durations) if len(durations) > 1 else 0,
                'min': min(durations),
                'max': max(durations)
            },
            'throughput_mbps': {
                'mean': mean(throughputs),
                'median': median(throughputs),
                'stdev': stdev(throughputs) if len(throughputs) > 1 else 0,
                'min': min(throughputs),
                'max': max(throughputs)
            },
            'cpu_usage_percent': {
                'mean': mean(cpu_usages),
                'median': median(cpu_usages),
                'stdev': stdev(cpu_usages) if len(cpu_usages) > 1 else 0,
                'min': min(cpu_usages),
                'max': max(cpu_usages)
            },
            'memory_usage_mb': {
                'mean': mean(memory_usages),
                'median': median(memory_usages),
                'stdev': stdev(memory_usages) if len(memory_usages) > 1 else 0,
                'min': min(memory_usages),
                'max': max(memory_usages)
            },
            'packet_loss_percent': {
                'mean': mean(packet_losses),
                'median': median(packet_losses),
                'stdev': stdev(packet_losses) if len(packet_losses) > 1 else 0,
                'min': min(packet_losses),
                'max': max(packet_losses)
            },
            'retry_count': {
                'mean': mean(retries),
                'median': median(retries),
                'stdev': stdev(retries) if len(retries) > 1 else 0,
                'min': min(retries),
                'max': max(retries)
            }
        }

        # Flood metrics
        min_rates = [r['flood']['min_rate_pps'] for r in self.runs]
        max_rates = [r['flood']['max_rate_pps'] for r in self.runs]
        avg_rates = [r['flood']['avg_rate_pps'] for r in self.runs]
        rate_adjustments = [r['flood']['rate_adjustments'] for r in self.runs]

        stats['flood'] = {
            'min_rate_pps': {
                'mean': mean(min_rates),
                'median': median(min_rates),
                'stdev': stdev(min_rates) if len(min_rates) > 1 else 0,
                'min': min(min_rates),
                'max': max(min_rates)
            },
            'max_rate_pps': {
                'mean': mean(max_rates),
                'median': median(max_rates),
                'stdev': stdev(max_rates) if len(max_rates) > 1 else 0,
                'min': min(max_rates),
                'max': max(max_rates)
            },
            'avg_rate_pps': {
                'mean': mean(avg_rates),
                'median': median(avg_rates),
                'stdev': stdev(avg_rates) if len(avg_rates) > 1 else 0,
                'min': min(avg_rates),
                'max': max(avg_rates)
            },
            'rate_adjustments': {
                'mean': mean(rate_adjustments),
                'median': median(rate_adjustments),
                'stdev': stdev(rate_adjustments) if len(rate_adjustments) > 1 else 0,
                'min': min(rate_adjustments),
                'max': max(rate_adjustments)
            }
        }

        return stats

    def generate_summary_text(self, stats: Dict[str, Any]) -> str:
        """Generate human-readable summary"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"TGP-Piper Benchmark Summary - {self.scenario.upper()}")
        lines.append("=" * 80)
        lines.append(f"Scenario: {stats['scenario']}")
        lines.append(f"Total Runs: {stats['total_runs']}")
        lines.append(f"Timestamp: {stats['timestamp']}")
        lines.append("")

        # Connection metrics
        lines.append("CONNECTION METRICS:")
        lines.append("-" * 80)
        conn = stats['connection']
        lines.append(f"  Connection Time (ms):")
        lines.append(f"    Mean: {conn['time_ms']['mean']:.2f} ± {conn['time_ms']['stdev']:.2f}")
        lines.append(f"    Median: {conn['time_ms']['median']:.2f} (Min: {conn['time_ms']['min']:.2f}, Max: {conn['time_ms']['max']:.2f})")
        lines.append(f"  Handshake Rounds:")
        lines.append(f"    Mean: {conn['handshake_rounds']['mean']:.1f} ± {conn['handshake_rounds']['stdev']:.1f}")
        lines.append(f"    Median: {conn['handshake_rounds']['median']:.1f}")
        lines.append(f"  Bilateral Receipt Time (ms):")
        lines.append(f"    Mean: {conn['bilateral_receipt_time_ms']['mean']:.2f} ± {conn['bilateral_receipt_time_ms']['stdev']:.2f}")
        lines.append(f"    Median: {conn['bilateral_receipt_time_ms']['median']:.2f}")
        lines.append("")

        # Transfer metrics
        lines.append("TRANSFER METRICS:")
        lines.append("-" * 80)
        xfer = stats['transfer']
        lines.append(f"  Duration (ms):")
        lines.append(f"    Mean: {xfer['duration_ms']['mean']:.2f} ± {xfer['duration_ms']['stdev']:.2f}")
        lines.append(f"    Median: {xfer['duration_ms']['median']:.2f}")
        lines.append(f"  Throughput (MB/s):")
        lines.append(f"    Mean: {xfer['throughput_mbps']['mean']:.2f} ± {xfer['throughput_mbps']['stdev']:.2f}")
        lines.append(f"    Median: {xfer['throughput_mbps']['median']:.2f} (Min: {xfer['throughput_mbps']['min']:.2f}, Max: {xfer['throughput_mbps']['max']:.2f})")
        lines.append(f"  CPU Usage (%):")
        lines.append(f"    Mean: {xfer['cpu_usage_percent']['mean']:.1f} ± {xfer['cpu_usage_percent']['stdev']:.1f}")
        lines.append(f"    Median: {xfer['cpu_usage_percent']['median']:.1f}")
        lines.append(f"  Memory Usage (MB):")
        lines.append(f"    Mean: {xfer['memory_usage_mb']['mean']:.1f} ± {xfer['memory_usage_mb']['stdev']:.1f}")
        lines.append(f"    Median: {xfer['memory_usage_mb']['median']:.1f}")
        lines.append(f"  Packet Loss (%):")
        lines.append(f"    Mean: {xfer['packet_loss_percent']['mean']:.2f} ± {xfer['packet_loss_percent']['stdev']:.2f}")
        lines.append(f"    Median: {xfer['packet_loss_percent']['median']:.2f}")
        lines.append(f"  Retry Count:")
        lines.append(f"    Mean: {xfer['retry_count']['mean']:.1f} ± {xfer['retry_count']['stdev']:.1f}")
        lines.append(f"    Median: {xfer['retry_count']['median']:.1f}")
        lines.append("")

        # Flood metrics
        lines.append("ADAPTIVE FLOOD METRICS:")
        lines.append("-" * 80)
        flood = stats['flood']
        lines.append(f"  Min Rate (packets/sec):")
        lines.append(f"    Mean: {flood['min_rate_pps']['mean']:.0f}")
        lines.append(f"  Max Rate (packets/sec):")
        lines.append(f"    Mean: {flood['max_rate_pps']['mean']:.0f}")
        lines.append(f"  Avg Rate (packets/sec):")
        lines.append(f"    Mean: {flood['avg_rate_pps']['mean']:.0f} ± {flood['avg_rate_pps']['stdev']:.0f}")
        lines.append(f"    Median: {flood['avg_rate_pps']['median']:.0f}")
        lines.append(f"  Rate Adjustments:")
        lines.append(f"    Mean: {flood['rate_adjustments']['mean']:.1f} ± {flood['rate_adjustments']['stdev']:.1f}")
        lines.append(f"    Median: {flood['rate_adjustments']['median']:.1f}")
        lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    def save_statistics(self, stats: Dict[str, Any], output_file: str) -> None:
        """Save statistics to JSON file"""
        with open(output_file, 'w') as f:
            json.dump(stats, f, indent=2)

    def generate_csv(self, stats: Dict[str, Any], output_file: str) -> None:
        """Generate CSV summary"""
        import csv

        # Flatten stats for CSV
        rows = []

        # Add connection metrics
        conn = stats['connection']
        rows.append(['Category', 'Metric', 'Mean', 'Median', 'StdDev', 'Min', 'Max'])
        rows.append(['Connection', 'Time (ms)',
                     conn['time_ms']['mean'],
                     conn['time_ms']['median'],
                     conn['time_ms']['stdev'],
                     conn['time_ms']['min'],
                     conn['time_ms']['max']])
        rows.append(['Connection', 'Handshake Rounds',
                     conn['handshake_rounds']['mean'],
                     conn['handshake_rounds']['median'],
                     conn['handshake_rounds']['stdev'],
                     conn['handshake_rounds']['min'],
                     conn['handshake_rounds']['max']])
        rows.append(['Connection', 'Bilateral Time (ms)',
                     conn['bilateral_receipt_time_ms']['mean'],
                     conn['bilateral_receipt_time_ms']['median'],
                     conn['bilateral_receipt_time_ms']['stdev'],
                     conn['bilateral_receipt_time_ms']['min'],
                     conn['bilateral_receipt_time_ms']['max']])

        # Add transfer metrics
        xfer = stats['transfer']
        rows.append(['Transfer', 'Duration (ms)',
                     xfer['duration_ms']['mean'],
                     xfer['duration_ms']['median'],
                     xfer['duration_ms']['stdev'],
                     xfer['duration_ms']['min'],
                     xfer['duration_ms']['max']])
        rows.append(['Transfer', 'Throughput (MB/s)',
                     xfer['throughput_mbps']['mean'],
                     xfer['throughput_mbps']['median'],
                     xfer['throughput_mbps']['stdev'],
                     xfer['throughput_mbps']['min'],
                     xfer['throughput_mbps']['max']])
        rows.append(['Transfer', 'CPU Usage (%)',
                     xfer['cpu_usage_percent']['mean'],
                     xfer['cpu_usage_percent']['median'],
                     xfer['cpu_usage_percent']['stdev'],
                     xfer['cpu_usage_percent']['min'],
                     xfer['cpu_usage_percent']['max']])
        rows.append(['Transfer', 'Memory (MB)',
                     xfer['memory_usage_mb']['mean'],
                     xfer['memory_usage_mb']['median'],
                     xfer['memory_usage_mb']['stdev'],
                     xfer['memory_usage_mb']['min'],
                     xfer['memory_usage_mb']['max']])
        rows.append(['Transfer', 'Packet Loss (%)',
                     xfer['packet_loss_percent']['mean'],
                     xfer['packet_loss_percent']['median'],
                     xfer['packet_loss_percent']['stdev'],
                     xfer['packet_loss_percent']['min'],
                     xfer['packet_loss_percent']['max']])
        rows.append(['Transfer', 'Retries',
                     xfer['retry_count']['mean'],
                     xfer['retry_count']['median'],
                     xfer['retry_count']['stdev'],
                     xfer['retry_count']['min'],
                     xfer['retry_count']['max']])

        # Add flood metrics
        flood = stats['flood']
        rows.append(['Flood', 'Min Rate (pps)',
                     flood['min_rate_pps']['mean'],
                     flood['min_rate_pps']['median'],
                     flood['min_rate_pps']['stdev'],
                     flood['min_rate_pps']['min'],
                     flood['min_rate_pps']['max']])
        rows.append(['Flood', 'Max Rate (pps)',
                     flood['max_rate_pps']['mean'],
                     flood['max_rate_pps']['median'],
                     flood['max_rate_pps']['stdev'],
                     flood['max_rate_pps']['min'],
                     flood['max_rate_pps']['max']])
        rows.append(['Flood', 'Avg Rate (pps)',
                     flood['avg_rate_pps']['mean'],
                     flood['avg_rate_pps']['median'],
                     flood['avg_rate_pps']['stdev'],
                     flood['avg_rate_pps']['min'],
                     flood['avg_rate_pps']['max']])
        rows.append(['Flood', 'Rate Adjustments',
                     flood['rate_adjustments']['mean'],
                     flood['rate_adjustments']['median'],
                     flood['rate_adjustments']['stdev'],
                     flood['rate_adjustments']['min'],
                     flood['rate_adjustments']['max']])

        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)

    def analyze(self, output_dir: str = None) -> None:
        """Run full analysis pipeline"""
        if output_dir is None:
            output_dir = str(self.data_dir)

        # Load all runs
        self.load_all_runs()

        if not self.runs:
            print("Error: No benchmark runs found")
            sys.exit(1)

        # Calculate statistics
        stats = self.calculate_statistics()

        # Save statistics
        stats_file = os.path.join(output_dir, 'statistics.json')
        self.save_statistics(stats, stats_file)
        print(f"Statistics saved to: {stats_file}")

        # Generate CSV
        csv_file = os.path.join(output_dir, 'summary.csv')
        self.generate_csv(stats, csv_file)
        print(f"CSV summary saved to: {csv_file}")

        # Generate text summary
        summary_file = os.path.join(output_dir, 'summary.txt')
        with open(summary_file, 'w') as f:
            f.write(self.generate_summary_text(stats))
        print(f"Text summary saved to: {summary_file}")

        # Print summary to console
        print("\n" + self.generate_summary_text(stats))


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze.py <data_directory>")
        sys.exit(1)

    data_dir = sys.argv[1]
    analyzer = BenchmarkAnalyzer(data_dir)
    analyzer.analyze()


if __name__ == '__main__':
    main()
