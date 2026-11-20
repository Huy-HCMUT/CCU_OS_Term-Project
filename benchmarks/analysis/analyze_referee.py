#!/usr/bin/env python3
"""
analyze_referee.py
Phase 5: Compare referee period measurements against DUT internal DWT timestamps.

Note:
Both mean periods are measured in each board's own CPU-clock units (at nominal 160 MHz),
so ref_vs_dut_ppm represents the inter-board offset after the referee's own cycle loss (if any).
It is not an offset against true (SI) time.
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def analyze_tag(tag: str, dwt_path: Path, ref_path: Path) -> dict:
    dwt_df = pd.read_csv(dwt_path, comment="#").iloc[1:]
    ref_df = pd.read_csv(ref_path, comment="#").iloc[1:]

    n_dut = len(dwt_df)
    n_ref = len(ref_df)

    dwt_periods_us = dwt_df["dwt_delta_cyc"] / 160.0
    dut_mean = float(dwt_periods_us.mean()) if n_dut > 0 else float("nan")

    if "interval_cyc" in ref_df.columns:
        ref_periods_us = ref_df["interval_cyc"] / 160.0
        referee_clock = "dwt"
    else:
        ref_periods_us = ref_df["interval_us"].astype(float)
        referee_clock = "k_cycle_us"

    ref_mean = float(ref_periods_us.mean()) if n_ref > 0 else float("nan")
    ref_std = float(ref_periods_us.std()) if n_ref > 1 else 0.0
    ref_max_abs_jitter = float(np.max(np.abs(ref_periods_us - 10000.0))) if n_ref > 0 else float("nan")
    ref_misses = int(ref_df["is_miss"].astype(int).sum()) if "is_miss" in ref_df else 0

    if not np.isnan(dut_mean) and not np.isnan(ref_mean) and dut_mean != 0:
        ref_vs_dut_ppm = float((ref_mean / dut_mean - 1.0) * 1e6)
    else:
        ref_vs_dut_ppm = float("nan")

    return {
        "tag": tag,
        "referee_clock": referee_clock,
        "n_dut": n_dut,
        "n_ref": n_ref,
        "dut_period_mean_us": dut_mean,
        "ref_period_mean_us": ref_mean,
        "ref_vs_dut_ppm": ref_vs_dut_ppm,
        "ref_period_std_us": ref_std,
        "ref_max_abs_jitter_us": ref_max_abs_jitter,
        "ref_misses": ref_misses,
    }


def find_tags(raw_dir: Path) -> list[str]:
    tags = []
    prefix = "config_c_dwt_"
    suffix = ".csv"
    for dwt_file in raw_dir.glob(f"{prefix}*{suffix}"):
        tag = dwt_file.name[len(prefix) : -len(suffix)]
        ref_file = raw_dir / f"config_c_referee_{tag}.csv"
        if ref_file.exists():
            tags.append(tag)
    return sorted(tags)


def df_to_markdown(df: pd.DataFrame) -> str:
    headers = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join([":---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        row_vals = []
        for h in headers:
            v = row[h]
            if h in ("dut_period_mean_us", "ref_period_mean_us", "ref_period_std_us", "ref_max_abs_jitter_us"):
                row_vals.append(f"{v:.4f}")
            elif h == "ref_vs_dut_ppm":
                row_vals.append(f"{v:.2f}")
            else:
                row_vals.append(str(v))
        lines.append("| " + " | ".join(row_vals) + " |")
    return "\n".join(lines)


def run_comparison(raw_dir: Path, out_md_path: Path):
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    tags = find_tags(raw_dir)
    if not tags:
        print(f"No matching DWT/Referee paired files in {raw_dir}")
        return

    results = []
    for tag in tags:
        dwt_path = raw_dir / f"config_c_dwt_{tag}.csv"
        ref_path = raw_dir / f"config_c_referee_{tag}.csv"
        res = analyze_tag(tag, dwt_path, ref_path)
        results.append(res)

    cols = [
        "tag",
        "referee_clock",
        "n_dut",
        "n_ref",
        "dut_period_mean_us",
        "ref_period_mean_us",
        "ref_vs_dut_ppm",
        "ref_period_std_us",
        "ref_max_abs_jitter_us",
        "ref_misses",
    ]
    df = pd.DataFrame(results)[cols]

    csv_path = out_md_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False, float_format="%.4f")
    print(f"Saved {csv_path}")

    with open(out_md_path, "w") as f:
        f.write("# Referee vs DUT Clock Comparison Summary\n\n")
        f.write(
            "> Both means are in each board's own CPU-clock units. "
            "`ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). "
            "It is not an offset against true SI time.\n\n"
        )
        f.write(df_to_markdown(df))
        f.write("\n")
    print(f"Saved {out_md_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare Referee vs DUT clock periods")
    parser.add_argument("--raw", type=Path, required=True, help="Input raw CSV folder")
    parser.add_argument("--out", type=Path, required=True, help="Output markdown path (.csv written beside it)")
    args = parser.parse_args()

    run_comparison(args.raw.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()

