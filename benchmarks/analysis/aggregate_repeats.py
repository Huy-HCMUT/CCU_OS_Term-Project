#!/usr/bin/env python3
"""Aggregate per-run Config C summary.csv metrics across Phase 5b repeats."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import numpy as np
import pandas as pd

VARIANTS = [
    ("baseline, stock", "baseline_dwtref"),
    ("IPC, stock", "ipc"),
    ("baseline, tuned", "baseline_tuned"),
    ("IPC, tuned", "ipc_tuned"),
]

LONG_COLUMNS = [
    "variant",
    "rep",
    "stress_pct",
    "cycles",
    "jitter_std_us",
    "lateness_p99_9_us",
    "wcl_max_us",
    "dmr_1000us_pct",
    "dmr_200us_pct",
]

SUMMARY_HEADERS = [
    "Variant",
    "Stress",
    "n runs",
    "σ_L (µs) mean [min–max]",
    "p99.9 (µs) mean [min–max]",
    "WCL (µs) mean [min–max]",
    "DMR @ 1 ms max (%)",
    "DMR @ 0.2 ms (%) mean [min–max]",
]


def find_variant_folders(results_dir: Path, base: str) -> list[tuple[int, Path]]:
    """Return sorted (rep, folder) pairs under results_dir matching ^<base>(_r<rep>)?$."""
    pattern = re.compile(rf"^{re.escape(base)}(?:_r(?P<rep>\d+))?$")
    matched: list[tuple[int, Path]] = []
    if not results_dir.exists():
        return matched
    for entry in results_dir.iterdir():
        if not entry.is_dir():
            continue
        m = pattern.fullmatch(entry.name)
        if not m:
            continue
        rep = int(m.group("rep")) if m.group("rep") else 1
        matched.append((rep, entry))
    return sorted(matched, key=lambda item: item[0])


def _fmt_range(vals: np.ndarray, decimals: int) -> str:
    fmt = f".{decimals}f"
    mean_v = float(np.mean(vals))
    min_v = float(np.min(vals))
    max_v = float(np.max(vals))
    return f"{mean_v:{fmt}} [{min_v:{fmt}}–{max_v:{fmt}}]"


def aggregate(results_dir: Path, out_dir: Path) -> tuple[pd.DataFrame, str]:
    long_rows: list[dict] = []
    missing_variants: list[str] = []

    for label, base in VARIANTS:
        folders = find_variant_folders(results_dir, base)
        loaded_any = False
        for rep, folder in folders:
            summary_csv = folder / "summary.csv"
            if not summary_csv.exists():
                continue
            df = pd.read_csv(summary_csv)
            c_rows = df[df["config"].astype(str).str.upper() == "C"]
            for _, row in c_rows.iterrows():
                long_rows.append(
                    {
                        "variant": label,
                        "rep": rep,
                        "stress_pct": int(row["stress_pct"]),
                        "cycles": int(row["cycles"]),
                        "jitter_std_us": float(row["jitter_std_us"]),
                        "lateness_p99_9_us": float(row["lateness_p99_9_us"]),
                        "wcl_max_us": float(row["wcl_max_us"]),
                        "dmr_1000us_pct": float(row["dmr_1000us_pct"]),
                        "dmr_200us_pct": float(row["dmr_200us_pct"]),
                    }
                )
                loaded_any = True
        if not loaded_any:
            missing_variants.append(label)

    long_df = pd.DataFrame(long_rows, columns=LONG_COLUMNS)
    out_dir.mkdir(parents=True, exist_ok=True)
    long_csv = out_dir / "repeats_long.csv"
    long_df.to_csv(long_csv, index=False, float_format="%.4f")

    md_lines = [
        "# Phase 5b Config C Repeats Summary",
        "",
        "| " + " | ".join(SUMMARY_HEADERS) + " |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for label, _ in VARIANTS:
        if label in missing_variants:
            continue
        vdf = long_df[long_df["variant"] == label]
        for stress in (0, 50, 100):
            sdf = vdf[vdf["stress_pct"] == stress]
            if sdf.empty:
                continue
            n_runs = int(len(sdf))
            row = [
                label,
                f"{stress}%",
                str(n_runs),
                _fmt_range(sdf["jitter_std_us"].to_numpy(dtype=float), 1),
                _fmt_range(sdf["lateness_p99_9_us"].to_numpy(dtype=float), 1),
                _fmt_range(sdf["wcl_max_us"].to_numpy(dtype=float), 1),
                f"{float(np.max(sdf['dmr_1000us_pct'].to_numpy(dtype=float))):.2f}",
                _fmt_range(sdf["dmr_200us_pct"].to_numpy(dtype=float), 2),
            ]
            md_lines.append("| " + " | ".join(row) + " |")

    md_lines.append("")
    if missing_variants:
        md_lines.append(f"Missing variants (not run): {', '.join(missing_variants)}.")
        md_lines.append("")
    md_lines.append(
        "Each run is analysed separately (period fitted per run, lateness relative to that run's best cycle); "
        "mean/min/max are across runs, cycles are not pooled."
    )
    md_lines.append("")
    md_text = "\n".join(md_lines)
    md_path = out_dir / "repeats_summary.md"
    md_path.write_text(md_text, encoding="utf-8")
    print(f"Wrote {long_csv}")
    print(f"Wrote {md_path}")
    return long_df, md_text


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=repo / "results")
    parser.add_argument("--out", type=Path, default=repo / "results" / "phase5b")
    args = parser.parse_args(argv)
    aggregate(args.results, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

