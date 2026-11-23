"""Tests for replay_animation.py. Run: cd benchmarks/analysis && python -m pytest -q"""

import numpy as np
import pandas as pd

import replay_animation as ra


def test_series_paths_match_the_raw_layout(tmp_path):
    assert ra.series_path(tmp_path, "A", "rboth", 1) == tmp_path / "real_r1" / "A_0_rboth.csv"
    assert ra.series_path(tmp_path, "B-iso", "rnet", 2) == tmp_path / "real_r2" / "B_0_iso_rnet.csv"
    assert ra.series_path(tmp_path, "C", "rboth", 1) == tmp_path / "act_tuned_rboth" / "C_0_act_tuned_rboth.csv"
    assert ra.series_path(tmp_path, "C", "rboth", 2) == tmp_path / "act_tuned_rboth_r2" / "C_0_act_tuned_rboth.csv"


def test_running_stats():
    worst, misses = ra.running_stats(np.array([10.0, 1500.0, 20.0, 2000.0]))
    assert list(worst) == [10.0, 1500.0, 1500.0, 2000.0]
    assert list(misses) == [0, 1, 1, 2]


def test_still_frame_from_synthetic_runs(tmp_path):
    raw = tmp_path / "raw"
    (raw / "real_r1").mkdir(parents=True)
    (raw / "act_tuned_rboth").mkdir()
    n = 300
    for name, late_ms in (("A_0_rboth", np.r_[np.full(n - 1, 0.2), 1.5]), ("B_0_rboth", np.full(n, 0.05))):
        pd.DataFrame({"cycle": np.arange(n), "lateness_ms": late_ms}).to_csv(
            raw / "real_r1" / f"{name}.csv", index=False)
    pd.DataFrame({"cycle": np.arange(n), "wake_cyc": np.arange(n) * 1_600_000}).to_csv(
        raw / "act_tuned_rboth" / "C_0_act_tuned_rboth.csv", index=False)

    a = ra.load_series(raw / "real_r1" / "A_0_rboth.csv", "A")
    assert a.min() == 0.0 and a.max() == 1300.0          # relative to the best cycle

    out = tmp_path / "out"
    assert ra.main(["--raw", str(raw), "--out", str(out), "--still", "5", "--cycles-per-frame", "50"]) == 0
    assert (out / "replay_rboth_r1.png").stat().st_size > 0
