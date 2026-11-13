from pathlib import Path
import pandas as pd

from aggregate_repeats import aggregate


def _write_summary_csv(folder: Path, wcl_0: float, sigma_0: float = 10.0) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for stress in (0, 50, 100):
        rows.append(
            {
                "series": "C-test",
                "config": "C",
                "tag": "test",
                "stress_pct": stress,
                "files": f"C_{stress}.csv",
                "format": "wake-only",
                "cycles": 10000,
                "lateness_mean_us": 5.0,
                "jitter_std_us": sigma_0 + stress * 0.1,
                "lateness_min_us": 0.0,
                "lateness_p50_us": 2.0,
                "lateness_p99_us": 30.0,
                "lateness_p99_9_us": wcl_0 - 2.0 + stress,
                "wcl_max_us": wcl_0 + stress,
                "misses_1000us": 0,
                "dmr_1000us_pct": 0.0,
                "misses_200us": 5,
                "dmr_200us_pct": 0.05,
                "severe_starvation_40ms": 0,
                "period_mean_us": 10005.0,
                "period_std_us": 1.0,
                "notes": "",
            }
        )
    pd.DataFrame(rows).to_csv(folder / "summary.csv", index=False)


def test_aggregate_repeats_exact_match_and_missing(tmp_path):
    res_dir = tmp_path / "results"
    out_dir = res_dir / "phase5b"

    _write_summary_csv(res_dir / "baseline_dwtref", wcl_0=50.0, sigma_0=10.0)
    _write_summary_csv(res_dir / "baseline_dwtref_r2", wcl_0=70.0, sigma_0=20.0)
    _write_summary_csv(res_dir / "ipc", wcl_0=700.0, sigma_0=40.0)
    _write_summary_csv(res_dir / "ipc_tuned", wcl_0=18.0, sigma_0=3.0)

    long_df, md_text = aggregate(res_dir, out_dir)

    assert (out_dir / "repeats_long.csv").exists()
    assert (out_dir / "repeats_summary.md").exists()

    base_rows = long_df[(long_df["variant"] == "baseline, stock") & (long_df["stress_pct"] == 0)]
    assert len(base_rows) == 2

    ipc_rows = long_df[(long_df["variant"] == "IPC, stock") & (long_df["stress_pct"] == 0)]
    assert len(ipc_rows) == 1

    assert "| baseline, stock | 0% | 2 | 15.0 [10.0–20.0] | 58.0 [48.0–68.0] | 60.0 [50.0–70.0] | 0.00 | 0.05 [0.05–0.05] |" in md_text
    assert "| IPC, stock | 0% | 1 |" in md_text
    assert "| IPC, tuned | 0% | 1 |" in md_text
    assert "baseline, tuned" in md_text
    assert "not run" in md_text

