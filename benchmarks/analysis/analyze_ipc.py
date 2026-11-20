#!/usr/bin/env python3
"""
analyze_ipc.py
Phase 5: Analyze Linux-to-MCU setpoint IPC telemetry.
Evaluates packet delivery, round-trip time, sequence staleness/age, and setpoint consistency.
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def parse_rx_count_from_header(seq_path: Path) -> int:
    """rx_count from the '# rx_count=<n>' first line; -1 if missing or not an integer."""
    with open(seq_path, "r") as f:
        first_line = f.readline().strip()
    if not first_line.startswith("#") or "rx_count=" not in first_line:
        return -1
    tokens = first_line.split("rx_count=", 1)[1].split()
    if not tokens:
        return -1
    try:
        return int(tokens[0])
    except ValueError:
        return -1


def analyze_tag(tag: str, seq_path: Path, sender_path: Path) -> dict:
    rx_count = parse_rx_count_from_header(seq_path)
    seq_df = pd.read_csv(seq_path, comment="#")
    sender_df = pd.read_csv(sender_path, comment="#")

    cycles = len(seq_df)
    sent = len(sender_df)
    ok_mask = sender_df["status"] == "ok"
    sent_ok = int(ok_mask.sum())
    send_errors = sent - sent_ok
    skipped_slots = int(sender_df["skipped_after"].sum()) if "skipped_after" in sender_df else 0

    applied_seqs = seq_df["applied_seq"].to_numpy()
    pos_indices = np.where(applied_seqs > 0)[0]
    if len(pos_indices) > 0:
        first_cycle_with_ipc = int(pos_indices[0])
        pos_applied = applied_seqs[pos_indices]
        distinct_applied = int(len(np.unique(pos_applied)))
        min_applied = int(np.min(pos_applied))
        max_applied = int(np.max(pos_applied))

        # unobserved_ok: ok seqs with min(applied>0) <= seq <= max(applied) that never appear in applied_seq
        ok_seqs = sender_df.loc[ok_mask, "seq"].to_numpy()
        candidate_ok = ok_seqs[(ok_seqs >= min_applied) & (ok_seqs <= max_applied)]
        applied_set = set(pos_applied)
        unobserved_ok = int(sum(1 for s in candidate_ok if s not in applied_set))

        # age calculation from first_cycle_with_ipc on
        # age = cycle - the first cycle at which the current applied_seq appeared
        first_seen = {}
        for c, s in enumerate(applied_seqs):
            if s not in first_seen:
                first_seen[s] = c

        ages = [c - first_seen[applied_seqs[c]] for c in range(first_cycle_with_ipc, cycles)]
        age_p50_cyc = float(np.percentile(ages, 50))
        age_p99_cyc = float(np.percentile(ages, 99))
        age_max_cyc = float(np.max(ages))
    else:
        first_cycle_with_ipc = -1
        distinct_applied = 0
        unobserved_ok = 0
        age_p50_cyc = float("nan")
        age_p99_cyc = float("nan")
        age_max_cyc = float("nan")

    # setpoint_mismatch: applied rows whose applied_setpoint_pct differs from sender's setpoint_pct
    # plus applied seqs missing from the sender file
    sender_map = dict(zip(sender_df["seq"], sender_df["setpoint_pct"]))
    setpoint_mismatch = 0
    for _, row in seq_df.iterrows():
        s = int(row["applied_seq"])
        if s > 0:
            if s not in sender_map or row["applied_setpoint_pct"] != sender_map[s]:
                setpoint_mismatch += 1

    # RTT statistics over ok rows
    ok_rtts = sender_df.loc[ok_mask, "rtt_us"].to_numpy(dtype=float)
    if len(ok_rtts) > 0:
        rtt_p50_us = float(np.percentile(ok_rtts, 50))
        rtt_p99_us = float(np.percentile(ok_rtts, 99))
        rtt_max_us = float(np.max(ok_rtts))
    else:
        rtt_p50_us = float("nan")
        rtt_p99_us = float("nan")
        rtt_max_us = float("nan")

    return {
        "tag": tag,
        "cycles": cycles,
        "sent": sent,
        "sent_ok": sent_ok,
        "send_errors": send_errors,
        "skipped_slots": skipped_slots,
        "rx_count": rx_count,
        "first_cycle_with_ipc": first_cycle_with_ipc,
        "distinct_applied": distinct_applied,
        "unobserved_ok": unobserved_ok,
        "setpoint_mismatch": setpoint_mismatch,
        "age_p50_cyc": age_p50_cyc,
        "age_p99_cyc": age_p99_cyc,
        "age_max_cyc": age_max_cyc,
        "rtt_p50_us": rtt_p50_us,
        "rtt_p99_us": rtt_p99_us,
        "rtt_max_us": rtt_max_us,
    }


def find_tags(raw_dir: Path) -> list[str]:
    tags = []
    prefix = "config_c_ipc_seq_"
    suffix = ".csv"
    for seq_file in raw_dir.glob(f"{prefix}*{suffix}"):
        tag = seq_file.name[len(prefix) : -len(suffix)]
        sender_file = raw_dir / f"config_c_ipc_sender_{tag}.csv"
        if sender_file.exists():
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
            if isinstance(v, (float, np.floating)):
                row_vals.append(f"{v:.4f}")
            else:
                row_vals.append(str(v))
        lines.append("| " + " | ".join(row_vals) + " |")
    return "\n".join(lines)


def run_analysis(raw_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    tags = find_tags(raw_dir)
    if not tags:
        print(f"No matching IPC runs found in {raw_dir}")
        return

    results = []
    for tag in tags:
        seq_path = raw_dir / f"config_c_ipc_seq_{tag}.csv"
        sender_path = raw_dir / f"config_c_ipc_sender_{tag}.csv"
        res = analyze_tag(tag, seq_path, sender_path)
        results.append(res)

    cols = [
        "tag",
        "cycles",
        "sent",
        "sent_ok",
        "send_errors",
        "skipped_slots",
        "rx_count",
        "first_cycle_with_ipc",
        "distinct_applied",
        "unobserved_ok",
        "setpoint_mismatch",
        "age_p50_cyc",
        "age_p99_cyc",
        "age_max_cyc",
        "rtt_p50_us",
        "rtt_p99_us",
        "rtt_max_us",
    ]
    df = pd.DataFrame(results)[cols]

    # Write CSV formatted with 4 decimals
    csv_out = out_dir / "ipc_summary.csv"
    df.to_csv(csv_out, index=False, float_format="%.4f")
    print(f"Saved {csv_out}")

    # Write Markdown summary table and flags
    md_out = out_dir / "ipc_summary.md"
    with open(md_out, "w") as f:
        f.write("# Config C IPC Telemetry Summary\n\n")
        f.write(df_to_markdown(df))
        f.write("\n\n### Observations & Flags\n\n")

        for r in results:
            flags = []
            if r["setpoint_mismatch"] > 0:
                flags.append(f"setpoint_mismatch={r['setpoint_mismatch']}")
            if r["send_errors"] > 0:
                flags.append(f"send_errors={r['send_errors']}")
            if r["first_cycle_with_ipc"] != 0:
                flags.append(f"first_cycle_with_ipc={r['first_cycle_with_ipc']}")
            if r["rx_count"] < 0:
                flags.append("rx_count=unknown")

            if flags:
                f.write(f"- **Tag `{r['tag']}`:** Flagged: {', '.join(flags)}\n")
            else:
                f.write(f"- **Tag `{r['tag']}`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).\n")

    print(f"Saved {md_out}")


def main():
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Analyze Config C Linux->MCU setpoint IPC")
    parser.add_argument("--raw", type=Path, default=repo_root / "results" / "raw" / "ipc", help="Input raw CSV folder")
    parser.add_argument("--out", type=Path, default=repo_root / "results" / "ipc", help="Output directory")
    args = parser.parse_args()

    raw_dir = args.raw if args.raw.is_absolute() else (repo_root / args.raw).resolve()
    out_dir = args.out if args.out.is_absolute() else (repo_root / args.out).resolve()

    run_analysis(raw_dir, out_dir)


if __name__ == "__main__":
    main()
