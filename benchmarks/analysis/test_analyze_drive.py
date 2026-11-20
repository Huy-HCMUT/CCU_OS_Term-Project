from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import analyze_drive  # noqa: E402


def _make_base_run(folder: Path, tag: str = "0_act_tuned", *, n_cycles: int = 10, seq_sps: dict[int, int] | None = None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    seq_sps = seq_sps or {2: 80, 5: 60, 8: 100}

    # config_c_ipc_seq_<tag>.csv
    cur_sp = 100
    seq_rows = []
    for k in range(n_cycles):
        if k in seq_sps:
            cur_sp = seq_sps[k]
        seq_rows.append((k, k + 1, cur_sp))
    with open(folder / f"config_c_ipc_seq_{tag}.csv", "w", encoding="utf-8", newline="") as f:
        f.write("# rx_count=10\n")
        pd.DataFrame(seq_rows, columns=["cycle", "applied_seq", "applied_setpoint_pct"]).to_csv(f, index=False)

    # config_c_ipc_sender_<tag>.csv
    sender_rows = [
        (k + 1, k, sp, k * 100000, k * 100000, k * 100000 + 500000, 500.0, 0, "ok")
        for k, _, sp in seq_rows
    ]
    with open(folder / f"config_c_ipc_sender_{tag}.csv", "w", encoding="utf-8", newline="") as f:
        f.write("# frames_source=cwru period_ns=85333333\n")
        pd.DataFrame(
            sender_rows,
            columns=["seq", "frame_idx", "setpoint_pct", "release_ns", "t_send_ns", "t_return_ns", "rtt_us", "skipped_after", "status"],
        ).to_csv(f, index=False)

    # config_c_dwt_<tag>.csv (starts at cyc=1000, 10 ms = 1,600,000 cyc per tick)
    dwt_rows = [(k, 1000 + k * 1600000, 1600000, 10000.0, 0.0) for k in range(n_cycles)]
    pd.DataFrame(
        dwt_rows,
        columns=["cycle", "dwt_cyccnt", "dwt_delta_cyc", "dwt_period_us", "dwt_lateness_ms"],
    ).to_csv(folder / f"config_c_dwt_{tag}.csv", index=False)


def test_analyze_drive_lost_wrong_and_u32_rollover(tmp_path):
    raw_dir = tmp_path / "raw"
    folder = raw_dir / "act_tuned"
    _make_base_run(folder, tag="0_act_tuned", n_cycles=10, seq_sps={2: 80, 5: 60, 8: 100})

    # 3 act writes matching seq_sps: cycles 2 (sp 80), 5 (sp 60), 8 (sp 100)
    act_rows = [
        (2, 1000 + 2 * 1600000 + 81600, 320, 80),
        (5, 1000 + 5 * 1600000 + 81600, 320, 60),
        (8, 1000 + 8 * 1600000 + 81600, 320, 100),
    ]
    with open(folder / "config_c_act_0_act_tuned.csv", "w", encoding="utf-8", newline="") as f:
        f.write("# act_count=3\n")
        pd.DataFrame(act_rows, columns=["cycle", "t_write_cyc", "cost_cyc", "setpoint_pct"]).to_csv(f, index=False)

    # Drive events:
    # - 1 pre-run event at tick_idx = -1 (excluded from lost/wrong/extra/delays)
    # - tick 2 matches sp 80 (high = 0.64 * 320000 = 204800 -> decoded 80 %), with tick_cyc near 2^32 wrapping past 0!
    # - tick 5 has high = 0.6 * 320000 = 192000 for sp 60 -> decoded 75 % -> wrong = 1
    # - tick 8 is missing -> lost = 1
    tick2_cyc = 0xFFFFFF00  # 4,294,967,040: wraps to 0 after 256 cyc
    rise2_cyc = (tick2_cyc + 160000) & 0xFFFFFFFF   # +1000.0 us
    fall2_cyc = (tick2_cyc + 364800) & 0xFFFFFFFF   # +2280.0 us (high = 204800 cyc)

    tick5_cyc = 5_000_000
    rise5_cyc = tick5_cyc + 160000                  # +1000.0 us
    fall5_cyc = tick5_cyc + 160000 + 192000         # +2200.0 us (high = 192000 cyc -> 0.6 * period -> decoded 75 %)

    drive_rows = [
        (0, -1, 100, 200, 256200, 256000, 320000),
        (1, 2, tick2_cyc, rise2_cyc, fall2_cyc, 204800, 320000),
        (2, 5, tick5_cyc, rise5_cyc, fall5_cyc, 192000, 320000),
    ]
    with open(folder / "config_c_drive_0_act_tuned.csv", "w", encoding="utf-8", newline="") as f:
        f.write(
            "# ticks=10 tick_min_cyc=1599900 tick_max_cyc=1600100 periods=100 "
            "period_outliers=0 level_errors=0 initial_high_cyc=256000 events=3 events_dropped=0\n"
        )
        pd.DataFrame(
            drive_rows,
            columns=["event", "tick_idx", "tick_cyc", "rise_cyc", "fall_cyc", "high_cyc", "period_cyc"],
        ).to_csv(f, index=False)

    out_dir = tmp_path / "out"
    df, md_text = analyze_drive.analyze_drive(raw_dir, out_dir)

    assert (out_dir / "drive_long.csv").exists()
    assert (out_dir / "drive.md").exists()
    assert len(df) == 1

    r = df.iloc[0]
    assert bool(r["writes_match"]) is True
    assert r["pre_run_events"] == 1
    assert r["writes"] == 3
    assert r["matched"] == 2
    assert r["lost"] == 1
    assert r["wrong"] == 1
    assert r["extra"] == 0

    # Rollover tick2_cyc -> rise2_cyc / fall2_cyc gives positive 1000 us / 2280 us (with tick5: 1000 / 2200 us)
    assert r["drive_start_min_us"] == pytest.approx(1000.0)
    assert r["drive_start_max_us"] == pytest.approx(1000.0)
    assert r["drive_seen_min_us"] == pytest.approx(2200.0)
    assert r["drive_seen_max_us"] == pytest.approx(2280.0)
    assert r["drive_seen_p50_us"] == pytest.approx(2240.0)

    # DUT offsets & cost
    assert r["write_offset_min_us"] == pytest.approx(510.0)
    assert r["write_cost_max_us"] == pytest.approx(2.0)

    # Chain bound: rtt_p99 (500 us = 0.5 ms) + 10 ms + drive_seen_p99 (2.2792 ms)
    expected_cb = r["rtt_p99_us"] / 1000.0 + 10.0 + r["drive_seen_p99_us"] / 1000.0
    assert r["chain_bound_ms"] == pytest.approx(expected_cb)
    assert "upper bound (sum of p99s: send → stored, ≤ 1 tick wait, tick → drive sees it)" in md_text


def test_analyze_drive_finds_rboth_tier(tmp_path):
    raw_dir = tmp_path / "raw"
    folder = raw_dir / "act_tuned_rboth"
    tag = "0_act_tuned_rboth"
    _make_base_run(folder, tag=tag, n_cycles=10, seq_sps={2: 80})

    act_rows = [(2, 1000 + 2 * 1600000 + 80000, 320, 80)]
    with open(folder / f"config_c_act_{tag}.csv", "w", encoding="utf-8", newline="") as f:
        f.write("# act_count=1\n")
        pd.DataFrame(act_rows, columns=["cycle", "t_write_cyc", "cost_cyc", "setpoint_pct"]).to_csv(f, index=False)

    drive_rows = [(0, 2, 1000, 161000, 365800, 204800, 320000)]
    with open(folder / f"config_c_drive_{tag}.csv", "w", encoding="utf-8", newline="") as f:
        f.write(
            "# ticks=10 tick_min_cyc=1599900 tick_max_cyc=1600100 periods=100 "
            "period_outliers=0 level_errors=0 initial_high_cyc=256000 events=1 events_dropped=0\n"
        )
        pd.DataFrame(
            drive_rows,
            columns=["event", "tick_idx", "tick_cyc", "rise_cyc", "fall_cyc", "high_cyc", "period_cyc"],
        ).to_csv(f, index=False)

    df, md_text = analyze_drive.analyze_drive(raw_dir, tmp_path / "out")

    assert len(df) == 1
    r = df.iloc[0]
    assert r["tier"] == "rboth"
    assert r["tag"] == tag
    assert r["lost"] == 0 and r["wrong"] == 0 and r["extra"] == 0
    assert "| rboth | 1 | 1 | 0 | 0 | 0 |" in md_text

