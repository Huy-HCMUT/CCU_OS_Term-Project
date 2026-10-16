#!/usr/bin/env python3
"""Wake-up lateness analysis for the A / B / C benchmark matrix.

Reads one CSV per run from a raw-results directory, computes the KPIs defined
in docs/Project_Scope_Statement.md §4.3.2, and writes a summary table plus the
figures listed in §5 (CDF curves, box plots) and a deadline-miss-ratio vs.
tolerance curve for the multi-tier tolerance discussion (issue #2).

File naming
-----------
    <config>_<stress>[_<tag>].csv        e.g. A_0.csv, B_100.csv, C_50_referee.csv

<config> is a single letter (A, B, C, ...), <stress> is the stress-ng level in
percent (0, 50, 100), and <tag> is free text. Files that share a config and a
stress level are pooled.

Accepted CSV layouts (column names are case-insensitive; '#' lines are comments)
--------------------------------------------------------------------------------
1. lateness_<unit>                       lateness already computed on the device
2. release_<unit>, wake_<unit>           lateness = wake - release
3. wake_<unit>                           only wake-up timestamps (e.g. DWT dumps
                                         or edges captured by an external referee
                                         board); the release schedule is
                                         reconstructed, see reconstruct_release()

<unit> is one of ns, us, ms, s, or cyc (raw cycle counts; needs --clock-hz).
An optional integer `cycle` column gives the cycle index k, so dropped samples
do not shift the schedule; otherwise the row index is used.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

NOMINAL_PERIOD_US = 10_000.0          # 10 ms control tick (§4.3.1)
DEFAULT_TOLERANCES_MS = (1.0, 0.2)    # coarse tier (§4.3.2) + precision tier (issue #2)
SEVERE_STARVATION_MS = 40.0           # §4.3.2 / §8

UNIT_TO_US = {"ns": 1e-3, "us": 1.0, "ms": 1e3, "s": 1e6}
FILENAME_RE = re.compile(
    r"^(?P<config>[A-Za-z])_(?:stress)?(?P<stress>\d+)(?:_(?P<tag>[\w.-]+))?\.csv$",
    re.IGNORECASE,
)

# Categorical slots in fixed order; the first three are CVD-validated as a set.
CONFIG_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#008300", "#6250d6", "#e34948"]
CONFIG_LABELS = {
    "A": "A · Linux CFS",
    "B": "B · Linux SCHED_FIFO",
    "C": "C · Zephyr (dual-OS)",
}
SURFACE = "#ffffff"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"


@dataclass
class Run:
    config: str
    stress: int
    path: Path
    lateness_us: np.ndarray
    period_us: np.ndarray
    source_format: str
    fitted_period_us: float | None = None
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def parse_filename(path: Path) -> tuple[str, int] | None:
    m = FILENAME_RE.match(path.name)
    if not m:
        return None
    return m.group("config").upper(), int(m.group("stress"))


def _find_column(columns: list[str], stem: str) -> tuple[str, str] | None:
    """Return (column name, unit) for the first column named <stem>_<unit>."""
    for col in columns:
        m = re.fullmatch(rf"{stem}_(ns|us|ms|s|cyc)", col.strip().lower())
        if m:
            return col, m.group(1)
    return None


def _to_us(values: pd.Series, unit: str, clock_hz: float | None, *,
           origin: float | int = 0, counter_bits: int = 32) -> np.ndarray:
    """Convert a column to microseconds, relative to `origin` (same unit).

    Subtracting the origin before the float conversion keeps sub-ns precision
    for large absolute timestamps (CLOCK_MONOTONIC in ns, cycle counters).
    Cycle counts are unwrapped first: the 32-bit DWT counter at 160 MHz wraps
    every 26.8 s, i.e. several times during a 10,000-cycle run.
    """
    raw = values.to_numpy()
    if unit == "cyc":
        if not clock_hz:
            raise ValueError("cycle-count columns (*_cyc) need --clock-hz")
        raw = raw.astype(np.int64)
        wraps = np.concatenate([[0], np.cumsum(np.diff(raw) < 0)])
        raw = raw + wraps * (1 << counter_bits)
        return (raw - origin).astype(np.float64) * (1e6 / clock_hz)
    if np.issubdtype(raw.dtype, np.integer):
        return (raw.astype(np.int64) - int(origin)).astype(np.float64) * UNIT_TO_US[unit]
    return (raw.astype(np.float64) - float(origin)) * UNIT_TO_US[unit]


def _cycle_index(df: pd.DataFrame) -> np.ndarray:
    for col in df.columns:
        if col.strip().lower() == "cycle":
            k = df[col].to_numpy(dtype=np.int64)
            return k - k[0]
    return np.arange(len(df), dtype=np.int64)


def reconstruct_release(wake_us: np.ndarray, k: np.ndarray, period_us: float | None
                        ) -> tuple[np.ndarray, float]:
    """Rebuild the release schedule R_k = t0 + k*T from wake times alone.

    T is the nominal period when given, else it is fitted by least squares
    (t_k on k). Fitting is needed when the timestamps come from a clock that is
    not the one driving the timer (e.g. an external referee board): a 50 ppm
    crystal mismatch is 0.5 µs per 10 ms cycle and would otherwise accumulate
    into several milliseconds of fake lateness over a 10,000-cycle run.

    t0 is placed so the earliest wake-up has zero lateness, i.e. lateness is
    measured relative to the best-case cycle. This is a lower bound on the true
    lateness (any constant offset common to all cycles is not observable).
    """
    if period_us is None:
        period_us = float(np.polyfit(k.astype(np.float64), wake_us, 1)[0])
    t0 = float(np.min(wake_us - k * period_us))
    return t0 + k * period_us, period_us


def load_run(path: Path, *, clock_hz: float | None = None, period_mode: str = "fit",
             counter_bits: int = 32) -> Run:
    parsed = parse_filename(path)
    if parsed is None:
        raise ValueError(f"{path.name}: expected <config>_<stress>[_<tag>].csv")
    config, stress = parsed

    df = pd.read_csv(path, comment="#", skipinitialspace=True)
    if df.empty:
        raise ValueError(f"{path.name}: no data rows")
    cols = list(df.columns)
    k = _cycle_index(df)
    fitted = None
    notes: list[str] = []

    conv = {"clock_hz": clock_hz, "counter_bits": counter_bits}
    if (lat := _find_column(cols, "lateness")) is not None:
        if lat[1] == "cyc":
            raise ValueError(f"{path.name}: lateness_cyc is not supported; convert on device "
                             "or log wake_cyc instead")
        lateness = _to_us(df[lat[0]], lat[1], **conv)
        wake = k * NOMINAL_PERIOD_US + lateness
        fmt = "lateness"
    elif (wk := _find_column(cols, "wake")) is not None:
        origin = df[wk[0]].iloc[0]
        rel = _find_column(cols, "release")
        if rel is not None:
            if rel[1] != wk[1]:
                raise ValueError(f"{path.name}: release and wake columns must share a unit")
            # Rebase both on the same origin so the difference stays exact.
            origin = min(origin, df[rel[0]].iloc[0])
            wake = _to_us(df[wk[0]], wk[1], origin=origin, **conv)
            release = _to_us(df[rel[0]], rel[1], origin=origin, **conv)
            lateness = wake - release
            fmt = "release+wake"
        else:
            wake = _to_us(df[wk[0]], wk[1], origin=origin, **conv)
            nominal = NOMINAL_PERIOD_US if period_mode == "nominal" else None
            release, period = reconstruct_release(wake, k, nominal)
            lateness = wake - release
            fmt = "wake-only"
            if nominal is None:
                fitted = period
                ppm = (period / NOMINAL_PERIOD_US - 1.0) * 1e6
                notes.append(f"fitted period {period:.4f} us ({ppm:+.1f} ppm)")
            notes.append("lateness relative to best-case cycle")
    else:
        raise ValueError(
            f"{path.name}: need a lateness_<unit>, wake_<unit> (+ release_<unit>) column; "
            f"got {cols}")

    period = np.diff(wake) / np.maximum(np.diff(k), 1)
    if np.any(np.diff(k) > 1):
        notes.append(f"{int(np.sum(np.diff(k) - 1))} cycle(s) missing from log")
    return Run(config, stress, path, lateness, period, fmt, fitted, notes)


def trim(run: Run, warmup: int, max_cycles: int | None) -> Run:
    end = None if max_cycles is None else warmup + max_cycles
    lat = run.lateness_us[warmup:end]
    # period[i] spans cycles i..i+1; keep the ones fully inside the window.
    per = run.period_us[warmup:None if end is None else end - 1]
    if len(lat) == 0:
        raise ValueError(f"{run.path.name}: no cycles left after --warmup {warmup}")
    if max_cycles is not None and len(lat) < max_cycles:
        run.notes.append(f"only {len(lat)} cycles after warm-up (wanted {max_cycles})")
    return Run(run.config, run.stress, run.path, lat, per, run.source_format,
               run.fitted_period_us, run.notes)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #

def dmr(lateness_us: np.ndarray, tolerance_ms: float) -> float:
    """Deadline miss ratio in percent: share of cycles with L_k > tolerance."""
    return float(np.mean(lateness_us > tolerance_ms * 1e3) * 100.0)


def tol_key(tolerance_ms: float) -> str:
    return f"{tolerance_ms * 1e3:g}us"


def summarize(config: str, stress: int, runs: list[Run],
              tolerances_ms: tuple[float, ...]) -> dict:
    lat = np.concatenate([r.lateness_us for r in runs])
    per = np.concatenate([r.period_us for r in runs])
    row = {
        "config": config,
        "stress_pct": stress,
        "files": ";".join(r.path.name for r in runs),
        "format": ";".join(sorted({r.source_format for r in runs})),
        "cycles": int(lat.size),
        "lateness_mean_us": lat.mean(),
        "jitter_std_us": lat.std(ddof=1) if lat.size > 1 else 0.0,
        "lateness_min_us": lat.min(),
        "lateness_p50_us": np.percentile(lat, 50),
        "lateness_p99_us": np.percentile(lat, 99),
        "lateness_p99_9_us": np.percentile(lat, 99.9),
        "wcl_max_us": lat.max(),
    }
    for tol in tolerances_ms:
        k = tol_key(tol)
        row[f"misses_{k}"] = int(np.sum(lat > tol * 1e3))
        row[f"dmr_{k}_pct"] = dmr(lat, tol)
    row["severe_starvation_40ms"] = int(np.sum(lat > SEVERE_STARVATION_MS * 1e3))
    row["period_mean_us"] = per.mean() if per.size else np.nan
    row["period_std_us"] = per.std(ddof=1) if per.size > 1 else np.nan
    row["notes"] = "; ".join(dict.fromkeys(n for r in runs for n in r.notes))
    return row


def format_markdown(summary: pd.DataFrame, tolerances_ms: tuple[float, ...]) -> str:
    head = ["Config", "Stress", "Cycles", "Mean (µs)", "σ_L (µs)", "p99.9 (µs)",
            "WCL (µs)"] + [f"DMR @ {tol:g} ms" for tol in tolerances_ms] + ["> 40 ms"]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join([" :--- "] * 2 + [" ---: "] * (len(head) - 2)) + "|"]
    for _, r in summary.iterrows():
        cells = [
            CONFIG_LABELS.get(r.config, r.config), f"{r.stress_pct}%", f"{r.cycles:,}",
            f"{r.lateness_mean_us:.3f}", f"{r.jitter_std_us:.3f}",
            f"{r.lateness_p99_9_us:.3f}", f"{r.wcl_max_us:.3f}",
        ] + [f"{r[f'dmr_{tol_key(t)}_pct']:.2f}%" for t in tolerances_ms] + [
            str(r.severe_starvation_40ms)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Plots
# --------------------------------------------------------------------------- #

def _style(plt) -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.size": 9,
        "text.color": TEXT_PRIMARY, "axes.labelcolor": TEXT_SECONDARY,
        "axes.edgecolor": GRID, "axes.linewidth": 0.8,
        "xtick.color": TEXT_SECONDARY, "ytick.color": TEXT_SECONDARY,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "lines.linewidth": 1.5,
    })


def _color_map(configs: list[str]) -> dict[str, str]:
    # Fixed slot per config letter so a missing config never repaints the rest.
    return {c: CONFIG_COLORS[(ord(c) - ord("A")) % len(CONFIG_COLORS)] for c in configs}


def _panels(plt, n: int, sharey: bool = True):
    fig, axes = plt.subplots(1, n, figsize=(3.4 * n, 3.0), sharey=sharey, squeeze=False)
    return fig, axes[0]


def plot_all(groups: dict[tuple[str, int], np.ndarray], tolerances_ms: tuple[float, ...],
             out_dir: Path, floor_us: float) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    _style(plt)
    configs = sorted({c for c, _ in groups})
    stresses = sorted({s for _, s in groups})
    colors = _color_map(configs)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    us_fmt = FuncFormatter(lambda v, _: f"{v:g}" if v < 1e3 else f"{v / 1e3:g} ms")

    def tol_lines(ax, vertical: bool, label: bool = False):
        for tol in tolerances_ms:
            (ax.axvline if vertical else ax.axhline)(
                tol * 1e3, color=TEXT_SECONDARY, lw=0.8, ls=(0, (3, 3)), zorder=3)
            if label:
                kw = ({"x": tol * 1e3, "y": 1.0, "transform": ax.get_xaxis_transform(),
                       "ha": "right", "va": "top", "rotation": 90} if vertical else
                      {"x": 1.0, "y": tol * 1e3, "transform": ax.get_yaxis_transform(),
                       "ha": "right", "va": "bottom"})
                ax.text(s=f"{tol:g} ms ", fontsize=7, color=TEXT_SECONDARY, **kw)

    def legend(fig, handles_from):
        handles, labels = handles_from.get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=len(labels),
                   bbox_to_anchor=(0.5, 1.02))

    def finish(fig, name, title, has_legend=True):
        fig.suptitle(title, y=1.10 if has_legend else 1.0, fontsize=10, color=TEXT_PRIMARY)
        fig.tight_layout()
        path = out_dir / name
        fig.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    # 1. Deadline miss ratio vs. tolerance (complementary CDF of lateness).
    fig, axes = _panels(plt, len(stresses))
    xs = np.logspace(np.log10(floor_us), np.log10(1e5), 400)
    # A log axis cannot show 0 %, so "no misses" is drawn on a floor one decade
    # below the resolution of the largest run (1 cycle in n) and labelled "0".
    zero = 10 ** np.floor(np.log10(100.0 / max(v.size for v in groups.values()))) / 10
    for ax, s in zip(axes, stresses):
        for c in configs:
            lat = groups.get((c, s))
            if lat is None:
                continue
            srt = np.sort(lat)
            miss = (1.0 - np.searchsorted(srt, xs, side="right") / srt.size) * 100.0
            ax.step(xs, np.maximum(miss, zero), where="post",
                    color=colors[c], label=CONFIG_LABELS.get(c, c))
        tol_lines(ax, vertical=True, label=ax is axes[-1])
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_ylim(zero * 0.7, 150)
        ax.xaxis.set_major_formatter(us_fmt)
        ax.set_title(f"{s}% stress", fontsize=9, color=TEXT_PRIMARY)
        ax.set_xlabel("Deadline tolerance (µs)")
    axes[0].set_ylabel("Deadline miss ratio (%)")
    axes[0].yaxis.set_major_formatter(
        FuncFormatter(lambda v, _: "0" if np.isclose(v, zero) else f"{v:g}"))
    legend(fig, axes[0])
    finish(fig, "dmr_vs_tolerance.png",
           "Deadline miss ratio vs. tolerance (dashed: "
           + ", ".join(f"{t:g} ms" for t in tolerances_ms) + " tiers)")

    # 2. Lateness CDF.
    fig, axes = _panels(plt, len(stresses))
    for ax, s in zip(axes, stresses):
        for c in configs:
            lat = groups.get((c, s))
            if lat is None:
                continue
            srt = np.sort(np.maximum(lat, floor_us))
            ax.step(srt, np.arange(1, srt.size + 1) / srt.size * 100.0, where="post",
                    color=colors[c], label=CONFIG_LABELS.get(c, c))
        tol_lines(ax, vertical=True)
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(us_fmt)
        ax.set_ylim(0, 100.5)
        ax.set_title(f"{s}% stress", fontsize=9, color=TEXT_PRIMARY)
        ax.set_xlabel("Wake-up lateness (µs)")
    axes[0].set_ylabel("Cycles (%)")
    legend(fig, axes[0])
    finish(fig, "lateness_cdf.png", "Cumulative distribution of wake-up lateness")

    # 3. Box plots, whiskers at p0.1 / p99.9, outliers beyond.
    fig, axes = _panels(plt, len(stresses))
    for ax, s in zip(axes, stresses):
        present = [c for c in configs if (c, s) in groups]
        data = [np.maximum(groups[(c, s)], floor_us) for c in present]
        bp = ax.boxplot(data, whis=(0.1, 99.9), widths=0.5, patch_artist=True,
                        medianprops={"color": TEXT_PRIMARY, "lw": 1.2},
                        whiskerprops={"color": TEXT_SECONDARY, "lw": 0.8},
                        capprops={"color": TEXT_SECONDARY, "lw": 0.8},
                        flierprops={"marker": "o", "markersize": 2.5, "alpha": 0.5,
                                    "markeredgewidth": 0})
        for patch, flier, c in zip(bp["boxes"], bp["fliers"], present):
            patch.set(facecolor=colors[c], edgecolor=colors[c], alpha=0.85)
            flier.set(markerfacecolor=colors[c])
        ax.set_xticks(range(1, len(present) + 1), present)
        tol_lines(ax, vertical=False, label=ax is axes[-1])
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(us_fmt)
        ax.set_title(f"{s}% stress", fontsize=9, color=TEXT_PRIMARY)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Wake-up lateness (µs)")
    finish(fig, "lateness_boxplot.png",
           "Wake-up lateness by configuration (whiskers: p0.1–p99.9)", has_legend=False)

    # 4. Lateness over time — exposes warm-up transients, drift and bursts.
    fig, axes = plt.subplots(len(configs), len(stresses),
                             figsize=(3.4 * len(stresses), 1.9 * len(configs)),
                             sharex=True, squeeze=False)
    for i, c in enumerate(configs):
        for j, s in enumerate(stresses):
            ax = axes[i][j]
            lat = groups.get((c, s))
            if lat is not None:
                ax.plot(np.arange(lat.size), np.maximum(lat, floor_us),
                        color=colors[c], lw=0.6)
                tol_lines(ax, vertical=False)
            ax.set_yscale("log")
            ax.yaxis.set_major_formatter(us_fmt)
            if i == 0:
                ax.set_title(f"{s}% stress", fontsize=9, color=TEXT_PRIMARY)
            if j == 0:
                ax.set_ylabel(f"{c}\nlateness (µs)")
            if i == len(configs) - 1:
                ax.set_xlabel("Cycle")
    finish(fig, "lateness_timeseries.png", "Wake-up lateness per cycle", has_legend=False)
    return written


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--raw", type=Path, default=repo / "results" / "raw",
                   help="directory of <config>_<stress>[_tag].csv files (default: results/raw)")
    p.add_argument("--out", type=Path, default=repo / "results",
                   help="output directory; plots go to <out>/plots (default: results)")
    p.add_argument("--tolerances", type=float, nargs="+", default=list(DEFAULT_TOLERANCES_MS),
                   metavar="MS", help="deadline tolerances in ms (default: 1.0 0.2)")
    p.add_argument("--warmup", type=int, default=0,
                   help="cycles to discard at the start of each run (default: 0)")
    p.add_argument("--max-cycles", type=int, default=None,
                   help="keep at most this many cycles after warm-up (e.g. 10000)")
    p.add_argument("--clock-hz", type=float, default=None,
                   help="clock rate for *_cyc columns (STM32U585 DWT: 160e6)")
    p.add_argument("--counter-bits", type=int, default=32,
                   help="width of the cycle counter behind *_cyc columns, for wrap-around "
                        "unwrapping (default: 32)")
    p.add_argument("--period-mode", choices=["fit", "nominal"], default="fit",
                   help="wake-only files: fit the period (default; removes clock drift "
                        "between boards) or assume exactly 10 ms")
    p.add_argument("--plot-floor-us", type=float, default=0.1,
                   help="lateness below this is drawn at this value on log axes (default: 0.1)")
    p.add_argument("--no-plots", action="store_true", help="only write the summary tables")
    args = p.parse_args(argv)

    files = sorted(args.raw.glob("*.csv"))
    if not files:
        print(f"no CSV files in {args.raw}", file=sys.stderr)
        return 1

    tolerances = tuple(sorted(set(args.tolerances), reverse=True))
    by_group: dict[tuple[str, int], list[Run]] = {}
    for f in files:
        if parse_filename(f) is None:
            print(f"skipping {f.name}: name is not <config>_<stress>[_tag].csv", file=sys.stderr)
            continue
        run = trim(load_run(f, clock_hz=args.clock_hz, period_mode=args.period_mode,
                            counter_bits=args.counter_bits),
                   args.warmup, args.max_cycles)
        by_group.setdefault((run.config, run.stress), []).append(run)
    if not by_group:
        print("no usable runs", file=sys.stderr)
        return 1

    rows = [summarize(c, s, runs, tolerances) for (c, s), runs in sorted(by_group.items())]
    summary = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.out / "summary.csv", index=False, float_format="%.4f")
    md = format_markdown(summary, tolerances)
    (args.out / "summary.md").write_text(md, encoding="utf-8")
    print(md)
    for r in rows:
        if r["notes"]:
            print(f"note [{r['config']} {r['stress_pct']}%]: {r['notes']}")

    if not args.no_plots:
        groups = {k: np.concatenate([r.lateness_us for r in v]) for k, v in by_group.items()}
        for path in plot_all(groups, tolerances, args.out / "plots", args.plot_floor_us):
            print(f"wrote {path}")
    print(f"wrote {args.out / 'summary.csv'}")
    print(f"wrote {args.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
