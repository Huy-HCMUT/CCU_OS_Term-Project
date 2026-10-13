#!/usr/bin/env python3
"""
parse_all_in_one_metrics.py - Telemetry Parser & Master KPI Table Generator
Course: CCU Operating Systems (Fall 2026) - Term Project
Author: Quang-Huy Nguyen & Akash / An-Rui Peng

Parses the All-in-One Industrial Benchmark raw CSV files:
  - Config A (CFS) vs Config B (SCHED_FIFO 90 + mlockall + Core 0 Pinning)
  - Across 0% (Idle), 50% (Medium Composite), 100% (Maximum Storm)
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

RESULTS_DIR = Path(__file__).resolve().parent / "raw"
PLOTS_DIR = Path(__file__).resolve().parent / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

def analyze_csv(csv_path: Path):
    if not csv_path.exists():
        return None

    try:
        data = np.genfromtxt(csv_path, delimiter=",", skip_header=1)
    except Exception:
        return None

    if data.ndim == 1 and len(data) == 0:
        return None
    if data.ndim == 1:
        data = data.reshape(1, -1)

    lateness = data[:, 3]
    is_miss = data[:, 4]
    is_starv = data[:, 5]
    nivcsw = data[:, 7]
    minflt = data[:, 8]

    n_cycles = len(lateness)
    avg_l = float(np.mean(lateness))
    min_l = float(np.min(lateness))
    max_l = float(np.max(lateness))
    p999_l = float(np.percentile(lateness, 99.9))
    jitter_sigma = float(np.std(lateness))
    miss_count = int(np.sum(is_miss))
    dmr = (miss_count / n_cycles) * 100.0 if n_cycles > 0 else 0.0
    miss_count_05 = int(np.sum(lateness > 0.5))
    dmr_05 = (miss_count_05 / n_cycles) * 100.0 if n_cycles > 0 else 0.0
    miss_count_02 = int(np.sum(lateness > 0.2))
    dmr_02 = (miss_count_02 / n_cycles) * 100.0 if n_cycles > 0 else 0.0
    starv_count = int(np.sum(is_starv))

    delta_nivcsw = int(nivcsw[-1] - nivcsw[0]) if len(nivcsw) > 1 else 0
    delta_minflt = int(minflt[-1] - minflt[0]) if len(minflt) > 1 else 0

    return {
        "n_cycles": n_cycles,
        "avg_l": avg_l,
        "min_l": min_l,
        "max_l": max_l,
        "p999_l": p999_l,
        "jitter_sigma": jitter_sigma,
        "miss_count": miss_count,
        "dmr": dmr,
        "miss_count_05": miss_count_05,
        "dmr_05": dmr_05,
        "miss_count_02": miss_count_02,
        "dmr_02": dmr_02,
        "starv_count": starv_count,
        "nivcsw": delta_nivcsw,
        "minflt": delta_minflt
    }

def generate_master_plot(results):
    stresses = [0, 50, 100]
    cfs_max = [results.get(('A', s), {}).get('max_l', 0) for s in stresses]
    fifo_max = [results.get(('B', s), {}).get('max_l', 0) for s in stresses]
    cfs_dmr = [results.get(('A', s), {}).get('dmr', 0) for s in stresses]
    fifo_dmr = [results.get(('B', s), {}).get('dmr', 0) for s in stresses]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Worst-Case Lateness
    x = np.arange(len(stresses))
    width = 0.35

    rects1 = ax1.bar(x - width/2, cfs_max, width, label='Config A (Linux CFS)', color='#e63946', alpha=0.85)
    rects2 = ax1.bar(x + width/2, fifo_max, width, label='Config B (SCHED_FIFO 90)', color='#2a9d8f', alpha=0.85)
    ax1.axhline(1.0, color='#d62828', linestyle='--', linewidth=1.5, label='Deadline Limit (1.0 ms)')
    ax1.set_ylabel('Worst-Case Lateness (ms)')
    ax1.set_title('All-in-One Stress: Worst-Case Lateness Comparison')
    ax1.set_xticks(x)
    ax1.set_xticklabels(['0% (Idle)', '50% (Composite)', '100% (Storm)'])
    ax1.legend(loc='upper left')

    for r in rects1:
        h = r.get_height()
        ax1.annotate(f'{h:.2f} ms', xy=(r.get_x() + r.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')
    for r in rects2:
        h = r.get_height()
        ax1.annotate(f'{h:.2f} ms', xy=(r.get_x() + r.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')

    # Deadline Miss Ratio
    rects3 = ax2.bar(x - width/2, cfs_dmr, width, label='Config A (CFS)', color='#e63946', alpha=0.85)
    rects4 = ax2.bar(x + width/2, fifo_dmr, width, label='Config B (SCHED_FIFO)', color='#2a9d8f', alpha=0.85)
    ax2.set_ylabel('Deadline Miss Ratio (DMR %)')
    ax2.set_title('All-in-One Stress: Deadline Miss Ratio (%)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(['0% (Idle)', '50% (Composite)', '100% (Storm)'])
    ax2.legend(loc='upper left')

    for r in rects3:
        h = r.get_height()
        ax2.annotate(f'{h:.2f}%', xy=(r.get_x() + r.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')
    for r in rects4:
        h = r.get_height()
        ax2.annotate(f'{h:.2f}%', xy=(r.get_x() + r.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8, fontweight='bold')

    plt.tight_layout()
    out = PLOTS_DIR / "all_in_one_master_comparison.png"
    plt.savefig(out, dpi=300)
    plt.close()
    print(f"[Plot] Saved All-in-One master figure: {out}")

def main():
    print("=" * 105)
    print(" CCU OS Term Project: ULTIMATE ALL-IN-ONE INDUSTRIAL BENCHMARK RESULTS")
    print(" Vectors Combined: CPU Saturation + Flash I/O + VM Memory + Single-Core Pinning")
    print("=" * 105)

    configs = ["A", "B"]
    stresses = [0, 50, 100]

    results = {}
    for cfg in configs:
        for st in stresses:
            fname = f"all_in_one_config_{cfg}_stress_{st}.csv"
            fpath = RESULTS_DIR / fname
            results[(cfg, st)] = analyze_csv(fpath)

    print("\n| Configuration | All-in-One Stress | Avg Lateness | Worst-Case Lateness | Tail (P99.9) | Jitter (σ) | DMR (1.0ms) | Misses | Invol Ctx Sw | Minor Faults |")
    print("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for cfg in configs:
        cfg_name = "Config A (Linux CFS)" if cfg == "A" else "Config B (SCHED_FIFO 90 + mlock)"
        for st in stresses:
            m = results.get((cfg, st))
            st_label = f"{st}% (Idle)" if st == 0 else (f"{st}% (Composite)" if st == 50 else f"{st}% (Storm)")
            if m:
                print(f"| **{cfg_name}** | **{st_label}** | {m['avg_l']:.3f} ms | **{m['max_l']:.3f} ms** | {m['p999_l']:.3f} ms | {m['jitter_sigma']:.3f} ms | **{m['dmr']:.2f}%** | **{m['miss_count']} / {m['n_cycles']}** | {m['nivcsw']} | {m['minflt']} |")
            else:
                print(f"| **{cfg_name}** | **{st_label}** | *(Pending)* | - | - | - | - | - | - | - |")

    print("\n" + "=" * 105)
    print(" INDUSTRIAL PRECISION TOLERANCE SENSITIVITY BREAKDOWN (1.0 ms vs 0.5 ms vs 0.2 ms)")
    print("=" * 105)
    print("| Configuration | Stress Tier | DMR @ 1.0 ms (Standard) | DMR @ 0.5 ms (Medium) | DMR @ 0.2 ms (Precision 200 µs) | Misses @ 200 µs |")
    print("| :---: | :---: | :---: | :---: | :---: | :---: |")

    for cfg in configs:
        cfg_name = "Config A (CFS)" if cfg == "A" else "Config B (FIFO 90)"
        for st in stresses:
            m = results.get((cfg, st))
            st_label = f"{st}% (Idle)" if st == 0 else (f"{st}% (Composite)" if st == 50 else f"{st}% (Storm)")
            if m:
                print(f"| **{cfg_name}** | **{st_label}** | **{m['dmr']:.2f}%** ({m['miss_count']}) | **{m['dmr_05']:.2f}%** ({m['miss_count_05']}) | **{m['dmr_02']:.2f}%** ({m['miss_count_02']}) | **{m['miss_count_02']} / {m['n_cycles']}** |")

    print("=" * 105 + "\n")

    # If all results present, generate master plot
    if all(results.get((c, s)) is not None for c in configs for s in stresses):
        generate_master_plot(results)

if __name__ == "__main__":
    main()
