#!/usr/bin/env python3
"""Cross-config Phase 5d comparison (A, B, B-iso, and Config C variants) under one relative-lateness definition."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_latency import load_run, parse_filename  # noqa: E402

SERIES_ORDER = [
    "A",
    "B",
    "B-iso",
    "C baseline stock",
    "C IPC stock",
    "C baseline tuned",
    "C IPC tuned",
]
TIERS = ["0", "50", "100", "allcore"]
TIER_LABELS = {
    "0": "0%",
    "50": "50%",
    "100": "100%",
    "allcore": "all-core",
}

SERIES_COLORS = {
    "A": "#2a78d6",
    "B": "#eb6834",
    "B-iso": "#eda100",
    "C baseline stock": "#6250d6",
    "C IPC stock": "#e34948",
    "C baseline tuned": "#1baf7a",
    "C IPC tuned": "#008300",
}

LINUX_DIR_RE = re.compile(r"^linux_r(?P<rep>\d+)$")
LINUX_FILE_RE = re.compile(r"^(?P<config>[AB])_(?P<stress>0|50|100)(?P<rest>.*)\.csv$")

CONFIG_C_DIR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^baseline_dwtref(?P<ac>_allcore)?(?:_r(?P<rep>\d+))?$"), "C baseline stock"),
    (re.compile(r"^ipc(?P<ac>_allcore)?(?:_r(?P<rep>\d+))?$"), "C IPC stock"),
    (re.compile(r"^baseline_tuned(?P<ac>_allcore)?(?:_r(?P<rep>\d+))?$"), "C baseline tuned"),
    (re.compile(r"^ipc_tuned(?P<ac>_allcore)?(?:_r(?P<rep>\d+))?$"), "C IPC tuned"),
]

LONG_COLUMNS = [
    "series",
    "tier",
    "rep",
    "file",
    "n",
    "sigma_us",
    "p999_us",
    "wcl_us",
    "dmr_1000_pct",
    "dmr_200_pct",
    "wcl_abs_us",
    "dmr_1000_abs_pct",
    "floor_us",
]


def _parse_linux_file(path: Path) -> tuple[str, str] | None:
    m = LINUX_FILE_RE.match(path.name)
    if not m:
        return None
    cfg = m.group("config").upper()
    stress = m.group("stress")
    stem = path.stem.lower()
    series = "B-iso" if (cfg == "B" and "_iso" in stem) else cfg
    tier = "allcore" if stem.endswith("_allcore") else stress
    return series, tier


def _summarize_run(
    *,
    series: str,
    tier: str,
    rep: int,
    rel_path: str,
    l_rel: np.ndarray,
    l_abs: np.ndarray | None = None,
) -> dict:
    n = int(l_rel.size)
    row = {
        "series": series,
        "tier": tier,
        "rep": rep,
        "file": rel_path,
        "n": n,
        "sigma_us": float(l_rel.std(ddof=1)) if n > 1 else 0.0,
        "p999_us": float(np.percentile(l_rel, 99.9)),
        "wcl_us": float(np.max(l_rel)),
        "dmr_1000_pct": float(np.mean(l_rel > 1000.0) * 100.0),
        "dmr_200_pct": float(np.mean(l_rel > 200.0) * 100.0),
        "wcl_abs_us": float(np.max(l_abs)) if l_abs is not None else np.nan,
        "dmr_1000_abs_pct": float(np.mean(l_abs > 1000.0) * 100.0) if l_abs is not None else np.nan,
        "floor_us": float(np.min(l_abs)) if l_abs is not None else np.nan,
        "_l_rel": l_rel,
    }
    return row


def _collect_runs(raw_dir: Path) -> tuple[list[dict], list[Path]]:
    records: list[dict] = []
    scanned_dirs: list[Path] = []
    if not raw_dir.exists():
        return records, scanned_dirs

    # Linux repeat folders: results/raw/linux_r<N>/
    linux_dirs: list[tuple[int, Path]] = []
    for entry in raw_dir.iterdir():
        if not entry.is_dir():
            continue
        m = LINUX_DIR_RE.fullmatch(entry.name)
        if m:
            linux_dirs.append((int(m.group("rep")), entry))
    for rep, folder in sorted(linux_dirs, key=lambda x: x[0]):
        scanned_dirs.append(folder)
        for csv_path in sorted(folder.glob("*.csv")):
            parsed = _parse_linux_file(csv_path)
            if parsed is None:
                continue
            series, tier = parsed
            df = pd.read_csv(csv_path, comment="#", skipinitialspace=True)
            if df.empty or "lateness_ms" not in df.columns:
                continue
            l_abs = df["lateness_ms"].to_numpy(dtype=np.float64) * 1000.0
            floor_us = float(np.min(l_abs))
            l_rel = l_abs - floor_us
            records.append(
                _summarize_run(
                    series=series,
                    tier=tier,
                    rep=rep,
                    rel_path=f"{folder.name}/{csv_path.name}",
                    l_rel=l_rel,
                    l_abs=l_abs,
                )
            )

    # Config C folders (excluding archive and unrelated folders via fullmatch)
    c_dirs: list[tuple[str, bool, int, Path]] = []
    for entry in raw_dir.iterdir():
        if not entry.is_dir():
            continue
        for pat, series_name in CONFIG_C_DIR_PATTERNS:
            m = pat.fullmatch(entry.name)
            if m:
                is_ac = bool(m.group("ac"))
                rep = int(m.group("rep")) if m.group("rep") else 1
                c_dirs.append((series_name, is_ac, rep, entry))
                break

    series_rank = {s: i for i, s in enumerate(SERIES_ORDER)}
    for series_name, is_ac, rep, folder in sorted(
        c_dirs, key=lambda x: (series_rank[x[0]], x[1], x[2], x[3].name)
    ):
        scanned_dirs.append(folder)
        for csv_path in sorted(folder.glob("C_*.csv")):
            parsed = parse_filename(csv_path)
            if parsed is None or parsed[0] != "C":
                continue
            run = load_run(csv_path, clock_hz=160e6, period_mode="fit")
            tier = "allcore" if (is_ac or csv_path.stem.lower().endswith("_allcore")) else str(run.stress)
            records.append(
                _summarize_run(
                    series=series_name,
                    tier=tier,
                    rep=rep,
                    rel_path=f"{folder.name}/{csv_path.name}",
                    l_rel=run.lateness_us,
                    l_abs=None,
                )
            )

    return records, scanned_dirs


def _parse_env_tier(path: Path) -> str | None:
    name = path.name
    if name.startswith("config_c_env_"):
        tag = name[len("config_c_env_") : -len(".txt")]
        if tag.startswith("sanity"):
            return None
        if "_allcore" in tag:
            return "allcore"
        m = re.match(r"^(0|50|100)(?:_|$)", tag)
        return m.group(1) if m else None
    if name.startswith("env_"):
        stem = name[len("env_") : -len(".txt")]
        if stem.endswith("_iso_allcore"):
            return "allcore (B-iso)"
        if stem.endswith("_allcore"):
            return "allcore"
        m = re.match(r"^[AB]_(0|50|100)(?:_|$)", stem)
        return m.group(1) if m else None
    return None


def _collect_env_loads(scanned_dirs: list[Path]) -> list[dict]:
    per_tier_runs: dict[str, list[dict[str, float]]] = {}
    kv_re = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")
    for folder in scanned_dirs:
        env_files = sorted(list(folder.glob("config_c_env_*.txt")) + list(folder.glob("env_*.txt")))
        for ef in env_files:
            tier = _parse_env_tier(ef)
            if tier is None:
                continue
            sample_vals: dict[str, list[float]] = {
                "stress_ng_procs": [],
                "busy_cpu0": [],
                "busy_cpu1": [],
                "busy_cpu2": [],
                "busy_cpu3": [],
            }
            for line in ef.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or not line.startswith("sample="):
                    continue
                kv = dict(kv_re.findall(line))
                if "stress_ng_procs" not in kv:
                    continue
                for k in sample_vals:
                    if k in kv:
                        try:
                            sample_vals[k].append(float(kv[k]))
                        except ValueError:
                            pass
            if sample_vals["stress_ng_procs"]:
                run_med = {
                    k: float(np.median(v)) for k, v in sample_vals.items() if v
                }
                per_tier_runs.setdefault(tier, []).append(run_med)

    rows: list[dict] = []
    tier_order = ["0", "50", "100", "allcore", "allcore (B-iso)"]
    for tier in tier_order:
        runs = per_tier_runs.get(tier, [])
        if not runs:
            continue
        row = {"tier": TIER_LABELS.get(tier, tier), "n_env_runs": len(runs)}
        for k in ("stress_ng_procs", "busy_cpu0", "busy_cpu1", "busy_cpu2", "busy_cpu3"):
            vals = [r[k] for r in runs if k in r]
            row[k] = float(np.median(vals)) if vals else np.nan
        rows.append(row)
    return rows


def _fmt_range(vals: np.ndarray, decimals: int) -> str:
    fmt = f".{decimals}f"
    return f"{float(np.mean(vals)):{fmt}} [{float(np.min(vals)):{fmt}}–{float(np.max(vals)):{fmt}}]"


def _build_markdown(long_df: pd.DataFrame, env_rows: list[dict]) -> str:
    headers = ["Series"]
    aligns = [":---"]
    for t in TIERS:
        tl = TIER_LABELS[t]
        headers.extend(
            [
                f"{tl} n",
                f"{tl} WCL µs mean [min–max]",
                f"{tl} σ_L µs mean",
                f"{tl} DMR@1 ms max %",
            ]
        )
        aligns.extend(["---:", "---:", "---:", "---:"])

    lines = [
        "# Phase 5d Cross-Configuration Comparison",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(aligns) + " |",
    ]

    for series in SERIES_ORDER:
        sdf_s = long_df[long_df["series"] == series]
        cells = [series]
        for t in TIERS:
            sdf = sdf_s[sdf_s["tier"] == t]
            if sdf.empty:
                cells.extend(["0", "—", "—", "—"])
            else:
                wcl_str = _fmt_range(sdf["wcl_us"].to_numpy(dtype=float), 1)
                sigma_str = f"{float(np.mean(sdf['sigma_us'].to_numpy(dtype=float))):.1f}"
                dmr_str = f"{float(np.max(sdf['dmr_1000_pct'].to_numpy(dtype=float))):.2f}"
                cells.extend([str(len(sdf)), wcl_str, sigma_str, dmr_str])
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "**Relative lateness definition:** For Linux runs (`A`, `B`, `B-iso`), relative lateness is "
            "`L_rel = L_abs - min(L_abs)` within each run (wake-up floor `floor_us = min(L_abs)` subtracted). "
            "For Config C runs, lateness is wake-only (`wake_cyc` @ 160 MHz) relative to each run's best-case cycle "
            "using a least-squares fitted period (`analyze_latency.load_run(..., period_mode='fit')`).",
            "",
            "**Additional Linux columns:** Absolute Linux metrics (`wcl_abs_us`, `dmr_1000_abs_pct`) and each run's "
            "wake-up floor (`floor_us`) are recorded in `compare_long.csv`.",
            "",
            "**Excluded runs:** Phase 2 single runs (`results/raw/A_*.csv`, `results/raw/B_*.csv`) are not included "
            "here because they used an earlier binary logging per-process `getrusage(RUSAGE_SELF)` counters; "
            "they remain in `results/summary.*`.",
            "",
        ]
    )

    if env_rows:
        lines.extend(
            [
                "**Measured Linux load per tier (median across runs from `config_c_env_*.txt` / `env_*.txt`):**",
                "",
                "| Tier | env files | stress-ng procs | cpu0 % | cpu1 % | cpu2 % | cpu3 % |",
                "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for er in env_rows:
            lines.append(
                f"| {er['tier']} | {er['n_env_runs']} | {er['stress_ng_procs']:.0f} | "
                f"{er['busy_cpu0']:.1f} | {er['busy_cpu1']:.1f} | {er['busy_cpu2']:.1f} | {er['busy_cpu3']:.1f} |"
            )
        lines.append("")
    else:
        lines.append("**Measured Linux load per tier:** No `config_c_env_*.txt` or `env_*.txt` files found in the scanned folders.")
        lines.append("")

    return "\n".join(lines)


def _plot_charts(records: list[dict], out_dir: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update(
        {
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",
            "font.size": 9,
            "axes.grid": True,
            "grid.color": "#e4e3df",
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )

    us_fmt = FuncFormatter(lambda v, _: f"{v:g} µs" if v < 1e3 else f"{v / 1e3:g} ms")
    written: list[Path] = []

    def plot_cdf_tier(tier_key: str, out_name: str, title: str) -> None:
        fig, ax = plt.subplots(figsize=(6.4, 4.0))
        tier_recs = [r for r in records if r["tier"] == tier_key]
        seen_series: set[str] = set()
        for r in tier_recs:
            s = r["series"]
            label = s if s not in seen_series else "_nolegend_"
            seen_series.add(s)
            srt = np.sort(np.maximum(r["_l_rel"], 0.1))
            y = np.arange(1, srt.size + 1) / srt.size * 100.0
            ax.step(
                srt,
                y,
                where="post",
                color=SERIES_COLORS.get(s, "#333333"),
                lw=1.3,
                alpha=0.85,
                label=label,
            )
        ax.axvline(1000.0, color="#52514e", lw=1.0, ls="--")
        ax.text(1000.0, 98.0, " 1 ms deadline", fontsize=8, color="#52514e", va="top", ha="left")
        ax.set_xscale("log")
        ax.set_xlim(left=0.1)
        if not tier_recs:
            ax.set_xlim(0.1, 2000.0)
            ax.text(
                0.5,
                0.5,
                f"No runs available for {TIER_LABELS[tier_key]} tier",
                transform=ax.transAxes,
                ha="center",
                va="center",
                color="#52514e",
            )
        ax.xaxis.set_major_formatter(us_fmt)
        ax.set_ylim(0, 100.5)
        ax.set_xlabel("Relative wake-up lateness")
        ax.set_ylabel("Cycles (%)")
        ax.set_title(title, fontsize=10)
        if seen_series:
            ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()
        out_path = out_dir / out_name
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        written.append(out_path)

    plot_cdf_tier("100", "cdf_100.png", "Empirical CDF of relative wake-up lateness (100% core-0 tier)")
    plot_cdf_tier("allcore", "cdf_allcore.png", "Empirical CDF of relative wake-up lateness (all-core tier)")

    # WCL by tier scatter plot (one point per run, y log scale)
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    tier_idx = {t: i for i, t in enumerate(TIERS)}
    series_offsets = np.linspace(-0.24, 0.24, len(SERIES_ORDER))
    offset_map = {s: float(series_offsets[i]) for i, s in enumerate(SERIES_ORDER)}

    has_points = False
    for s in SERIES_ORDER:
        s_recs = [r for r in records if r["series"] == s]
        if not s_recs:
            continue
        has_points = True
        xs = [tier_idx[r["tier"]] + offset_map[s] for r in s_recs]
        ys = [max(float(r["wcl_us"]), 0.1) for r in s_recs]
        ax.scatter(
            xs,
            ys,
            color=SERIES_COLORS.get(s, "#333333"),
            label=s,
            s=36,
            alpha=0.85,
            edgecolors="#ffffff",
            linewidths=0.4,
            zorder=4,
        )

    ax.axhline(1000.0, color="#52514e", lw=1.0, ls="--", zorder=2)
    ax.text(len(TIERS) - 0.55, 1000.0, "1 ms deadline", fontsize=8, color="#52514e", va="bottom", ha="right")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(us_fmt)
    ax.set_xticks(range(len(TIERS)), [TIER_LABELS[t] for t in TIERS])
    ax.set_xlim(-0.5, len(TIERS) - 0.5)
    ax.set_xlabel("Stress tier")
    ax.set_ylabel("Worst-case relative lateness")
    ax.set_title("Worst-case relative lateness per run across stress tiers", fontsize=10)
    if has_points:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=8, ncol=4)
    fig.tight_layout()
    wcl_path = out_dir / "wcl_by_tier.png"
    fig.savefig(wcl_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    written.append(wcl_path)
    return written


def compare(raw_dir: Path, out_dir: Path) -> tuple[pd.DataFrame, str, list[Path]]:
    records, scanned_dirs = _collect_runs(raw_dir)
    env_rows = _collect_env_loads(scanned_dirs)

    long_rows = [{k: r[k] for k in LONG_COLUMNS} for r in records]
    long_df = pd.DataFrame(long_rows, columns=LONG_COLUMNS)

    out_dir.mkdir(parents=True, exist_ok=True)
    long_csv = out_dir / "compare_long.csv"
    long_df.to_csv(long_csv, index=False, float_format="%.4f")

    md_text = _build_markdown(long_df, env_rows)
    md_path = out_dir / "compare_configs.md"
    md_path.write_text(md_text, encoding="utf-8")

    charts = _plot_charts(records, out_dir)
    print(f"Wrote {long_csv}")
    print(f"Wrote {md_path}")
    for c in charts:
        print(f"Wrote {c}")
    return long_df, md_text, charts


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=repo / "results" / "raw")
    parser.add_argument("--out", type=Path, default=repo / "results" / "phase5d")
    args = parser.parse_args(argv)
    compare(args.raw, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

