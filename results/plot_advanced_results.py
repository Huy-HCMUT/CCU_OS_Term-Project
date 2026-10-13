#!/usr/bin/env python3
"""
plot_advanced_results.py - High-Resolution Publication Plots for Tests 1 to 5
Course: CCU Operating Systems (Fall 2026) - Term Project
Author: Quang-Huy Nguyen & Akash / An-Rui Peng
"""

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

RAW_DIR = Path(__file__).resolve().parent / "raw"
PLOTS_DIR = Path(__file__).resolve().parent / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# Set clean aesthetic styling
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "font.family": "sans-serif",
    "figure.titlesize": 14,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 300
})

def load_data(fname):
    p = RAW_DIR / fname
    if not p.exists():
        return None
    d = np.genfromtxt(p, delimiter=",", skip_header=1)
    return d

def plot_test1():
    d_cfs = load_data("test1_io_config_A.csv")
    d_fifo = load_data("test1_io_config_B.csv")
    if d_cfs is None or d_fifo is None:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Time series
    t_cfs = d_cfs[:, 0] * 0.01  # convert cycle to seconds
    l_cfs = d_cfs[:, 3]
    t_fifo = d_fifo[:, 0] * 0.01
    l_fifo = d_fifo[:, 3]

    ax1.plot(t_cfs, l_cfs, label="Config A (Linux CFS)", color="#e63946", alpha=0.85, linewidth=1.0)
    ax1.plot(t_fifo, l_fifo, label="Config B (SCHED_FIFO 90)", color="#2a9d8f", alpha=0.9, linewidth=1.0)
    ax1.axhline(1.0, color="#d62828", linestyle="--", linewidth=1.5, label="Deadline Limit (1.0 ms)")
    ax1.set_xlabel("Elapsed Time (seconds)")
    ax1.set_ylabel("Wake-up Lateness $L_k$ (ms)")
    ax1.set_title("Test 1: Lateness under Flash/eMMC I/O Contention")
    ax1.set_ylim(-0.2, 21.0)
    ax1.legend(loc="upper right", frameon=True)

    # CDF
    sorted_cfs = np.sort(l_cfs)
    sorted_fifo = np.sort(l_fifo)
    p_cfs = np.linspace(0, 1, len(sorted_cfs))
    p_fifo = np.linspace(0, 1, len(sorted_fifo))

    ax2.plot(sorted_cfs, p_cfs, label="Config A (CFS)", color="#e63946", linewidth=2.0)
    ax2.plot(sorted_fifo, p_fifo, label="Config B (SCHED_FIFO)", color="#2a9d8f", linewidth=2.0)
    ax2.axvline(1.0, color="#d62828", linestyle="--", linewidth=1.5, label="Deadline (1.0 ms)")
    ax2.set_xlabel("Wake-up Lateness $L_k$ (ms)")
    ax2.set_ylabel("Cumulative Probability (CDF)")
    ax2.set_title("Test 1: Empirical CDF Comparison")
    ax2.set_xlim(-0.1, 5.0)
    ax2.legend(loc="lower right", frameon=True)

    plt.tight_layout()
    out = PLOTS_DIR / "test1_io_contention_comparison.png"
    plt.savefig(out)
    plt.close()
    print(f"[Plot] Saved: {out}")

def plot_test2():
    d = load_data("test2_10000_cycles_config_B.csv")
    if d is None:
        return

    fig, ax = plt.subplots(figsize=(10, 4.5))
    t = d[:, 0] * 0.01
    l = d[:, 3]

    ax.plot(t, l, color="#1d3557", alpha=0.75, linewidth=0.8, label="Cycle Lateness $L_k$")
    ax.axhline(1.0, color="#e63946", linestyle="--", linewidth=1.5, label="1.0 ms Deadline Threshold")
    ax.axhline(np.mean(l), color="#e76f51", linestyle="-", linewidth=1.5, label=f"Mean Latency ({np.mean(l):.3f} ms)")

    ax.set_xlabel("Continuous Operation Time (seconds)")
    ax.set_ylabel("Wake-up Lateness $L_k$ (ms)")
    ax.set_title("Test 2: Extended 10,000-Cycle Endurance Profile (100 s Continuous under 100% Stress)")
    ax.set_ylim(-0.05, 1.2)
    ax.legend(loc="upper right", frameon=True)

    plt.tight_layout()
    out = PLOTS_DIR / "test2_10000_cycles_endurance.png"
    plt.savefig(out)
    plt.close()
    print(f"[Plot] Saved: {out}")

def plot_test3():
    d_float = load_data("test3_affinity_floating.csv")
    d_core0 = load_data("test3_affinity_pinned_core0.csv")
    if d_float is None or d_core0 is None:
        return

    fig, ax = plt.subplots(figsize=(8, 4.5))
    l_float = d_float[:, 3]
    l_core0 = d_core0[:, 3]

    data = [l_float, l_core0]
    box = ax.boxplot(data, tick_labels=["Floating (4 Cores)", "Co-located (Core 0)"],
                     patch_artist=True, showmeans=True, showfliers=True)

    colors = ["#457b9d", "#e76f51"]
    for patch, color in zip(box['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Wake-up Lateness $L_k$ (ms)")
    ax.set_title("Test 3: CPU Affinity & Core Pinning Contention Comparison")
    ax.axhline(1.0, color="#d62828", linestyle="--", label="Deadline (1.0 ms)")
    ax.legend(loc="upper right")

    plt.tight_layout()
    out = PLOTS_DIR / "test3_affinity_comparison.png"
    plt.savefig(out)
    plt.close()
    print(f"[Plot] Saved: {out}")

def plot_test4():
    d_nomlock = load_data("test4_memory_no_mlock.csv")
    d_mlock = load_data("test4_memory_with_mlock.csv")
    if d_nomlock is None or d_mlock is None:
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Minor page fault bar comparison
    d_minflt_no = int(d_nomlock[-1, 8] - d_nomlock[0, 8])
    d_minflt_yes = int(d_mlock[-1, 8] - d_mlock[0, 8])

    bars = ax1.bar(["Without mlockall", "With mlockall (--mlock)"], [d_minflt_no, d_minflt_yes],
                   color=["#e63946", "#2a9d8f"], width=0.5)
    ax1.set_ylabel("Minor Page Faults (ru_minflt)")
    ax1.set_title("Test 4: Elimination of MMU Page Faults")
    for bar in bars:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval + 0.5, str(yval), ha='center', va='bottom', fontweight='bold')

    # Lateness distribution
    ax2.plot(d_nomlock[:500, 0] * 0.01, d_nomlock[:500, 3], label="Default (No mlock)", color="#e63946", alpha=0.8)
    ax2.plot(d_mlock[:500, 0] * 0.01, d_mlock[:500, 3], label="Locked (--mlock)", color="#2a9d8f", alpha=0.8)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Lateness (ms)")
    ax2.set_title("Test 4: Transient Lateness Comparison")
    ax2.legend(loc="upper right")

    plt.tight_layout()
    out = PLOTS_DIR / "test4_memory_locking.png"
    plt.savefig(out)
    plt.close()
    print(f"[Plot] Saved: {out}")

def plot_test5():
    d_fifo = load_data("test5_policy_sched_fifo.csv")
    d_rr = load_data("test5_policy_sched_rr.csv")
    if d_fifo is None or d_rr is None:
        return

    fig, ax = plt.subplots(figsize=(8, 4.5))
    l_fifo = d_fifo[:, 3]
    l_rr = d_rr[:, 3]

    ax.hist(l_fifo, bins=40, alpha=0.6, label="SCHED_FIFO (Prio 90)", color="#2a9d8f", density=True)
    ax.hist(l_rr, bins=40, alpha=0.6, label="SCHED_RR (Prio 90)", color="#e76f51", density=True)
    ax.set_xlabel("Wake-up Lateness $L_k$ (ms)")
    ax.set_ylabel("Probability Density")
    ax.set_title("Test 5: Real-Time Policy Distribution (SCHED_FIFO vs SCHED_RR)")
    ax.legend(loc="upper right")

    plt.tight_layout()
    out = PLOTS_DIR / "test5_policy_comparison.png"
    plt.savefig(out)
    plt.close()
    print(f"[Plot] Saved: {out}")

def main():
    plot_test1()
    plot_test2()
    plot_test3()
    plot_test4()
    plot_test5()
    print("[Plots] All publication plots generated successfully in results/plots/!")

if __name__ == "__main__":
    main()
