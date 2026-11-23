#!/usr/bin/env python3
"""Replay recorded lateness as a video, for the demo video and the presentation.

Every point is a real measured cycle from the committed raw data: no simulation.
Lateness uses the same definition as compare_realload.py (L_rel, relative to the
run's best cycle; Config C with the period fitted). The first --max-cycles cycles
of each run are replayed side by side on one log-scale axis that scrolls in time,
with a running worst case and miss count per configuration.

    python benchmarks/analysis/replay_animation.py                 # rboth, run 1 -> MP4
    python benchmarks/analysis/replay_animation.py --still 400     # poster frame -> PNG

Writes results/replay/replay_<tier>_r<rep>.mp4 (needs ffmpeg) or .png with --still.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_latency import load_run  # noqa: E402

DEADLINE_US = 1000.0
PERIOD_S = 0.010
FLOOR_US = 0.5            # log axis cannot show 0: lateness below this is drawn here

BG = "#14213D"
INK = "#F7F6F2"
MUTED = "#9AA5BA"
GRID = "#2A3A5C"
SERIES = {  # label, colour (dark-background steps of the project palette)
    "A": ("A · Linux default", "#3987e5"),
    "B": ("B · SCHED_FIFO 90", "#ef7a4a"),
    "B-iso": ("B-iso · reserved core", "#9085e9"),
    "C": ("C · Zephyr MCU", "#1fc48a"),
}
TIER_NAMES = {
    "rboth": "network traffic + CNN (rboth)",
    "rdeploy": "CNN on the sensor stream (rdeploy)",
    "rnet": "bulk network traffic (rnet)",
}


def series_path(raw: Path, series: str, tier: str, rep: int) -> Path:
    if series == "C":
        folder = f"act_tuned_{tier}" + (f"_r{rep}" if rep > 1 else "")
        return raw / folder / f"C_0_act_tuned_{tier}.csv"
    name = {"A": "A_0", "B": "B_0", "B-iso": "B_0_iso"}[series]
    return raw / f"real_r{rep}" / f"{name}_{tier}.csv"


def load_series(path: Path, series: str) -> np.ndarray:
    """Lateness in µs relative to the run's best cycle, as in compare_realload.py."""
    if series == "C":
        return load_run(path, clock_hz=160e6, period_mode="fit").lateness_us
    df = pd.read_csv(path, comment="#", skipinitialspace=True)
    l_abs = df["lateness_ms"].to_numpy(dtype=np.float64) * 1000.0
    return l_abs - float(np.min(l_abs))


def running_stats(lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Worst case and miss count after each cycle."""
    return np.maximum.accumulate(lat), np.cumsum(lat > DEADLINE_US)


def _fmt_us(v: float) -> str:
    return f"{v / 1000:.2f} ms" if v >= 1000 else f"{v:.1f} µs"


def build(data: dict[str, np.ndarray], tier: str, rep: int, window: int, cycles_per_frame: int):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 18, "text.color": INK, "axes.labelcolor": MUTED,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID})
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.07, 0.14, 0.62, 0.66], facecolor=BG)
    ax.set_yscale("log")
    ax.set_ylim(FLOOR_US * 0.8, 3e4)
    ax.set_yticks([1, 10, 100, 1000, 10000])
    ax.set_yticklabels(["1 µs", "10 µs", "100 µs", "1 ms", "10 ms"])
    ax.grid(True, axis="y", color=GRID, lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.axhline(DEADLINE_US, color="#F59E5B", lw=2, ls=(0, (6, 4)), zorder=1)
    ax.text(1.0, DEADLINE_US * 1.12, "1 ms deadline", color="#F59E5B", fontsize=18,
            ha="right", va="bottom", transform=ax.get_yaxis_transform())
    ax.set_xlabel("Time in the run (s)")
    ax.set_ylabel("Lateness of each 10 ms tick")

    fig.text(0.07, 0.93, "Recorded data, replayed: the 10 ms loop under " + TIER_NAMES.get(tier, tier),
             fontsize=30, weight="bold", color=INK)
    fig.text(0.07, 0.885, f"Every dot is one measured cycle (run {rep}, first "
             f"{min(len(v) for v in data.values()):,} cycles of each configuration), played "
             f"{cycles_per_frame * 30 * PERIOD_S:.0f}× faster than real time",
             fontsize=19, color=MUTED)
    fig.text(0.07, 0.04, "Source: results/raw (Arduino UNO Q, Nov 2026) · lateness relative to each "
             "run's best cycle (below 0.5 µs drawn at 0.5 µs) · benchmarks/analysis/replay_animation.py", fontsize=14, color=MUTED)

    scat, cards = {}, {}
    y0 = 0.74
    for i, (s, lat) in enumerate(data.items()):
        label, color = SERIES[s]
        scat[s] = ax.scatter([], [], s=14, color=color, alpha=0.85, linewidths=0, label=label)
        y = y0 - i * 0.17
        fig.patches.append(matplotlib.patches.FancyBboxPatch(
            (0.73, y - 0.035), 0.24, 0.13, boxstyle="round,pad=0.005,rounding_size=0.01",
            transform=fig.transFigure, facecolor="#1C2B4D", edgecolor=color, lw=2))
        fig.text(0.745, y + 0.06, label, fontsize=20, weight="bold", color=INK)
        cards[s] = (fig.text(0.745, y + 0.012, "", fontsize=19, color=INK),
                    fig.text(0.745, y - 0.022, "", fontsize=19, color=MUTED))

    n = min(len(v) for v in data.values())
    stats = {s: running_stats(v[:n]) for s, v in data.items()}

    def draw(frame: int):
        end = min(n, (frame + 1) * cycles_per_frame)
        start = max(0, end - window)
        t = np.arange(start, end) * PERIOD_S
        for s, lat in data.items():
            y = np.maximum(lat[start:end], FLOOR_US)
            scat[s].set_offsets(np.column_stack([t, y]))
            worst, misses = stats[s]
            cards[s][0].set_text(f"worst so far  {_fmt_us(float(worst[end - 1]))}")
            cards[s][1].set_text(f"over 1 ms  {int(misses[end - 1]):,} of {end:,} ticks")
        ax.set_xlim(max(0.0, end * PERIOD_S - window * PERIOD_S), max(window, end) * PERIOD_S)
        return list(scat.values())

    frames = (n + cycles_per_frame - 1) // cycles_per_frame
    return fig, draw, frames


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--raw", type=Path, default=repo / "results" / "raw")
    p.add_argument("--out", type=Path, default=repo / "results" / "replay")
    p.add_argument("--tier", default="rboth", choices=sorted(TIER_NAMES))
    p.add_argument("--rep", type=int, default=1)
    p.add_argument("--series", nargs="+", default=["A", "B", "C"], choices=list(SERIES))
    p.add_argument("--max-cycles", type=int, default=10_000,
                   help="cycles replayed per configuration (Config C runs have 10,000)")
    p.add_argument("--cycles-per-frame", type=int, default=20, help="20 at 30 fps = 6x real time")
    p.add_argument("--window", type=int, default=1500, help="cycles visible at once (15 s)")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--still", type=int, default=None, metavar="FRAME",
                   help="write one frame as PNG instead of the video")
    args = p.parse_args(argv)

    data = {}
    for s in args.series:
        path = series_path(args.raw, s, args.tier, args.rep)
        if not path.exists():
            print(f"missing {path}", file=sys.stderr)
            return 1
        data[s] = load_series(path, s)[: args.max_cycles]

    fig, draw, frames = build(data, args.tier, args.rep, args.window, args.cycles_per_frame)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"replay_{args.tier}_r{args.rep}"
    if args.still is not None:
        draw(min(args.still, frames - 1))
        path = args.out / f"{stem}.png"
        fig.savefig(path, facecolor=BG)
    else:
        from matplotlib.animation import FFMpegWriter, FuncAnimation
        anim = FuncAnimation(fig, draw, frames=frames, blit=False)
        path = args.out / f"{stem}.mp4"
        anim.save(path, writer=FFMpegWriter(fps=args.fps, bitrate=4000,
                                            extra_args=["-pix_fmt", "yuv420p"]))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
