#!/usr/bin/env python3
"""Compare Config C Phase 4.5 baseline, DWT-referee re-run, and Phase 5 IPC."""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


def load_c_by_stress(csv_path: Path) -> dict[int, pd.Series]:
    df = pd.read_csv(csv_path)
    c_rows = df[df["config"].astype(str).str.upper() == "C"]
    return {int(row["stress_pct"]): row for _, row in c_rows.iterrows()}


def build_table(
    p45_csv: Path,
    rerun_csv: Path,
    ipc_csv: Path,
) -> str:
    p45 = load_c_by_stress(p45_csv)
    rerun = load_c_by_stress(rerun_csv)
    ipc = load_c_by_stress(ipc_csv)

    headers = [
        "Stress",
        "σ_L (µs)",
        "p99.9 (µs)",
        "WCL (µs)",
        "DMR @ 1 ms",
        "ΔWCL IPC − re-run (µs)",
    ]
    lines = [
        "# Config C Baseline vs. IPC Comparison",
        "",
        "| " + " | ".join(headers) + " |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for stress in (0, 50, 100):
        r_p45 = p45[stress]
        r_re = rerun[stress]
        r_ipc = ipc[stress]

        def fmt_triple(col: str, suffix: str = "") -> str:
            return (
                f"{float(r_p45[col]):.2f}{suffix} / "
                f"{float(r_re[col]):.2f}{suffix} / "
                f"{float(r_ipc[col]):.2f}{suffix}"
            )

        delta_wcl = float(r_ipc["wcl_max_us"]) - float(r_re["wcl_max_us"])
        row = [
            f"{stress}%",
            fmt_triple("jitter_std_us"),
            fmt_triple("lateness_p99_9_us"),
            fmt_triple("wcl_max_us"),
            fmt_triple("dmr_1000us_pct", "%"),
            f"{delta_wcl:+.2f}",
        ]
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "Cells show `P4.5 / re-run / IPC`.",
            "",
            "P4.5 = Config C baseline (no IPC), original runs. "
            "Re-run = same sketch, DWT-based referee. "
            "IPC = Phase 5. Same timing loop and stress-ng commands; "
            "lateness is wake-only, relative to the best cycle, period fitted "
            "(see benchmarks/analysis/README.md); one run per condition.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p45", type=Path, default=repo / "results" / "summary.csv")
    parser.add_argument(
        "--rerun", type=Path, default=repo / "results" / "baseline_dwtref" / "summary.csv"
    )
    parser.add_argument("--ipc", type=Path, default=repo / "results" / "ipc" / "summary.csv")
    parser.add_argument(
        "--out",
        type=Path,
        default=repo / "results" / "ipc" / "compare_baseline_vs_ipc.md",
    )
    args = parser.parse_args(argv)

    md = build_table(args.p45, args.rerun, args.ipc)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

