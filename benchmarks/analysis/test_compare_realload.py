from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import compare_realload  # noqa: E402


def _write_linux_csv(path: Path, lateness_ms: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = lateness_ms.size
    lines = ["# rusage=thread affinity=-1 analytics_affinity=-1 no_cstates=0"]
    lines.append("cycle,scheduled_ns,actual_wake_ns,lateness_ms,is_miss,is_starvation,setpoint,nivcsw,minflt")
    for k, lms in enumerate(lateness_ms):
        sched = k * 10_000_000
        wake = sched + int(round(lms * 1_000_000))
        lines.append(f"{k},{sched},{wake},{lms:.6f},{1 if lms > 1.0 else 0},0,100,0,0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_counters(path: Path, *, net_rx: list[int], wlan_rx: int, irq10: list[int], pswpin: int) -> None:
    text = "\n".join(
        [
            "#TIME",
            "1000.0",
            "#INTERRUPTS",
            "           CPU0       CPU1       CPU2       CPU3",
            f" 10:   {irq10[0]:8d}   {irq10[1]:8d}   {irq10[2]:8d}   {irq10[3]:8d}  GICv3 wifi0",
            "#SOFTIRQS",
            "                    CPU0       CPU1       CPU2       CPU3",
            f"      NET_RX: {net_rx[0]:8d}   {net_rx[1]:8d}   {net_rx[2]:8d}   {net_rx[3]:8d}",
            "       TIMER:      100        100        100        100",
            "#NETDEV",
            "Inter-|   Receive                                                |  Transmit",
            " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed",
            f" wlan0: {wlan_rx}    500    0    0    0     0          0         0     1000       10    0    0    0     0       0          0",
            "#VMSTAT",
            f"pswpin {pswpin}",
            "pswpout 0",
            "pgmajfault 2",
            "#END",
        ]
    )
    path.write_text(text + "\n", encoding="utf-8")


def test_compare_realload_blocks_evidence_and_filtering(tmp_path):
    raw_dir = tmp_path / "raw"
    real_r1 = raw_dir / "real_r1"
    real_r1.mkdir(parents=True)

    # 30,000 cycles -> 3 blocks of 10,000, floor = 0.05 ms = 50 us
    lat = np.full(30000, 0.05, dtype=np.float64)
    lat[100] = 0.25   # block 0 rel max = 200 us
    lat[12000] = 0.45  # block 1 rel max = 400 us
    lat[25000] = 0.65  # block 2 rel max = 600 us
    _write_linux_csv(real_r1 / "A_0_rnet.csv", lat)
    _write_counters(real_r1 / "counters_A_0_rnet_before.txt", net_rx=[10, 20, 30, 40], wlan_rx=1000, irq10=[1, 2, 3, 4], pswpin=0)
    _write_counters(real_r1 / "counters_A_0_rnet_after.txt", net_rx=[110, 120, 130, 140], wlan_rx=501000, irq10=[11, 12, 13, 14], pswpin=3)
    (real_r1 / "thermal_A_0_rnet.csv").write_text(
        "time_s,busy_cpu0,busy_cpu1,busy_cpu2,busy_cpu3,temp_max_c,freq_cpu0_khz,freq_cpu1_khz,freq_cpu2_khz,freq_cpu3_khz,cooling_states\n"
        "100.0,10.0,20.0,30.0,40.0,55.5,2016000,2016000,2016000,2016000,0;0\n"
        "110.0,15.0,25.0,35.0,45.0,62.3,1800000,2016000,2016000,2016000,0;1\n",
        encoding="utf-8",
    )
    (real_r1 / "env_A_0_rnet.txt").write_text("# loadcheck start: LOADCHECK OK tier=rnet rx_Bps=2000000 inferences=-\n", encoding="utf-8")

    # Second run: B_0_iso_rdeploy.csv (series B-iso, tier rdeploy)
    b_lat = np.full(10000, 0.02, dtype=np.float64)
    b_lat[500] = 0.12  # rel max = 100 us
    _write_linux_csv(real_r1 / "B_0_iso_rdeploy.csv", b_lat)
    (real_r1 / "analytics_B_0_iso_rdeploy.csv").write_text(
        "t_mono_ns,count,cls,infer_us\n"
        "1000000000,1,0,30000.0\n"
        "2000000000,2,1,40000.0\n"
        "3000000000,3,2,50000.0\n",
        encoding="utf-8",
    )
    (real_r1 / "pc_traffic_rdeploy.json").write_text(json.dumps({"avg_rate_Bps": 48000.0, "reconnects": 0}), encoding="utf-8")

    # Folders that must be ignored
    linux_r1 = raw_dir / "linux_r1"
    linux_r1.mkdir(parents=True)
    _write_linux_csv(linux_r1 / "A_0.csv", np.full(100, 0.1))
    arch = raw_dir / "archive" / "real_r1"
    arch.mkdir(parents=True)
    _write_linux_csv(arch / "A_0_rnet.csv", np.full(100, 0.9))

    # Minimal Phase 5d reference CSV
    ref_csv = tmp_path / "compare_long.csv"
    pd.DataFrame(
        [
            {"series": "A", "tier": "0", "rep": 1, "file": "linux_r1/A_0.csv", "wcl_us": 550.0},
            {"series": "A", "tier": "allcore", "rep": 1, "file": "linux_r1/A_100_allcore.csv", "wcl_us": 20000.0},
        ]
    ).to_csv(ref_csv, index=False)

    out_dir = tmp_path / "out"
    df, md_text, chart = compare_realload.compare_realload(raw_dir, ref_csv, out_dir)

    assert len(df) == 2
    assert set(df["file"]) == {"real_r1/A_0_rnet.csv", "real_r1/B_0_iso_rdeploy.csv"}
    assert chart.exists()

    a_row = df[df["file"] == "real_r1/A_0_rnet.csv"].iloc[0]
    assert a_row["series"] == "A"
    assert a_row["tier"] == "rnet"
    assert a_row["n_blocks"] == 3
    assert a_row["block_wcl_median_us"] == pytest.approx(400.0)
    assert a_row["block_wcl_max_us"] == pytest.approx(600.0)
    assert a_row["softirq_net_rx_delta"] == 400
    assert a_row["wlan0_rx_bytes_delta"] == 500000
    assert a_row["pswpin_delta"] == 3
    assert bool(a_row["throttled"]) is True
    assert a_row["temp_max_c"] == pytest.approx(62.3)
    assert a_row["freq_min_khz"] == pytest.approx(1800000.0)

    b_row = df[df["file"] == "real_r1/B_0_iso_rdeploy.csv"].iloc[0]
    assert b_row["series"] == "B-iso"
    assert b_row["tier"] == "rdeploy"
    assert b_row["n_blocks"] == 1
    assert b_row["infer_count"] == 3
    assert b_row["infer_rate_hz"] == pytest.approx(1.0)
    assert b_row["infer_p50_us"] == pytest.approx(40000.0)
    assert b_row["pc_avg_rate_Bps"] == pytest.approx(48000.0)
    assert "550.0 [550.0–550.0]" in md_text


def _write_c_csv(path: Path, n: int = 10000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cycles = np.arange(n, dtype=np.int64)
    wake = cycles * 1_600_000
    if n > 10:
        wake[10] += 320  # +2.0 us jitter
    pd.DataFrame({"cycle": cycles, "wake_cyc": wake}).to_csv(path, index=False)


def test_compare_realload_act_tuned_and_ignores_non_realload_ipc(tmp_path):
    raw_dir = tmp_path / "raw"

    # Phase 6b act_tuned idle + act_tuned_rnet_r2 (no counters/thermal/traffic in idle)
    _write_c_csv(raw_dir / "act_tuned" / "C_0_act_tuned.csv")
    _write_c_csv(raw_dir / "act_tuned_rnet_r2" / "C_0_act_tuned_rnet.csv")
    (raw_dir / "act_tuned_rnet_r2" / "config_c_env_0_act_tuned_rnet.txt").write_text(
        "# loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=3000000 inferences=-\n",
        encoding="utf-8",
    )
    (raw_dir / "act_tuned_rnet_r2" / "pc_traffic_0_act_tuned_rnet.json").write_text(
        json.dumps({"avg_rate_Bps": 3100000.0, "reconnects": 0}),
        encoding="utf-8",
    )

    # Non-realload ipc_tuned folders must be ignored
    _write_c_csv(raw_dir / "ipc_tuned" / "C_0_ipc_tuned.csv")
    _write_c_csv(raw_dir / "ipc_tuned_allcore" / "C_100_ipc_tuned_allcore.csv")

    # Minimal ref CSV with NO C act tuned rows -> '–' in Ref columns without error
    ref_csv = tmp_path / "compare_long.csv"
    pd.DataFrame(
        [{"series": "A", "tier": "0", "rep": 1, "file": "linux_r1/A_0.csv", "wcl_us": 550.0}]
    ).to_csv(ref_csv, index=False)

    out_dir = tmp_path / "out"
    df, md_text, chart = compare_realload.compare_realload(raw_dir, ref_csv, out_dir)

    assert chart.exists()
    assert len(df) == 2
    assert set(df["series"]) == {"C act tuned"}
    assert set(df["tier"]) == {"0", "rnet"}

    idle_row = df[df["tier"] == "0"].iloc[0]
    assert idle_row["file"] == "act_tuned/C_0_act_tuned.csv"
    assert idle_row["rep"] == 1
    assert np.isnan(idle_row["wlan0_rx_bytes_delta"])
    assert np.isnan(idle_row["temp_max_c"])
    assert np.isnan(idle_row["pc_avg_rate_Bps"])

    rnet_row = df[df["tier"] == "rnet"].iloc[0]
    assert rnet_row["rep"] == 2
    assert rnet_row["pc_avg_rate_Bps"] == pytest.approx(3100000.0)

    # Pairs with no runs are skipped, and C act tuned shows '–' for both Ref cols
    assert "| A | 0 |" not in md_text
    assert "| C act tuned | rdeploy |" not in md_text
    assert "| C act tuned | 0 | 1 | 10000 |" in md_text
    assert "| – | – |" in md_text


def test_compare_realload_rboth_linux_and_act(tmp_path):
    raw_dir = tmp_path / "raw"
    real_r1 = raw_dir / "real_r1"
    real_r1.mkdir(parents=True)

    b_lat = np.full(10000, 0.03, dtype=np.float64)
    b_lat[100] = 0.53  # rel max = 500 us
    _write_linux_csv(real_r1 / "B_0_rboth.csv", b_lat)
    (real_r1 / "analytics_B_0_rboth.csv").write_text(
        "t_mono_ns,count,cls,infer_us\n"
        "1000000000,1,0,35000.0\n"
        "2000000000,2,1,45000.0\n",
        encoding="utf-8",
    )
    (real_r1 / "pc_traffic_rboth_bulk.json").write_text(
        json.dumps({"avg_rate_Bps": 6000000.0, "reconnects": 2}),
        encoding="utf-8",
    )
    (real_r1 / "pc_traffic_rboth_ingest.json").write_text(
        json.dumps({"avg_rate_Bps": 48000.0, "late_skips": 1}),
        encoding="utf-8",
    )

    _write_c_csv(raw_dir / "act_tuned_rboth" / "C_0_act_tuned_rboth.csv")
    (raw_dir / "act_tuned_rboth" / "config_c_env_0_act_tuned_rboth.txt").write_text(
        "# loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=5000000 inferences=55\n",
        encoding="utf-8",
    )
    (raw_dir / "act_tuned_rboth" / "pc_traffic_0_act_tuned_rboth_bulk.json").write_text(
        json.dumps({"avg_rate_Bps": 6200000.0, "reconnects": 0}),
        encoding="utf-8",
    )
    (raw_dir / "act_tuned_rboth" / "pc_traffic_0_act_tuned_rboth_ingest.json").write_text(
        json.dumps({"avg_rate_Bps": 47500.0, "late_skips": 0}),
        encoding="utf-8",
    )

    ref_csv = tmp_path / "compare_long.csv"
    pd.DataFrame(columns=["series", "tier", "rep", "file", "wcl_us"]).to_csv(ref_csv, index=False)

    out_dir = tmp_path / "out"
    df, md_text, chart = compare_realload.compare_realload(raw_dir, ref_csv, out_dir)

    assert chart.exists()
    assert len(df) == 2
    assert set(df["tier"]) == {"rboth"}

    b_row = df[df["series"] == "B"].iloc[0]
    assert b_row["tier"] == "rboth"
    assert not np.isnan(b_row["infer_count"])
    assert b_row["infer_count"] == 2
    assert b_row["pc_avg_rate_Bps"] == pytest.approx(6000000.0)
    assert b_row["pc_reconnects"] == 2
    assert b_row["pc_ingest_rate_Bps"] == pytest.approx(48000.0)
    assert b_row["pc_ingest_late_skips"] == 1

    c_row = df[df["series"] == "C act tuned"].iloc[0]
    assert c_row["tier"] == "rboth"
    assert c_row["pc_avg_rate_Bps"] == pytest.approx(6200000.0)
    assert c_row["pc_ingest_rate_Bps"] == pytest.approx(47500.0)

    assert "rboth" in md_text
    assert "ingest 48000 / skips 1" in md_text


