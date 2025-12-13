#!/usr/bin/env python3

"""
TGP-Piper Benchmark Visualization
Generates plots and charts from benchmark data
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

class BenchmarkVisualizer:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.stats_file = self.data_dir / 'statistics.json'
        self.output_dir = self.data_dir / 'plots'

        # Create output directory
        self.output_dir.mkdir(exist_ok=True)

    def load_statistics(self) -> Dict[str, Any]:
        """Load statistics from JSON file"""
        with open(self.stats_file, 'r') as f:
            return json.load(f)

    def plot_connection_time(self, stats: Dict[str, Any]) -> None:
        """Plot connection time comparison"""
        conn = stats['connection']

        fig, ax = plt.subplots(figsize=(10, 6))

        # Bar plot of mean connection time
        bars = ax.bar(['Connection Time', 'Bilateral Receipt'],
                      [conn['time_ms']['mean'], conn['bilateral_receipt_time_ms']['mean']],
                      yerr=[conn['time_ms']['stdev'], conn['bilateral_receipt_time_ms']['stdev']],
                      capsize=10, color=['#1f77b4', '#ff7f0e'])

        ax.set_ylabel('Time (ms)', fontsize=12)
        ax.set_title(f'Connection Establishment Time - {stats["scenario"].upper()}', fontsize=14)
        ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        ax.bar_label(bars, fmt='%.2f ms', padding=3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'connection_time.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_throughput(self, stats: Dict[str, Any]) -> None:
        """Plot throughput metrics"""
        xfer = stats['transfer']

        fig, ax = plt.subplots(figsize=(10, 6))

        # Create a box plot style visualization
        throughputs = [xfer['throughput_mbps']['min'],
                      xfer['throughput_mbps']['median'],
                      xfer['throughput_mbps']['max']]
        labels = ['Min', 'Median', 'Max']

        ax.plot(labels, throughputs, marker='o', linestyle='-',
                color='#2ca02c', linewidth=2, markersize=10)
        ax.fill_between(labels,
                       [xfer['throughput_mbps']['median'] - xfer['throughput_mbps']['stdev']] * 3,
                       [xfer['throughput_mbps']['median'] + xfer['throughput_mbps']['stdev']] * 3,
                       color='#2ca02c', alpha=0.2, label='±1 Std Dev')

        ax.set_ylabel('Throughput (MB/s)', fontsize=12)
        ax.set_title(f'Transfer Throughput - {stats["scenario"].upper()}', fontsize=14)
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend()

        # Add mean value
        ax.axhline(y=xfer['throughput_mbps']['mean'], color='red', linestyle='--',
                  label=f'Mean: {xfer["throughput_mbps"]["mean"]:.2f} MB/s')
        ax.legend()

        plt.tight_layout()
        plt.savefig(self.output_dir / 'throughput.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_cpu_memory(self, stats: Dict[str, Any]) -> None:
        """Plot CPU and Memory usage"""
        xfer = stats['transfer']

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # CPU Usage
        cpu_values = [xfer['cpu_usage_percent']['min'],
                     xfer['cpu_usage_percent']['median'],
                     xfer['cpu_usage_percent']['max']]
        ax1.plot(['Min', 'Median', 'Max'], cpu_values,
                marker='o', color='#d62728', linewidth=2, markersize=10)
        ax1.fill_between(['Min', 'Median', 'Max'],
                        [xfer['cpu_usage_percent']['median'] - xfer['cpu_usage_percent']['stdev']] * 3,
                        [xfer['cpu_usage_percent']['median'] + xfer['cpu_usage_percent']['stdev']] * 3,
                        color='#d62728', alpha=0.2)
        ax1.set_ylabel('CPU Usage (%)', fontsize=12)
        ax1.set_title('CPU Utilization', fontsize=12)
        ax1.grid(True, linestyle='--', alpha=0.7)
        ax1.axhline(y=xfer['cpu_usage_percent']['mean'], color='red', linestyle='--',
                   label=f'Mean: {xfer["cpu_usage_percent"]["mean"]:.1f}%')
        ax1.legend()

        # Memory Usage
        mem_values = [xfer['memory_usage_mb']['min'],
                     xfer['memory_usage_mb']['median'],
                     xfer['memory_usage_mb']['max']]
        ax2.plot(['Min', 'Median', 'Max'], mem_values,
                marker='o', color='#9467bd', linewidth=2, markersize=10)
        ax2.fill_between(['Min', 'Median', 'Max'],
                        [xfer['memory_usage_mb']['median'] - xfer['memory_usage_mb']['stdev']] * 3,
                        [xfer['memory_usage_mb']['median'] + xfer['memory_usage_mb']['stdev']] * 3,
                        color='#9467bd', alpha=0.2)
        ax2.set_ylabel('Memory (MB)', fontsize=12)
        ax2.set_title('Memory Usage', fontsize=12)
        ax2.grid(True, linestyle='--', alpha=0.7)
        ax2.axhline(y=xfer['memory_usage_mb']['mean'], color='red', linestyle='--',
                   label=f'Mean: {xfer["memory_usage_mb"]["mean"]:.1f} MB')
        ax2.legend()

        fig.suptitle(f'Resource Utilization - {stats["scenario"].upper()}', fontsize=16)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'resource_usage.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_adaptive_flood(self, stats: Dict[str, Any]) -> None:
        """Plot adaptive flood metrics"""
        flood = stats['flood']

        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot rate range
        bars = ax.bar(['Min Rate', 'Average Rate', 'Max Rate'],
                      [flood['min_rate_pps']['mean'],
                       flood['avg_rate_pps']['mean'],
                       flood['max_rate_pps']['mean']],
                      yerr=[flood['min_rate_pps']['stdev'],
                            flood['avg_rate_pps']['stdev'],
                            flood['max_rate_pps']['stdev']],
                      capsize=10, color=['#1f77b4', '#2ca02c', '#ff7f0e'])

        ax.set_ylabel('Packets per Second', fontsize=12)
        ax.set_title(f'Adaptive Flood Rate Control - {stats["scenario"].upper()}', fontsize=14)
        ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        ax.bar_label(bars, fmt='%.0f pps', padding=3)

        plt.tight_layout()
        plt.savefig(self.output_dir / 'adaptive_flood.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_comparison(self, baseline_stats: Dict[str, Any], new_stats: Dict[str, Any]) -> None:
        """Plot comparison between baseline and new implementation"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # Connection time comparison
        axes[0, 0].bar(['Baseline', 'TGP-Piper'],
                       [baseline_stats['connection']['time_ms']['mean'],
                        new_stats['connection']['time_ms']['mean']],
                       color=['#999999', '#1f77b4'])
        axes[0, 0].set_ylabel('Time (ms)')
        axes[0, 0].set_title('Connection Time Comparison')
        axes[0, 0].grid(True, axis='y', linestyle='--', alpha=0.7)

        # Throughput comparison
        axes[0, 1].bar(['Baseline', 'TGP-Piper'],
                       [baseline_stats['transfer']['throughput_mbps']['mean'],
                        new_stats['transfer']['throughput_mbps']['mean']],
                       color=['#999999', '#2ca02c'])
        axes[0, 1].set_ylabel('Throughput (MB/s)')
        axes[0, 1].set_title('Throughput Comparison')
        axes[0, 1].grid(True, axis='y', linestyle='--', alpha=0.7)

        # CPU usage comparison
        axes[1, 0].bar(['Baseline', 'TGP-Piper'],
                       [baseline_stats['transfer']['cpu_usage_percent']['mean'],
                        new_stats['transfer']['cpu_usage_percent']['mean']],
                       color=['#999999', '#d62728'])
        axes[1, 0].set_ylabel('CPU Usage (%)')
        axes[1, 0].set_title('CPU Efficiency Comparison')
        axes[1, 0].grid(True, axis='y', linestyle='--', alpha=0.7)

        # Packet loss tolerance comparison
        axes[1, 1].bar(['Baseline', 'TGP-Piper'],
                       [baseline_stats['transfer']['packet_loss_percent']['mean'],
                        new_stats['transfer']['packet_loss_percent']['mean']],
                       color=['#999999', '#9467bd'])
        axes[1, 1].set_ylabel('Packet Loss (%)')
        axes[1, 1].set_title('Packet Loss Tolerance')
        axes[1, 1].grid(True, axis='y', linestyle='--', alpha=0.7)

        fig.suptitle('TGP-Piper vs PipePiper Performance Comparison', fontsize=16)
        plt.tight_layout()
        plt.savefig(self.output_dir / 'comparison.png', dpi=300, bbox_inches='tight')
        plt.close()

    def generate_html_dashboard(self, stats: Dict[str, Any]) -> None:
        """Generate HTML dashboard with all visualizations"""
        dashboard_file = self.output_dir / 'dashboard.html'

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TGP-Piper Benchmark Dashboard - {stats['scenario'].upper()}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; text-align: center; }}
        h2 {{ color: #555; border-bottom: 2px solid #ddd; padding-bottom: 5px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .plot {{ margin: 20px 0; text-align: center; }}
        .plot img {{ max-width: 100%; height: auto; border: 1px solid #ddd; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .stats-table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        .stats-table th, .stats-table td {{ padding: 8px; text-align: left; border: 1px solid #ddd; }}
        .stats-table th {{ background: #f2f2f2; }}
        .stats-table tr:nth-child(even) {{ background: #f9f9f9; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>TGP-Piper Benchmark Dashboard - {stats['scenario'].upper()}</h1>

        <div class="summary">
            <h2>Summary Statistics</h2>
            <table class="stats-table">
                <tr><th>Metric</th><th>Mean</th><th>Median</th><th>StdDev</th><th>Min</th><th>Max</th></tr>
                <tr><td>Connection Time (ms)</td>
                    <td>{stats['connection']['time_ms']['mean']:.2f}</td>
                    <td>{stats['connection']['time_ms']['median']:.2f}</td>
                    <td>{stats['connection']['time_ms']['stdev']:.2f}</td>
                    <td>{stats['connection']['time_ms']['min']:.2f}</td>
                    <td>{stats['connection']['time_ms']['max']:.2f}</td></tr>
                <tr><td>Throughput (MB/s)</td>
                    <td>{stats['transfer']['throughput_mbps']['mean']:.2f}</td>
                    <td>{stats['transfer']['throughput_mbps']['median']:.2f}</td>
                    <td>{stats['transfer']['throughput_mbps']['stdev']:.2f}</td>
                    <td>{stats['transfer']['throughput_mbps']['min']:.2f}</td>
                    <td>{stats['transfer']['throughput_mbps']['max']:.2f}</td></tr>
                <tr><td>CPU Usage (%)</td>
                    <td>{stats['transfer']['cpu_usage_percent']['mean']:.1f}</td>
                    <td>{stats['transfer']['cpu_usage_percent']['median']:.1f}</td>
                    <td>{stats['transfer']['cpu_usage_percent']['stdev']:.1f}</td>
                    <td>{stats['transfer']['cpu_usage_percent']['min']:.1f}</td>
                    <td>{stats['transfer']['cpu_usage_percent']['max']:.1f}</td></tr>
                <tr><td>Memory Usage (MB)</td>
                    <td>{stats['transfer']['memory_usage_mb']['mean']:.1f}</td>
                    <td>{stats['transfer']['memory_usage_mb']['median']:.1f}</td>
                    <td>{stats['transfer']['memory_usage_mb']['stdev']:.1f}</td>
                    <td>{stats['transfer']['memory_usage_mb']['min']:.1f}</td>
                    <td>{stats['transfer']['memory_usage_mb']['max']:.1f}</td></tr>
            </table>
        </div>

        <div class="plot">
            <h2>Connection Time</h2>
            <img src="connection_time.png" alt="Connection Time Plot">
        </div>

        <div class="plot">
            <h2>Transfer Throughput</h2>
            <img src="throughput.png" alt="Throughput Plot">
        </div>

        <div class="plot">
            <h2>Resource Utilization</h2>
            <img src="resource_usage.png" alt="Resource Usage Plot">
        </div>

        <div class="plot">
            <h2>Adaptive Flood Control</h2>
            <img src="adaptive_flood.png" alt="Adaptive Flood Plot">
        </div>

        <div class="summary">
            <h2>Benchmark Details</h2>
            <p><strong>Scenario:</strong> {stats['scenario']}</p>
            <p><strong>Total Runs:</strong> {stats['total_runs']}</p>
            <p><strong>Timestamp:</strong> {stats['timestamp']}</p>
        </div>
    </div>
</body>
</html>
"""

        with open(dashboard_file, 'w') as f:
            f.write(html_content)

        print(f"Dashboard generated: {dashboard_file}")

    def visualize(self) -> None:
        """Run full visualization pipeline"""
        if not self.stats_file.exists():
            print(f"Error: Statistics file not found at {self.stats_file}")
            print("Please run analyze.py first to generate statistics")
            sys.exit(1)

        # Load statistics
        stats = self.load_statistics()

        print(f"Generating visualizations for {stats['scenario']} scenario...")

        # Generate plots
        self.plot_connection_time(stats)
        print("✓ Connection time plot generated")

        self.plot_throughput(stats)
        print("✓ Throughput plot generated")

        self.plot_cpu_memory(stats)
        print("✓ Resource usage plot generated")

        self.plot_adaptive_flood(stats)
        print("✓ Adaptive flood plot generated")

        # Generate dashboard
        self.generate_html_dashboard(stats)
        print("✓ HTML dashboard generated")

        print(f"\nAll visualizations saved to: {self.output_dir}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 visualize.py <data_directory>")
        sys.exit(1)

    data_dir = sys.argv[1]
    visualizer = BenchmarkVisualizer(data_dir)
    visualizer.visualize()


if __name__ == '__main__':
    main()
