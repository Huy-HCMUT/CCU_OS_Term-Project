from pathlib import Path
import pytest
import pandas as pd
from analyze_referee import analyze_tag, run_comparison


def test_referee_new_format(tmp_path):
    dwt_path = tmp_path / "config_c_dwt_new.csv"
    ref_path = tmp_path / "config_c_referee_new.csv"

    # DUT: dwt_delta_cyc 1600000, 1600800, 1600800, 1600800
    dwt_rows = [
        [0, 100000, 1600000, 10000.0, 0.0],
        [1, 1700800, 1600800, 10005.0, 0.0],
        [2, 3301600, 1600800, 10005.0, 0.0],
        [3, 4902400, 1600800, 10005.0, 0.0],
    ]
    pd.DataFrame(
        dwt_rows,
        columns=["cycle", "dwt_cyccnt", "dwt_delta_cyc", "dwt_period_us", "dwt_lateness_ms"],
    ).to_csv(dwt_path, index=False)

    # Referee: interval_cyc 800000000, 1600800, 1600800, 1600960 with matching interval_us, jitter_ms, is_miss
    ref_rows = [
        [0, 800000000, 5000000.0, 5000.0, 4990.0, 1],
        [1, 1600800, 10005.0, 10.005, 0.005, 0],
        [2, 1600800, 10005.0, 10.005, 0.005, 0],
        [3, 1600960, 10006.0, 10.006, 0.006, 0],
    ]
    pd.DataFrame(
        ref_rows,
        columns=["cycle", "interval_cyc", "interval_us", "interval_ms", "jitter_ms", "is_miss"],
    ).to_csv(ref_path, index=False)

    res = analyze_tag("new", dwt_path, ref_path)

    assert res["referee_clock"] == "dwt"
    assert res["dut_period_mean_us"] == 10005.0
    assert res["ref_period_mean_us"] == pytest.approx(10005.3333, abs=1e-4)
    assert res["ref_vs_dut_ppm"] == pytest.approx(33.317, abs=0.01)
    assert res["ref_misses"] == 0


def test_referee_old_format(tmp_path):
    dwt_path = tmp_path / "config_c_dwt_old.csv"
    ref_path = tmp_path / "config_c_referee_old.csv"

    dwt_rows = [
        [0, 100000, 1600000, 10000.0, 0.0],
        [1, 1700800, 1600800, 10005.0, 0.0],
        [2, 3301600, 1600800, 10005.0, 0.0],
        [3, 4902400, 1600800, 10005.0, 0.0],
    ]
    pd.DataFrame(
        dwt_rows,
        columns=["cycle", "dwt_cyccnt", "dwt_delta_cyc", "dwt_period_us", "dwt_lateness_ms"],
    ).to_csv(dwt_path, index=False)

    # Referee: cycle,interval_us,interval_ms,jitter_ms,is_miss with interval_us 5000000, 10001, 10002, 10003
    ref_rows = [
        [0, 5000000, 5000.0, 4990.0, 1],
        [1, 10001, 10.001, 0.001, 0],
        [2, 10002, 10.002, 0.002, 0],
        [3, 10003, 10.003, 0.003, 0],
    ]
    pd.DataFrame(
        ref_rows,
        columns=["cycle", "interval_us", "interval_ms", "jitter_ms", "is_miss"],
    ).to_csv(ref_path, index=False)

    res = analyze_tag("old", dwt_path, ref_path)

    assert res["referee_clock"] == "k_cycle_us"
    assert res["ref_period_mean_us"] == 10002.0


def test_run_comparison_pipeline(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_md = tmp_path / "out" / "referee_vs_dut.md"

    test_referee_new_format(raw_dir)
    run_comparison(raw_dir, out_md)

    assert out_md.exists()
    assert out_md.with_suffix(".csv").exists()

