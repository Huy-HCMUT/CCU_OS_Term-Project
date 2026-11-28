#!/usr/bin/env python3
"""Presentation charts, drawn from the committed result tables.

Writes six PNGs to results/slides/ in the presentation's style (white card
background, fixed colour per configuration, 1 ms deadline dashed):

  synthetic_wcl.png   worst case under stress-ng, per tier (phase5d/compare_long.csv)
  realload_block.png  typical block worst case with 95 % intervals (phase6b/headline_stats.csv)
  misses_rboth.png    deadline-miss ratio under rboth, pooled + per run (headline_stats.csv)
  kernel_cpu3.png     kernel work and busy share on CPU 3, B vs B-iso (cpu_interference.csv,
                      realload_long.csv)
  mcu_priority.png    Config C variants, stock vs tuned priority (compare_long.csv)
  chain_delay.png     tick-to-drive delay and Linux-to-MCU round trip (drive_long.csv)

    python benchmarks/analysis/slide_figures.py [--results results] [--out results/slides]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

INK = "#14213D"
INK2 = "#4A5568"
MUTED = "#6B7280"
GRID = "#E9E7E1"
AXIS = "#C9C7C0"
DEADLINE = "#C2410C"
COLORS = {"A": "#2a78d6", "B": "#eb6834", "B-iso": "#6250d6", "C": "#1baf7a"}
LABELS = {"A": "A · Linux default", "B": "B · SCHED_FIFO", "B-iso": "B-iso · reserved core",
          "C": "C · Zephyr MCU"}
US_TICKS = ([1, 10, 100, 1000, 10000], ["1 µs", "10 µs", "100 µs", "1 ms", "10 ms"])


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": ["Inter", "DejaVu Sans"], "font.size": 20,
        "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": AXIS,
        "xtick.color": INK2, "ytick.color": INK2, "axes.linewidth": 1.0,
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "legend.frameon": False, "legend.fontsize": 19,
    })
    return plt


def _deadline(ax, horizontal=True, label=True):
    (ax.axhline if horizontal else ax.axvline)(1000, color=DEADLINE, lw=2, ls=(0, (6, 4)), zorder=1)
    if label:
        if horizontal:
            ax.text(0.01, 1000 * 1.18, "1 ms deadline", color=DEADLINE, fontsize=18,
                    ha="left", va="bottom", transform=ax.get_yaxis_transform())
        else:
            ax.text(1000 * 1.1, 1.0, "1 ms\ndeadline", color=DEADLINE, fontsize=17,
                    ha="left", va="top", transform=ax.get_xaxis_transform())


def _fmt_us(v: float) -> str:
    if v >= 1000:
        return f"{v / 1000:.1f} ms" if v < 10000 else f"{v / 1000:.0f} ms"
    return f"{v:.0f} µs" if v >= 10 else f"{v:.1f} µs"


def _dot_groups(ax, groups, series, value, lo, hi, width=0.62):
    """Dot + whisker per series inside each x group (log scale safe, no bars)."""
    n = len(series)
    offs = np.linspace(-width / 2, width / 2, n)
    for gi, g in enumerate(groups):
        for si, s in enumerate(series):
            v, a, b = value(g, s), lo(g, s), hi(g, s)
            if v is None:
                continue
            x = gi + offs[si]
            ax.plot([x, x], [a, b], color=COLORS[s], lw=2.5, alpha=0.9, zorder=2)
            ax.plot(x, v, "o", ms=13, color=COLORS[s], mec="white", mew=2, zorder=3)
    return offs


def synthetic(results: Path, out: Path, plt) -> Path:
    df = pd.read_csv(results / "phase5d" / "compare_long.csv")
    df["s"] = df.series.replace({"C IPC tuned": "C"})
    tiers = ["0", "50", "100", "allcore"]
    names = ["Idle", "Core 0,\nmedium", "Core 0,\nheavy", "All cores"]
    series = ["A", "B", "B-iso", "C"]
    g = df[df.s.isin(series)].groupby(["s", "tier"]).wcl_us.agg(["mean", "min", "max"])
    fig, ax = plt.subplots(figsize=(11.2, 6.6), dpi=100)
    offs = _dot_groups(ax, tiers, series,
                       lambda t, s: g.loc[(s, t), "mean"], lambda t, s: g.loc[(s, t), "min"],
                       lambda t, s: g.loc[(s, t), "max"])
    _deadline(ax)
    ax.set_yscale("log"); ax.set_ylim(0.8, 6e4)
    ax.set_yticks(*US_TICKS); ax.minorticks_off()
    ax.set_xticks(range(len(tiers)), names); ax.set_xlim(-0.6, len(tiers) - 0.05)
    ax.grid(True, axis="y", color=GRID, lw=1); ax.set_axisbelow(True)
    ax.set_ylabel("Worst-case lateness")
    for t, s in (("allcore", "A"), ("allcore", "C"), ("50", "B"), ("0", "B-iso")):
        x = tiers.index(t) + offs[series.index(s)]
        v = g.loc[(s, t), "mean"]
        ax.text(x + 0.07, v, _fmt_us(v), ha="left", va="center", fontsize=18, color=INK)
    handles = [plt.Line2D([], [], marker="o", ls="", ms=12, color=COLORS[s]) for s in series]
    ax.legend(handles, [LABELS[s] for s in series], ncol=2, loc="lower left",
              bbox_to_anchor=(-0.02, 1.0), handletextpad=0.3, columnspacing=1.5)
    fig.tight_layout()
    path = out / "synthetic_wcl.png"; fig.savefig(path); plt.close(fig)
    return path


def realload(results: Path, out: Path, plt) -> Path:
    h = pd.read_csv(results / "phase6b" / "headline_stats.csv")
    h["s"] = h.series.replace({"C act tuned": "C"})
    h = h.set_index(["s", "tier"])
    tiers = ["rnet", "rdeploy", "rboth"]
    names = ["rnet\nnetwork", "rdeploy\nCNN", "rboth\nboth at once"]
    series = ["A", "B", "B-iso", "C"]

    def lo(t, s):
        r = h.loc[(s, t)]
        return r.block_min_us if np.isnan(r.block_median_lo_us) else r.block_median_lo_us

    def hi(t, s):
        r = h.loc[(s, t)]
        return r.block_max_us if np.isnan(r.block_median_hi_us) else r.block_median_hi_us

    fig, ax = plt.subplots(figsize=(11.2, 6.6), dpi=100)
    offs = _dot_groups(ax, tiers, series, lambda t, s: h.loc[(s, t)].block_median_us, lo, hi)
    _deadline(ax)
    ax.set_yscale("log"); ax.set_ylim(0.8, 6e4)
    ax.set_yticks(*US_TICKS); ax.minorticks_off()
    ax.set_xticks(range(len(tiers)), names); ax.set_xlim(-0.6, len(tiers) - 0.05)
    ax.grid(True, axis="y", color=GRID, lw=1); ax.set_axisbelow(True)
    ax.set_ylabel("Typical worst case per 10,000 ticks")
    for s in series:
        x = 2 + offs[series.index(s)]
        ax.text(x + 0.07, h.loc[(s, "rboth")].block_median_us, _fmt_us(h.loc[(s, "rboth")].block_median_us),
                ha="left", va="center", fontsize=18, color=INK)
    handles = [plt.Line2D([], [], marker="o", ls="", ms=12, color=COLORS[s]) for s in series]
    ax.legend(handles, [LABELS[s] for s in series], ncol=2, loc="lower left",
              bbox_to_anchor=(-0.02, 1.0), handletextpad=0.3, columnspacing=1.5)
    fig.tight_layout()
    path = out / "realload_block.png"; fig.savefig(path); plt.close(fig)
    return path


def misses(results: Path, out: Path, plt) -> Path:
    h = pd.read_csv(results / "phase6b" / "headline_stats.csv")
    h["s"] = h.series.replace({"C act tuned": "C"})
    h = h[h.tier == "rboth"].set_index("s")
    rows = ["A", "B", "B-iso", "C"]
    fig, ax = plt.subplots(figsize=(10.0, 5.6), dpi=100)
    left = 0.0006
    for i, s in enumerate(rows):
        y = len(rows) - 1 - i
        r = h.loc[s]
        if r.misses == 0:
            ax.annotate("", xy=(left * 1.15, y), xytext=(r.dmr_hi_pct, y),
                        arrowprops=dict(arrowstyle="-|>", color=COLORS[s], lw=2.5, mutation_scale=22))
            ax.plot(r.dmr_hi_pct, y, "|", ms=26, mew=3, color=COLORS[s])
            ax.text(r.dmr_hi_pct * 1.6, y, f"0 misses in {r.cycles:,} ticks:\nat most {r.dmr_hi_pct:.3f} %",
                    va="center", fontsize=18, color=INK, linespacing=1.3)
            continue
        ax.plot([r.dmr_lo_pct, r.dmr_hi_pct], [y, y], color=COLORS[s], lw=9, alpha=0.35, solid_capstyle="round")
        runs = [float(v) for v in r.dmr_per_run_pct.split(";")]
        ax.plot(runs, [y] * len(runs), "o", ms=11, mfc="white", mec=COLORS[s], mew=2.5, zorder=3)
        ax.plot(r.dmr_pct, y, "o", ms=14, color=COLORS[s], mec="white", mew=2, zorder=4)
        ax.text(max(runs + [r.dmr_hi_pct]) * 1.5, y, f"{r.dmr_pct:.3g} %", va="center", fontsize=19, color=INK)
    ax.set_xscale("log"); ax.set_xlim(left, 40)
    ax.set_xticks([0.001, 0.01, 0.1, 1, 10], ["0.001 %", "0.01 %", "0.1 %", "1 %", "10 %"]); ax.minorticks_off()
    ax.set_yticks(range(len(rows)), [LABELS[s] for s in reversed(rows)])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.grid(True, axis="x", color=GRID, lw=1); ax.set_axisbelow(True)
    ax.set_xlabel("Ticks later than 1 ms (log scale)")
    handles = [plt.Line2D([], [], marker="o", ls="", ms=12, color=INK2),
               plt.Line2D([], [], marker="o", ls="", ms=10, mfc="white", mec=INK2, mew=2),
               plt.Line2D([], [], lw=8, color=INK2, alpha=0.35)]
    ax.legend(handles, ["both runs pooled", "each run", "95 % interval"], ncol=1, loc="upper left",
              fontsize=17, handletextpad=0.4)
    fig.tight_layout()
    path = out / "misses_rboth.png"; fig.savefig(path); plt.close(fig)
    return path


def kernel_cpu3(results: Path, out: Path, plt) -> Path:
    ci = pd.read_csv(results / "phase6b" / "cpu_interference.csv")
    ci = ci[(ci.cpu == 3) & ci.series.isin(["B", "B-iso"])]
    per = ci.groupby(["series", "tier", "counter"]).per_s.mean().unstack()
    soft = per[["softirq_net_rx", "softirq_rcu", "softirq_sched", "softirq_timer"]].sum(axis=1)
    busy = pd.read_csv(results / "phase6b" / "realload_long.csv")
    busy = busy[busy.series.isin(["B", "B-iso"])].groupby(["series", "tier"]).busy_mean_cpu3.mean()
    tiers = ["rnet", "rdeploy", "rboth"]
    panels = [("Function-call interrupts (per s)", per["ipi_call"]),
              ("Softirqs (per s)", soft),
              ("Core 3 busy (%)", busy)]
    fig, axes = plt.subplots(1, 3, figsize=(16.6, 4.7), dpi=100)
    w = 0.36
    for ax, (title, data) in zip(axes, panels):
        for j, s in enumerate(["B", "B-iso"]):
            vals = [float(data.loc[(s, t)]) for t in tiers]
            xs = np.arange(len(tiers)) + (j - 0.5) * (w + 0.04)
            ax.bar(xs, vals, width=w, color=COLORS[s], label=LABELS[s], zorder=2)
            ax.text(xs[-1], vals[-1], f"{vals[-1]:.0f}", ha="center", va="bottom", fontsize=18, color=INK)
        ax.set_title(title, fontsize=20, color=INK, loc="left", pad=12)
        ax.set_xticks(range(len(tiers)), tiers)
        ax.grid(True, axis="y", color=GRID, lw=1); ax.set_axisbelow(True)
        ax.tick_params(axis="y", labelsize=17)
    axes[0].legend(loc="upper left", fontsize=17)
    fig.tight_layout(w_pad=2.5)
    path = out / "kernel_cpu3.png"; fig.savefig(path); plt.close(fig)
    return path


def mcu_priority(results: Path, out: Path, plt) -> Path:
    df = pd.read_csv(results / "phase5d" / "compare_long.csv")
    rows = [("C baseline stock", "Stock priority · no link"), ("C IPC stock", "Stock priority · with link"),
            ("C baseline tuned", "Tuned priority · no link"), ("C IPC tuned", "Tuned priority · with link")]
    stock, tuned = "#8A8F98", COLORS["C"]
    fig, ax = plt.subplots(figsize=(10.0, 5.2), dpi=100)
    rng = np.random.default_rng(1)
    for i, (series, _) in enumerate(rows):
        y = len(rows) - 1 - i
        v = df[df.series == series].wcl_us.to_numpy()
        c = stock if "stock" in series else tuned
        ax.plot(v, y + rng.uniform(-0.12, 0.12, v.size), "o", ms=10, color=c, alpha=0.75, mec="white", mew=1, zorder=3)
        ax.text(v.max() * 1.6, y, f"{v.min():.1f}–{v.max():.0f} µs" if v.max() < 100 else f"{v.min():.0f}–{v.max():.0f} µs",
                va="center", fontsize=18, color=INK)
    _deadline(ax, horizontal=False)
    ax.set_xscale("log"); ax.set_xlim(0.8, 8000)
    ax.set_xticks(*US_TICKS); ax.minorticks_off()
    ax.set_yticks(range(len(rows)), [r[1] for r in reversed(rows)])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.grid(True, axis="x", color=GRID, lw=1); ax.set_axisbelow(True)
    ax.set_xlabel("Worst-case lateness per run (all stress-ng tiers)")
    fig.tight_layout()
    path = out / "mcu_priority.png"; fig.savefig(path); plt.close(fig)
    return path


def chain(results: Path, out: Path, plt) -> Path:
    d = pd.read_csv(results / "phase6b" / "drive_long.csv")
    tiers = [("0", "Idle"), ("rnet", "rnet"), ("rdeploy", "rdeploy"), ("rboth", "rboth")]
    fig, ax = plt.subplots(figsize=(10.0, 4.6), dpi=100)
    for i, (t, name) in enumerate(tiers):
        y = len(tiers) - 1 - i
        r = d[d.tier == t]
        lo, hi, med = r.drive_seen_min_us.min() / 1000, r.drive_seen_max_us.max() / 1000, r.drive_seen_p50_us.mean() / 1000
        ax.plot([lo, hi], [y, y], color=COLORS["C"], lw=9, alpha=0.4, solid_capstyle="round")
        ax.plot(med, y, "o", ms=13, color=COLORS["C"], mec="white", mew=2, zorder=3)
        rtt = r.rtt_p99_us.max() / 1000
        ax.plot(rtt, y, "D", ms=12, color=COLORS["A"], mec="white", mew=1.5, zorder=3)
        ax.text(rtt + 0.4, y, f"{rtt:.1f} ms", va="center", fontsize=18, color=INK)
    ax.axvline(10, color=MUTED, lw=1.2, ls=(0, (2, 3)))
    ax.text(10.2, -0.75, "one tick (10 ms)", fontsize=16, color=MUTED, va="center")
    ax.set_xlim(0, 19)
    ax.set_yticks(range(len(tiers)), [n for _, n in reversed(tiers)])
    ax.set_ylim(-0.95, len(tiers) - 0.4)
    ax.grid(True, axis="x", color=GRID, lw=1); ax.set_axisbelow(True)
    ax.set_xlabel("Milliseconds")
    handles = [plt.Line2D([], [], lw=9, color=COLORS["C"], alpha=0.4),
               plt.Line2D([], [], marker="o", ls="", ms=12, color=COLORS["C"]),
               plt.Line2D([], [], marker="D", ls="", ms=11, color=COLORS["A"])]
    ax.legend(handles, ["tick → drive sees it (min–max)", "median", "Linux → MCU round trip (p99)"],
              ncol=2, loc="lower left", bbox_to_anchor=(-0.02, 1.0), fontsize=16, handletextpad=0.3,
              columnspacing=1.2)
    fig.tight_layout()
    path = out / "chain_delay.png"; fig.savefig(path); plt.close(fig)
    return path


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--results", type=Path, default=repo / "results")
    p.add_argument("--out", type=Path, default=repo / "results" / "slides")
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    plt = _plt()
    for fn in (synthetic, realload, misses, kernel_cpu3, mcu_priority, chain):
        print(f"wrote {fn(args.results, args.out, plt)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
