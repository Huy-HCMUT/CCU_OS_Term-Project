#!/usr/bin/env python3
"""Attribute late Config C pulses to Linux->MCU setpoint IPC arrivals."""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

CLOCK_MHZ = 160.0
LATE_THRESHOLD_US = 100.0

COLUMNS = [
    "folder",
    "tag",
    "n_intervals",
    "n_msg",
    "msg_base_rate",
    "n_late",
    "late_with_msg_share",
    "msg_late_share",
    "late_dev_p50_us",
    "late_dev_p90_us",
    "late_dev_max_us",
]


def find_ipc_dwt_tags(raw_dir: Path) -> list[str]:
    """Return sorted non-sanity tags that have both DWT and IPC seq CSVs."""
    prefix = "config_c_dwt_"
    suffix = ".csv"
    tags: list[str] = []
    for dwt_file in sorted(raw_dir.glob(f"{prefix}*{suffix}")):
        tag = dwt_file.name[len(prefix) : -len(suffix)]
        if tag.startswith("sanity"):
            continue
        seq_file = raw_dir / f"config_c_ipc_seq_{tag}.csv"
        if seq_file.exists():
            tags.append(tag)
    return sorted(tags)


def analyze_pair(folder_name: str, tag: str, dwt_path: Path, seq_path: Path) -> dict[str, str | int]:
    """Compute late-interval vs IPC-arrival attribution metrics for one run."""
    dwt_df = pd.read_csv(dwt_path, comment="#")
    seq_df = pd.read_csv(seq_path, comment="#")

    n = min(len(dwt_df), len(seq_df))
    period_us = dwt_df["dwt_delta_cyc"].iloc[1:n].to_numpy(dtype=np.float64) / CLOCK_MHZ
    dev = period_us - float(np.median(period_us))
    late = dev > LATE_THRESHOLD_US

    seqs = seq_df["applied_seq"].iloc[:n].to_numpy()
    msg = seqs[1:] != seqs[:-1]

    n_intervals = int(period_us.size)
    n_msg = int(np.sum(msg))
    n_late = int(np.sum(late))
    msg_base_rate = f"{(n_msg / n_intervals):.3f}" if n_intervals > 0 else ""

    if n_late > 0:
        late_with_msg_share = f"{float(np.mean(msg[late])):.3f}"
        late_devs = dev[late]
        late_dev_p50_us = f"{float(np.percentile(late_devs, 50)):.1f}"
        late_dev_p90_us = f"{float(np.percentile(late_devs, 90)):.1f}"
        late_dev_max_us = f"{float(np.max(late_devs)):.1f}"
    else:
        late_with_msg_share = ""
        late_dev_p50_us = ""
        late_dev_p90_us = ""
        late_dev_max_us = ""

    msg_late_share = f"{float(np.mean(late[msg])):.3f}" if n_msg > 0 else ""

    return {
        "folder": folder_name,
        "tag": tag,
        "n_intervals": n_intervals,
        "n_msg": n_msg,
        "msg_base_rate": msg_base_rate,
        "n_late": n_late,
        "late_with_msg_share": late_with_msg_share,
        "msg_late_share": msg_late_share,
        "late_dev_p50_us": late_dev_p50_us,
        "late_dev_p90_us": late_dev_p90_us,
        "late_dev_max_us": late_dev_max_us,
    }


def format_markdown_table(rows: list[dict[str, str | int]]) -> str:
    lines = [
        "# Config C IPC Latency Attribution",
        "",
        "Late interval definition: `period_us - median(period_us) > 100 µs`. "
        "`msg[k]` is true when `applied_seq[k] != applied_seq[k-1]`.",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in COLUMNS) + " |")
    lines.append("")
    return "\n".join(lines)


def run(raw_dirs: list[Path], out_md: Path) -> pd.DataFrame:
    rows: list[dict[str, str | int]] = []
    for raw_dir in raw_dirs:
        for tag in find_ipc_dwt_tags(raw_dir):
            rows.append(
                analyze_pair(
                    raw_dir.name,
                    tag,
                    raw_dir / f"config_c_dwt_{tag}.csv",
                    raw_dir / f"config_c_ipc_seq_{tag}.csv",
                )
            )
    if not rows:
        raise FileNotFoundError(f"No matching DWT + IPC seq pairs found in {raw_dirs}")

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
    parser.add_argument("--raw", nargs="+", type=Path, required=True, help="Input raw folders")
    parser.add_argument(
        "--out", type=Path, required=True, help="Output Markdown path (.csv written beside it)"
    )
    args = parser.parse_args(argv)
    run(args.raw, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

