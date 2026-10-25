#!/usr/bin/env python3
"""
parse_advanced_metrics.py - Telemetry Parser for Tests 1 through 5
Course: CCU Operating Systems (Fall 2026) - Term Project
Author: Quang-Huy Nguyen & Akash / An-Rui Peng

Parses the raw CSV files for the 5 advanced empirical stress tests:
  - Test 1: Kernel I/O Contention (Emergency Flash Dump)
  - Test 2: Extended 10,000-Cycle Endurance (30s Writeback Flush)
  - Test 3: CPU Affinity & Core Pinning (Co-location vs Floating)
  - Test 4: Virtual Memory Locking (mlockall vs Default)
  - Test 5: RT Scheduling Policy (SCHED_FIFO vs SCHED_RR)

Outputs clean, publication-ready Markdown tables and key OS insights.
"""

import sys
from pathlib import Path
import numpy as np

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

RESULTS_DIR = Path(__file__).resolve().parent / "raw"

def analyze_csv(csv_path: Path):
    if not csv_path.exists():
        return None

    try:
        data = np.genfromtxt(csv_path, delimiter=",", skip_header=1)
    except Exception as e:
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
        "starv_count": starv_count,
        "nivcsw": delta_nivcsw,
        "minflt": delta_minflt
    }

def print_test_row(name, m):
    if m:
        print(f"| **{name}** | {m['n_cycles']} | {m['avg_l']:.3f} ms | **{m['max_l']:.3f} ms** | {m['p999_l']:.3f} ms | {m['jitter_sigma']:.3f} ms | **{m['dmr']:.2f}%** ({m['miss_count']}) | {m['nivcsw']} | {m['minflt']} |")
    else:
        print(f"| **{name}** | *(Pending)* | - | - | - | - | - | - | - |")

def main():
    print("=" * 105)
    print(" CCU OS Term Project: Comprehensive Advanced Benchmark Results (Tests 1–5)")
    print(" Hardware: Arduino UNO Q (Qualcomm Cortex-A53 Linux MPU)")
    print("=" * 105)

    tests = [
        ("Test 1: Kernel I/O Contention", [
            ("Test 1A: Config A (CFS + I/O Contention)", "test1_io_config_A.csv"),
            ("Test 1B: Config B (FIFO 90 + I/O Contention)", "test1_io_config_B.csv")
        ]),
        ("Test 2: Extended 10,000-Cycle Endurance (100 s continuous)", [
            ("Test 2: Config B (FIFO 90, 10,000 Cycles)", "test2_10000_cycles_config_B.csv")
        ]),
        ("Test 3: CPU Affinity & Core Pinning Contention", [
            ("Test 3A: Floating across 4 Cores", "test3_affinity_floating.csv"),
            ("Test 3B: Co-located on Core 0 (--affinity 0)", "test3_affinity_pinned_core0.csv")
        ]),
        ("Test 4: Virtual Memory Locking (mlockall)", [
            ("Test 4A: Without mlockall (Default)", "test4_memory_no_mlock.csv"),
            ("Test 4B: With mlockall (--mlock)", "test4_memory_with_mlock.csv")
        ]),
        ("Test 5: Real-Time Scheduling Policy Comparison", [
            ("Test 5A: SCHED_FIFO (Priority 90)", "test5_policy_sched_fifo.csv"),
            ("Test 5B: SCHED_RR (Priority 90)", "test5_policy_sched_rr.csv")
        ])
    ]

    for title, group in tests:
        print(f"\n### {title}")
        print("| Condition | Cycles | Avg Lateness | Worst-Case Lateness | Tail (P99.9) | Jitter (σ) | DMR (%) [Misses] | Invol Ctx Sw | Minor Faults |")
        print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for label, fname in group:
            fpath = RESULTS_DIR / fname
            metrics = analyze_csv(fpath)
            print_test_row(label, metrics)

    print("\n" + "=" * 105)

if __name__ == "__main__":
    main()
