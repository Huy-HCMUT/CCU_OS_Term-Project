#!/usr/bin/env python3
"""
plot_config_c_dual_metrology.py
Generates academic publication-quality figures for:
1. DWT vs Hardware Referee Dual-Perspective Telemetry
2. Master Architecture Contrast: Config A vs Config B vs Config C
"""

import csv
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

def generate_plots():
    results_dir = Path(__file__).resolve().parent.parent / "results"
    raw_dir = results_dir / "raw"
    plots_dir = results_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Config C data (Stress 100)
    dwt_path = raw_dir / "config_c_dwt_stress100.csv"
    ref_path = raw_dir / "config_c_referee_stress100.csv"

    d_rows = list(csv.DictReader(open(dwt_path)))[1:]
    r_rows = list(csv.DictReader(open(ref_path)))[1:]

    d_periods = np.array([float(r['dwt_period_us']) for r in d_rows])
    r_periods = np.array([float(r['interval_us']) for r in r_rows])
    discrepancy = r_periods - d_periods
    cycles = np.arange(1, len(d_periods) + 1)

    # Configure styling
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 11,
        'axes.labelsize': 12,
        'axes.titlesize': 13,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 11,
        'figure.titlesize': 15,
        'figure.dpi': 300
    })

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Heterogeneous Dual-OS Real-Time Validation: Config C (Zephyr on STM32)\nInternal DWT Cycle Counter vs External Hardware Referee (100% Linux Stress)", fontweight='bold')

    # Subplot 1: Time Series of 10 ms Period (Cycles 1..999)
    ax1 = axes[0, 0]
    ax1.plot(cycles, d_periods / 1000.0, label='Board 1: STM32 DWT (Internal)', color='#1f77b4', alpha=0.8, linewidth=1.2)
    ax1.plot(cycles, r_periods / 1000.0, label='Board 2: Referee EXTI (External)', color='#ff7f0e', alpha=0.7, linestyle='--', linewidth=1.2)
    ax1.axhline(10.000, color='gray', linestyle=':', label='Target Period (10.000 ms)')
    ax1.set_xlabel('Actuation Cycle (k)')
    ax1.set_ylabel('Cycle Period (ms)')
    ax1.set_title('A: Period Stability Under 100% Linux Storm Contention')
    ax1.set_ylim([9.98, 10.02])
    ax1.grid(True, linestyle='--', alpha=0.5)
    ax1.legend(loc='upper right')

    # Subplot 2: Discrepancy & Static Clock Drift Distribution
    ax2 = axes[0, 1]
    drift_mean = np.mean(discrepancy)
    drift_std = np.std(discrepancy)
    n, bins, patches = ax2.hist(discrepancy, bins=25, color='#2ca02c', edgecolor='black', alpha=0.7)
    ax2.axvline(drift_mean, color='red', linestyle='--', linewidth=2, label=f'Mean Drift: {drift_mean:.2f} µs (157 ppm)')
    ax2.set_xlabel('Inter-Device Discrepancy (Referee - DWT) [µs]')
    ax2.set_ylabel('Cycle Frequency Count')
    ax2.set_title(f'B: Crystal Clock Drift Distribution (σ = {drift_std*1000:.0f} ns)')
    ax2.grid(True, linestyle='--', alpha=0.5)
    ax2.legend(loc='upper left')

    # Subplot 3: High-Zoom Jitter Histogram (Referee Physical Arrival)
    ax3 = axes[1, 0]
    jitter_us = r_periods - 10000.0
    ax3.hist(jitter_us, bins=20, color='#9467bd', edgecolor='black', alpha=0.7)
    ax3.axvline(np.mean(jitter_us), color='black', linestyle='--', label=f'Mean: {np.mean(jitter_us):.2f} µs')
    ax3.set_xlabel('Physical Arrival Jitter [µs]')
    ax3.set_ylabel('Cycle Frequency Count')
    ax3.set_title(f'C: Hardware Referee Physical Jitter (Max Jitter = {np.max(np.abs(jitter_us)):.1f} µs)')
    ax3.grid(True, linestyle='--', alpha=0.5)
    ax3.legend(loc='upper right')

    # Subplot 4: Master Architecture Comparison (Logarithmic Scale)
    ax4 = axes[1, 1]
    configs = ['Config A\n(Linux CFS)', 'Config B\n(Linux FIFO 90)', 'Config C\n(Zephyr Dual-OS)']
    jitters_std = [1733.0, 34.0, np.std(r_periods)] # us
    colors = ['#d62728', '#1f77b4', '#2ca02c']

    bars = ax4.bar(configs, jitters_std, color=colors, edgecolor='black', width=0.5)
    ax4.set_yscale('log')
    ax4.set_ylabel('Timing Jitter Std Dev [µs] (Log Scale)')
    ax4.set_title('D: Timing Jitter Contrast Across System Architectures')
    ax4.grid(True, which='both', linestyle='--', alpha=0.5)

    for bar, val in zip(bars, jitters_std):
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval * 1.3, f'{val:.2f} µs', ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    out_file = plots_dir / "config_c_dual_metrology_plot.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Master plot saved to: {out_file}")

if __name__ == "__main__":
    generate_plots()
