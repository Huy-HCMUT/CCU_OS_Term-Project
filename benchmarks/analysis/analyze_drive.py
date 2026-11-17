#!/usr/bin/env python3
"""Phase 6b full-chain actuation analysis: DUT PWM writes -> emulated drive on board 3."""

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
from analyze_ipc import analyze_tag  # noqa: E402

ACT_DIR_RE = re.compile(r"^act_tuned(?:_(?P<tier>rnet|rdeploy))?(?:_r(?P<rep>\d+))?$")
TIERS = ["0", "rdeploy", "rnet"]
DWT_HZ_MHZ = 160.0
PWM_NOMINAL_PERIOD_CYC = 320000.0

DRIVE_LONG_COLUMNS = [
    "folder",
    "tag",
    "tier",
    "rep",
    "seq_changes",
    "writes",
    "writes_match",
    "pre_run_events",
    "matched",
    "lost",
    "wrong",
    "extra",
    "drive_start_min_us",
    "drive_start_p50_us",
    "drive_start_p99_us",
    "drive_start_max_us",
    "drive_seen_min_us",
    "drive_seen_p50_us",
    "drive_seen_p99_us",
    "drive_seen_max_us",
    "write_offset_min_us",
    "write_offset_p50_us",
    "write_offset_max_us",
    "write_cost_min_us",
    "write_cost_p50_us",
    "write_cost_max_us",
    "drive_ticks",
    "ticks_ok",
    "period_outliers",
    "level_errors",
    "events_dropped",
    "initial_high_cyc",
    "initial_duty",
    "board3_tick_min_us",
    "board3_tick_max_us",
    "rtt_p99_us",
    "age_p99_cyc",
    "unobserved_ok",
    "chain_bound_ms",
]


def _signed_u32_diff(a: int, b: int) -> int:
    """Return signed 32-bit difference (a - b) handling uint32 rollover."""
    d = (int(a) - int(b)) & 0xFFFFFFFF
    if d >= 0x80000000:
        d -= 0x100000000
    return d


def _parse_drive_meta(path: Path) -> dict[str, int]:
    """Parse '# key=val ...' header line from config_c_drive_<tag>.csv."""
    meta: dict[str, int] = {}
    if not path.exists():
        return meta
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        first = f.readline().strip()
    if not first.startswith("#"):
        return meta
    for tok in first[1:].split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        try:
            meta[k] = int(v)
        except ValueError:
            pass
    return meta


def _stats_min_p50_p99_max(vals: list[float]) -> tuple[float, float, float, float]:
    if not vals:
        return (np.nan, np.nan, np.nan, np.nan)
    arr = np.asarray(vals, dtype=np.float64)
    return (
        float(np.min(arr)),
        float(np.percentile(arr, 50)),
        float(np.percentile(arr, 99)),
        float(np.max(arr)),
    )


def _stats_min_p50_max(vals: list[float]) -> tuple[float, float, float]:
    if not vals:
        return (np.nan, np.nan, np.nan)
    arr = np.asarray(vals, dtype=np.float64)
    return (
        float(np.min(arr)),
        float(np.percentile(arr, 50)),
        float(np.max(arr)),
    )


def _seq_changes(seq_df: pd.DataFrame) -> list[tuple[int, int]]:
    """Setpoint changes in seq log: cycles where applied_setpoint_pct differs from previous cycle, starting at 100."""
    changes: list[tuple[int, int]] = []
    prev = 100
    ordered = seq_df.sort_values("cycle") if "cycle" in seq_df.columns else seq_df
    for _, row in ordered.iterrows():
        c = int(row["cycle"])
        sp = int(row["applied_setpoint_pct"])
        if sp != prev:
            changes.append((c, sp))
            prev = sp
    return changes


def analyze_run(folder: Path, tier: str, rep: int, tag: str) -> dict:
    """Analyze one Phase 6b non-sanity act_tuned run."""
    drive_path = folder / f"config_c_drive_{tag}.csv"
    act_path = folder / f"config_c_act_{tag}.csv"
    seq_path = folder / f"config_c_ipc_seq_{tag}.csv"
    sender_path = folder / f"config_c_ipc_sender_{tag}.csv"
    dwt_path = folder / f"config_c_dwt_{tag}.csv"

    seq_df = pd.read_csv(seq_path, comment="#")
    changes_seq = _seq_changes(seq_df)

    act_df = pd.read_csv(act_path, comment="#")
    writes = [(int(r["cycle"]), int(r["setpoint_pct"])) for _, r in act_df.iterrows()]
    writes_match = writes == changes_seq

    dwt_df = pd.read_csv(dwt_path, comment="#") if dwt_path.exists() else pd.DataFrame(columns=["cycle", "dwt_cyccnt"])
    dwt_map = {int(r["cycle"]): int(r["dwt_cyccnt"]) for _, r in dwt_df.iterrows()}

    meta = _parse_drive_meta(drive_path)
    drive_df = pd.read_csv(drive_path, comment="#")
    if drive_df.empty:
        pre_run_events = 0
        in_run_df = drive_df
    else:
        pre_run_events = int((drive_df["tick_idx"] < 0).sum())
        in_run_df = drive_df[drive_df["tick_idx"] >= 0]

    # Index writes and in-run drive events by tick/cycle index
    writes_by_cycle: dict[int, list[tuple[int, int, int]]] = {}
    for _, r in act_df.iterrows():
        c = int(r["cycle"])
        writes_by_cycle.setdefault(c, []).append(
            (int(r["t_write_cyc"]), int(r["cost_cyc"]), int(r["setpoint_pct"]))
        )

    events_by_tick: dict[int, list[dict]] = {}
    for _, r in in_run_df.iterrows():
        k = int(r["tick_idx"])
        events_by_tick.setdefault(k, []).append(
            {
                "tick_cyc": int(r["tick_cyc"]),
                "rise_cyc": int(r["rise_cyc"]),
                "fall_cyc": int(r["fall_cyc"]),
                "high_cyc": int(r["high_cyc"]),
                "period_cyc": int(r["period_cyc"]),
            }
        )

    matched_count = 0
    lost = 0
    wrong = 0
    extra = 0
    for k in sorted(set(writes_by_cycle) | set(events_by_tick)):
        ws = writes_by_cycle.get(k, [])
        evs = events_by_tick.get(k, [])
        n_pair = min(len(ws), len(evs))
        matched_count += n_pair
        lost += len(ws) - n_pair
        extra += len(evs) - n_pair
        for idx in range(n_pair):
            sp = ws[idx][2]
            ev = evs[idx]
            p_cyc = ev["period_cyc"]
            if p_cyc <= 0:
                wrong += 1
            else:
                decoded_pct = 125.0 * float(ev["high_cyc"]) / float(p_cyc)
                if abs(decoded_pct - float(sp)) > 2.0:
                    wrong += 1

    # Board 3 delays for all in-run events (tick_idx >= 0) using signed 32-bit wraparound diff
    drive_start_us = [
        _signed_u32_diff(int(r["rise_cyc"]), int(r["tick_cyc"])) / DWT_HZ_MHZ
        for _, r in in_run_df.iterrows()
    ]
    drive_seen_us = [
        _signed_u32_diff(int(r["fall_cyc"]), int(r["tick_cyc"])) / DWT_HZ_MHZ
        for _, r in in_run_df.iterrows()
    ]
    ds_min, ds_p50, ds_p99, ds_max = _stats_min_p50_p99_max(drive_start_us)
    de_min, de_p50, de_p99, de_max = _stats_min_p50_p99_max(drive_seen_us)

    # DUT side write offsets & costs
    write_offset_us: list[float] = []
    write_cost_us: list[float] = []
    for _, r in act_df.iterrows():
        c = int(r["cycle"])
        write_cost_us.append(float(r["cost_cyc"]) / DWT_HZ_MHZ)
        if c in dwt_map:
            write_offset_us.append(_signed_u32_diff(int(r["t_write_cyc"]), dwt_map[c]) / DWT_HZ_MHZ)

    wo_min, wo_p50, wo_max = _stats_min_p50_max(write_offset_us)
    wc_min, wc_p50, wc_max = _stats_min_p50_max(write_cost_us)

    # Drive health metrics from '#' metadata
    drive_ticks = int(meta.get("ticks", 0))
    ticks_ok = drive_ticks == 10000
    period_outliers = int(meta.get("period_outliers", 0))
    level_errors = int(meta.get("level_errors", 0))
    events_dropped = int(meta.get("events_dropped", 0))
    initial_high_cyc = int(meta.get("initial_high_cyc", 0))
    initial_duty = float(initial_high_cyc) / PWM_NOMINAL_PERIOD_CYC
    board3_tick_min_us = float(meta["tick_min_cyc"]) / DWT_HZ_MHZ if drive_ticks > 1 and "tick_min_cyc" in meta else np.nan
    board3_tick_max_us = float(meta["tick_max_cyc"]) / DWT_HZ_MHZ if drive_ticks > 1 and "tick_max_cyc" in meta else np.nan

    # IPC stats via analyze_ipc.analyze_tag
    if sender_path.exists():
        ipc = analyze_tag(tag, seq_path, sender_path)
        rtt_p99_us = float(ipc["rtt_p99_us"])
        age_p99_cyc = float(ipc["age_p99_cyc"])
        unobserved_ok = int(ipc["unobserved_ok"])
    else:
        rtt_p99_us = np.nan
        age_p99_cyc = np.nan
        unobserved_ok = 0

    chain_bound_ms = (
        rtt_p99_us / 1000.0 + 10.0 + de_p99 / 1000.0
        if np.isfinite(rtt_p99_us) and np.isfinite(de_p99)
        else np.nan
    )

    return {
        "folder": folder.name,
        "tag": tag,
        "tier": tier,
        "rep": rep,
        "seq_changes": len(changes_seq),
        "writes": len(writes),
        "writes_match": bool(writes_match),
        "pre_run_events": pre_run_events,
        "matched": matched_count,
        "lost": lost,
        "wrong": wrong,
        "extra": extra,
        "drive_start_min_us": ds_min,
        "drive_start_p50_us": ds_p50,
        "drive_start_p99_us": ds_p99,
        "drive_start_max_us": ds_max,
        "drive_seen_min_us": de_min,
        "drive_seen_p50_us": de_p50,
        "drive_seen_p99_us": de_p99,
        "drive_seen_max_us": de_max,
        "write_offset_min_us": wo_min,
        "write_offset_p50_us": wo_p50,
        "write_offset_max_us": wo_max,
        "write_cost_min_us": wc_min,
        "write_cost_p50_us": wc_p50,
        "write_cost_max_us": wc_max,
        "drive_ticks": drive_ticks,
        "ticks_ok": ticks_ok,
        "period_outliers": period_outliers,
        "level_errors": level_errors,
        "events_dropped": events_dropped,
        "initial_high_cyc": initial_high_cyc,
        "initial_duty": initial_duty,
        "board3_tick_min_us": board3_tick_min_us,
        "board3_tick_max_us": board3_tick_max_us,
        "rtt_p99_us": rtt_p99_us,
        "age_p99_cyc": age_p99_cyc,
        "unobserved_ok": unobserved_ok,
        "chain_bound_ms": chain_bound_ms,
    }


def _collect_runs(raw_dir: Path) -> list[dict]:
    if not raw_dir.exists():
        return []
    dirs: list[tuple[str, int, Path]] = []
    tier_rank = {t: i for i, t in enumerate(TIERS)}
    for entry in raw_dir.iterdir():
        if not entry.is_dir():
            continue
        m = ACT_DIR_RE.fullmatch(entry.name)
        if not m:
            continue
        tier = m.group("tier") or "0"
        rep = int(m.group("rep")) if m.group("rep") else 1
        dirs.append((tier, rep, entry))

    rows: list[dict] = []
    for tier, rep, folder in sorted(dirs, key=lambda x: (tier_rank[x[0]], x[1])):
        sfx = f"_{tier}" if tier != "0" else ""
        tag = f"0_act_tuned{sfx}"
        required = (
            folder / f"config_c_drive_{tag}.csv",
            folder / f"config_c_act_{tag}.csv",
            folder / f"config_c_ipc_seq_{tag}.csv",
        )
        if not all(p.exists() for p in required):
            continue
        rows.append(analyze_run(folder, tier, rep, tag))
    return rows


def _fmt(v: float, decimals: int = 1) -> str:
    return f"{float(v):.{decimals}f}" if pd.notna(v) else "—"


def _build_markdown(long_df: pd.DataFrame) -> str:
    lines = [
        "# Phase 6b Full-Chain Drive Actuation Summary",
        "",
        "## Tier Summary (`C act tuned`)",
        "",
        "| Tier | n runs | writes | lost | wrong | extra | drive_seen p50 µs | drive_seen p99 µs | drive_seen max µs | write_cost max µs | rtt_p99 µs | chain_bound upper bound ms |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for tier in TIERS:
        sub = long_df[long_df["tier"] == tier] if not long_df.empty else long_df
        if sub.empty:
            lines.append(f"| {tier} | 0 | — | — | — | — | — | — | — | — | — | — |")
            continue
        n_runs = int(len(sub))
        writes = int(sub["writes"].sum())
        lost = int(sub["lost"].sum())
        wrong = int(sub["wrong"].sum())
        extra = int(sub["extra"].sum())
        p50_med = np.median(sub["drive_seen_p50_us"].dropna()) if sub["drive_seen_p50_us"].notna().any() else np.nan
        p99_max = np.max(sub["drive_seen_p99_us"].dropna()) if sub["drive_seen_p99_us"].notna().any() else np.nan
        seen_max = np.max(sub["drive_seen_max_us"].dropna()) if sub["drive_seen_max_us"].notna().any() else np.nan
        wc_max = np.max(sub["write_cost_max_us"].dropna()) if sub["write_cost_max_us"].notna().any() else np.nan
        rtt_max = np.max(sub["rtt_p99_us"].dropna()) if sub["rtt_p99_us"].notna().any() else np.nan
        cb_max = np.max(sub["chain_bound_ms"].dropna()) if sub["chain_bound_ms"].notna().any() else np.nan
        lines.append(
            f"| {tier} | {n_runs} | {writes} | {lost} | {wrong} | {extra} | "
            f"{_fmt(p50_med, 1)} | {_fmt(p99_max, 1)} | {_fmt(seen_max, 1)} | "
            f"{_fmt(wc_max, 2)} | {_fmt(rtt_max, 1)} | {_fmt(cb_max, 3)} |"
        )

    lines.extend(
        [
            "",
            "## Per-Run Details & Drive Health",
            "",
            "| Folder | Tier | Rep | writes match | pre_run | lost / wrong / extra | drive_start p50/p99/max µs | drive_seen p50/p99/max µs | write_offset min/p50/max µs | write_cost max µs | ticks (10k?) | pout / lerr / drop | initial_duty | board3 tick min–max µs | age_p99 cyc | unobs_ok |",
            "| :--- | :--- | ---: | :--- | ---: | :--- | :--- | :--- | :--- | ---: | :--- | :--- | ---: | :--- | ---: | ---: |",
        ]
    )

    for _, r in long_df.iterrows():
        ds_s = f"{_fmt(r['drive_start_p50_us'])} / {_fmt(r['drive_start_p99_us'])} / {_fmt(r['drive_start_max_us'])}"
        de_s = f"{_fmt(r['drive_seen_p50_us'])} / {_fmt(r['drive_seen_p99_us'])} / {_fmt(r['drive_seen_max_us'])}"
        wo_s = f"{_fmt(r['write_offset_min_us'], 2)} / {_fmt(r['write_offset_p50_us'], 2)} / {_fmt(r['write_offset_max_us'], 2)}"
        tick_rng = f"{_fmt(r['board3_tick_min_us'], 1)}–{_fmt(r['board3_tick_max_us'], 1)}"
        ticks_s = f"{int(r['drive_ticks'])} ({'OK' if r['ticks_ok'] else 'NO'})"
        health_s = f"{int(r['period_outliers'])} / {int(r['level_errors'])} / {int(r['events_dropped'])}"
        lwe_s = f"{int(r['lost'])} / {int(r['wrong'])} / {int(r['extra'])}"
        lines.append(
            f"| {r['folder']} | {r['tier']} | {int(r['rep'])} | {r['writes_match']} | {int(r['pre_run_events'])} | "
            f"{lwe_s} | {ds_s} | {de_s} | {wo_s} | {_fmt(r['write_cost_max_us'], 2)} | "
            f"{ticks_s} | {health_s} | {_fmt(r['initial_duty'], 4)} | {tick_rng} | "
            f"{_fmt(r['age_p99_cyc'], 1)} | {int(r['unobserved_ok'])} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- **Chain bound (`chain_bound_ms`):** `rtt_p99_us / 1000 + 10 + drive_seen_p99_us / 1000` — "
            "**upper bound (sum of p99s: send → stored, ≤ 1 tick wait, tick → drive sees it)**.",
            "- **Duty encoding:** `duty = 0.8 × setpoint`, so the emulated drive decodes "
            "`decoded_pct = 125 × high_cyc / period_cyc`. A matched event is counted as `wrong` if "
            "`|decoded_pct − setpoint_pct| > 2`. Events with `tick_idx < 0` occur before tick 0 "
            "(the `reset_ipc` write back to 100%) and are counted separately as `pre_run_events`.",
            "- **PWM modulation delay:** The PWM portion of `drive_seen_us` (waiting for the next 2 ms "
            "period boundary plus the 0.96–1.60 ms high pulse) is fixed by 500 Hz PWM hardware modulation "
            "and is not OS behavior.",
            "- **Clock domains:** `drive_start_us` and `drive_seen_us` use Board 3's 160 MHz DWT clock "
            "(signed 32-bit differences, no cross-board clock subtraction). `write_offset_us` and "
            "`write_cost_us` use the DUT MCU's 160 MHz DWT clock. `rtt_p99_us` uses Linux monotonic time.",
            "- **Scope:** Configs A, B, and B-iso have no physical drive output; Phase 6b drive measurements "
            "apply only to `C act tuned`.",
            "",
        ]
    )
    return "\n".join(lines)


def analyze_drive(raw_dir: Path, out_dir: Path) -> tuple[pd.DataFrame, str]:
    rows = _collect_runs(raw_dir)
    long_df = pd.DataFrame(rows, columns=DRIVE_LONG_COLUMNS)
    out_dir.mkdir(parents=True, exist_ok=True)

    long_csv = out_dir / "drive_long.csv"
    long_df.to_csv(long_csv, index=False, float_format="%.4f")

    md_text = _build_markdown(long_df)
    md_path = out_dir / "drive.md"
    md_path.write_text(md_text, encoding="utf-8")

    print(f"Wrote {long_csv}")
    print(f"Wrote {md_path}")
    return long_df, md_text


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=repo / "results" / "raw")
    parser.add_argument("--out", type=Path, default=repo / "results" / "phase6b")
    args = parser.parse_args(argv)
    analyze_drive(args.raw, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

