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


def _write_full_counters(
    path: Path,
    *,
    time_s: float,
    irq9: list[int],
    irq13: list[int],
    ipi_resched: list[int],
    ipi_call: list[int],
    ipi_tbcast: list[int],
    err_val: int,
    timer: list[int],
    net_rx: list[int],
    sched: list[int],
    rcu: list[int],
) -> None:
    text = "\n".join(
        [
            "#TIME",
            f"{time_s:.6f}",
            "#INTERRUPTS",
            "           CPU0       CPU1       CPU2       CPU3",
            f"  9:   {irq9[0]:8d}   {irq9[1]:8d}   {irq9[2]:8d}   {irq9[3]:8d}  GICv3 39 Level     arch_mem_timer",
            f" 13:   {irq13[0]:8d}   {irq13[1]:8d}   {irq13[2]:8d}   {irq13[3]:8d}  GICv3 19 Level     arch_timer",
            f"IPI0:  {ipi_resched[0]:8d}   {ipi_resched[1]:8d}   {ipi_resched[2]:8d}   {ipi_resched[3]:8d}  Rescheduling interrupts",
            f"IPI1:  {ipi_call[0]:8d}   {ipi_call[1]:8d}   {ipi_call[2]:8d}   {ipi_call[3]:8d}  Function call interrupts",
            f"IPI4:  {ipi_tbcast[0]:8d}   {ipi_tbcast[1]:8d}   {ipi_tbcast[2]:8d}   {ipi_tbcast[3]:8d}  Timer broadcast interrupts",
            f"Err:   {err_val:8d}",
            "#SOFTIRQS",
            "                    CPU0       CPU1       CPU2       CPU3",
            f"      TIMER:  {timer[0]:8d}   {timer[1]:8d}   {timer[2]:8d}   {timer[3]:8d}",
            f"     NET_RX:  {net_rx[0]:8d}   {net_rx[1]:8d}   {net_rx[2]:8d}   {net_rx[3]:8d}",
            f"      SCHED:  {sched[0]:8d}   {sched[1]:8d}   {sched[2]:8d}   {sched[3]:8d}",
            f"        RCU:  {rcu[0]:8d}   {rcu[1]:8d}   {rcu[2]:8d}   {rcu[3]:8d}",
            "#END",
        ]
    )
    path.write_text(text + "\n", encoding="utf-8")


def test_parse_counters_and_cpu_interference_per_cpu(tmp_path):
    raw_dir = tmp_path / "raw"
    real_r1 = raw_dir / "real_r1"
    real_r1.mkdir(parents=True)

    _write_linux_csv(real_r1 / "B_0_iso_rboth.csv", np.full(10000, 0.05, dtype=np.float64))
    _write_full_counters(
        real_r1 / "counters_B_0_iso_rboth_before.txt",
        time_s=100.0,
        irq9=[100, 100, 100, 100],
        irq13=[1000, 1000, 1000, 1000],
        ipi_resched=[50, 50, 50, 50],
        ipi_call=[200, 200, 200, 200],
        ipi_tbcast=[10, 10, 10, 10],
        err_val=0,
        timer=[10, 10, 10, 10],
        net_rx=[20, 20, 20, 20],
        sched=[30, 30, 30, 30],
        rcu=[40, 40, 40, 40],
    )
    _write_full_counters(
        real_r1 / "counters_B_0_iso_rboth_after.txt",
        time_s=110.0,
        irq9=[110, 120, 130, 140],
        irq13=[1100, 1200, 1300, 1400],
        ipi_resched=[55, 60, 65, 70],
        ipi_call=[250, 260, 270, 6620],
        ipi_tbcast=[11, 12, 13, 14],
        err_val=7,
        timer=[20, 30, 40, 1200],
        net_rx=[22, 24, 26, 28],
        sched=[50, 70, 90, 830],
        rcu=[70, 100, 130, 940],
    )

    # An act_tuned_rnet run must not appear in cpu_interference
    _write_c_csv(raw_dir / "act_tuned_rnet" / "C_0_act_tuned_rnet.csv")

    ref_csv = tmp_path / "compare_long.csv"
    pd.DataFrame(columns=["series", "tier", "rep", "file", "wcl_us"]).to_csv(ref_csv, index=False)

    out_dir = tmp_path / "out"
    df, md_text, chart = compare_realload.compare_realload(raw_dir, ref_csv, out_dir)

    assert chart.exists()
    assert (out_dir / "cpu3_kernel_work.png").exists()
    assert (out_dir / "cpu_interference.csv").exists()

    b_row = df[df["series"] == "B-iso"].iloc[0]
    assert b_row["counter_span_s"] == pytest.approx(10.0)
    assert b_row["dev_irq_per_cpu"] == "110,220,330,440"
    assert b_row["ipi_resched_per_cpu"] == "5,10,15,20"
    assert b_row["ipi_call_per_cpu"] == "50,60,70,6420"
    assert b_row["ipi_tbcast_per_cpu"] == "1,2,3,4"
    assert b_row["softirq_sched_per_cpu"] == "20,40,60,800"
    assert b_row["softirq_sched_delta"] == 920
    assert b_row["softirq_rcu_per_cpu"] == "30,60,90,900"
    assert b_row["softirq_rcu_delta"] == 1080

    cpu_df = pd.read_csv(out_dir / "cpu_interference.csv")
    assert set(cpu_df["series"]) == {"B-iso"}
    assert len(cpu_df) == 32  # 1 Linux run * 4 CPUs * 8 counters

    cpu3 = cpu_df[cpu_df["cpu"] == 3].set_index("counter")
    expected_cpu3_per_s = {
        "dev_irq": 44.0,
        "ipi_resched": 2.0,
        "ipi_call": 642.0,
        "ipi_tbcast": 0.4,
        "softirq_timer": 119.0,
        "softirq_net_rx": 0.8,
        "softirq_sched": 80.0,
        "softirq_rcu": 90.0,
    }
    for k, exp in expected_cpu3_per_s.items():
        assert cpu3.loc[k, "per_s"] == pytest.approx(exp)

    assert "## Kernel work on CPU 3" in md_text
    assert "**Repeats of `rboth`:**" in md_text
    assert "**B-iso isolation:**" in md_text


def test_parse_counters_without_ipi_and_act_only_cpu_interference(tmp_path):
    before = tmp_path / "before.txt"
    after = tmp_path / "after.txt"
    _write_counters(before, net_rx=[0, 0, 0, 0], wlan_rx=100, irq10=[1, 2, 3, 4], pswpin=0)
    _write_counters(after, net_rx=[5, 5, 5, 5], wlan_rx=200, irq10=[11, 12, 13, 14], pswpin=0)

    parsed = compare_realload._parse_counters(before, after)
    assert parsed["ipi_resched_per_cpu"] == ""
    assert parsed["ipi_call_per_cpu"] == ""
    assert parsed["ipi_tbcast_per_cpu"] == ""
    assert parsed["softirq_sched_per_cpu"] == ""
    assert parsed["softirq_rcu_per_cpu"] == ""
    assert parsed["dev_irq_per_cpu"] == "10,10,10,10"

    raw_dir = tmp_path / "raw_act"
    _write_c_csv(raw_dir / "act_tuned_rnet" / "C_0_act_tuned_rnet.csv")
    ref_csv = tmp_path / "ref.csv"
    pd.DataFrame(columns=["series", "tier", "rep", "file", "wcl_us"]).to_csv(ref_csv, index=False)
    out_dir = tmp_path / "out_act"
    df, _, _ = compare_realload.compare_realload(raw_dir, ref_csv, out_dir)
    assert len(df) == 1
    cpu_df = compare_realload.cpu_interference(df)
    assert cpu_df.empty


def test_load_evidence_table_pipe_count_matches_header(tmp_path):
    raw_dir = tmp_path / "raw"
    real_r1 = raw_dir / "real_r1"
    real_r1.mkdir(parents=True)

    _write_linux_csv(real_r1 / "B_0_iso_rnet.csv", np.full(10000, 0.05, dtype=np.float64))
    (real_r1 / "env_B_0_iso_rnet.txt").write_text(
        "# loadcheck start: LOADCHECK OK tier=rnet rx_Bps=6500000 inferences=-\n"
        "# loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6600000 inferences=-\n"
        "# irqs_moved=51 of 81\n"
        "# wifi_irq 140 effective=0\n"
        "# wifi_irq 141 effective=0\n",
        encoding="utf-8",
    )

    ref_csv = tmp_path / "compare_long.csv"
    pd.DataFrame(columns=["series", "tier", "rep", "file", "wcl_us"]).to_csv(ref_csv, index=False)

    out_dir = tmp_path / "out"
    df, md_text, _ = compare_realload.compare_realload(raw_dir, ref_csv, out_dir)

    # Long CSV preserves internal " | " separator unchanged
    row = df.iloc[0]
    assert " | " in row["loadcheck"]
    assert " | " in row["wifi_irq"]

    # Extract Markdown table rows directly under "## Load Evidence Per Run"
    lines = md_text.splitlines()
    start_idx = lines.index("## Load Evidence Per Run") + 1
    table_lines = []
    for ln in lines[start_idx:]:
        if not ln.strip():
            if table_lines:
                break
            continue
        if ln.startswith("|"):
            table_lines.append(ln)

    assert len(table_lines) == 3  # header + separator + 1 data row
    def count_unescaped_pipes(s: str) -> int:
        return sum(1 for i, ch in enumerate(s) if ch == "|" and (i == 0 or s[i - 1] != "\\"))

    header_pipes = count_unescaped_pipes(table_lines[0])
    for ln in table_lines[1:]:
        assert count_unescaped_pipes(ln) == header_pipes




