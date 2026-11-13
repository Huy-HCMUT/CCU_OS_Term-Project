#!/usr/bin/env python3
"""Measure periodic pulse-interval disturbances in Config C DWT logs."""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

CLOCK_MHZ = 160.0
DISTURB_THRESHOLD_US = 20.0

COLUMNS = [
    "file",
    "n_intervals",
    "median_period_us",
    "n_disturbed",
    "gap_set",
    "late_dev_median_us",
    "undisturbed_dev_std_us",
]


def analyze_dwt_file(path: Path, label: str | None = None) -> dict[str, str | int]:
    """Compute interval disturbance metrics from dwt_delta_cyc rows 1..end."""
    df = pd.read_csv(path, comment="#")
    cyc = df["dwt_delta_cyc"].iloc[1:].to_numpy(dtype=np.float64)
    period_us = cyc / CLOCK_MHZ
    median_period_us = float(np.median(period_us))
    dev_us = period_us - median_period_us

    disturbed = np.abs(dev_us) > DISTURB_THRESHOLD_US
    n_intervals = int(period_us.size)
    n_disturbed = int(np.sum(disturbed))

    disturbed_idx = np.flatnonzero(disturbed)
    if disturbed_idx.size >= 2:
        gaps = sorted({int(g) for g in np.diff(disturbed_idx)})
        gap_set = ";".join(str(g) for g in gaps)
    else:
        gap_set = ""

    late_devs = dev_us[disturbed & (dev_us > 0)]
    late_dev_median_us = f"{float(np.median(late_devs)):.1f}" if late_devs.size > 0 else ""

    rest = dev_us[~disturbed]
    if rest.size > 1:
        undisturbed_dev_std_us = f"{float(np.std(rest, ddof=1)):.2f}"
    elif rest.size == 1:
        undisturbed_dev_std_us = "0.00"
    else:
        undisturbed_dev_std_us = ""

    return {
        "file": label if label is not None else path.name,
        "n_intervals": n_intervals,
        "median_period_us": f"{median_period_us:.3f}",
        "n_disturbed": n_disturbed,
        "gap_set": gap_set,
        "late_dev_median_us": late_dev_median_us,
        "undisturbed_dev_std_us": undisturbed_dev_std_us,
    }


def collect_dwt_files(raw_dirs: list[Path]) -> list[tuple[Path, str]]:
    """Find non-sanity config_c_dwt_*.csv files, keeping folder prefix if names collide."""
    matched: list[Path] = []
    for raw_dir in raw_dirs:
        for p in sorted(raw_dir.glob("config_c_dwt_*.csv")):
            if "sanity" in p.name.lower():
                continue
            matched.append(p)

    names = [p.name for p in matched]
    has_duplicates = len(names) != len(set(names))
    return [
        (p, f"{p.parent.name}/{p.name}" if has_duplicates else p.name)
        for p in matched
    ]


def format_markdown_table(rows: list[dict[str, str | int]]) -> str:
    lines = [
        "# Config C Periodic Pulse-Displacement Pattern",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "| :--- | ---: | ---: | ---: | :--- | ---: | ---: |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in COLUMNS) + " |")
    lines.append("")
    return "\n".join(lines)


def run(raw_dirs: list[Path], out_md: Path) -> pd.DataFrame:
    files = collect_dwt_files(raw_dirs)
    if not files:
        raise FileNotFoundError(f"No matching config_c_dwt_*.csv files in {raw_dirs}")

    rows = [analyze_dwt_file(path, label=label) for path, label in files]
    df = pd.DataFrame(rows, columns=COLUMNS)

    out_md.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_md.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    out_md.write_text(format_markdown_table(rows), encoding="utf-8")
    print(f"Wrote {csv_path}")
    print(f"Wrote {out_md}")
    return df


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw", nargs="+", type=Path, required=True, help="One or more raw CSV folders"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output Markdown path (.csv written beside it)"
    )
    args = parser.parse_args(argv)
    run(args.raw, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

