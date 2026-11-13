from pathlib import Path
import pandas as pd
import pytest

from pulse_pattern import analyze_dwt_file, run


def _write_synth_dwt(path: Path, n_rows: int = 1001, disturb: bool = True) -> None:
    rows = []
    prev_cyc = 0
    for i in range(n_rows):
        cyc = i * 1_600_000 + (8_000 if (disturb and i > 0 and i % 11 == 0) else 0)
        delta = 1_600_000 if i == 0 else (cyc - prev_cyc)
        rows.append(
            {
                "cycle": i,
                "dwt_cyccnt": cyc,
                "dwt_delta_cyc": delta,
                "dwt_period_us": f"{delta / 160.0:.3f}",
                "dwt_lateness_ms": "0.00000",
            }
        )
        prev_cyc = cyc
    pd.DataFrame(rows).to_csv(path, index=False)


def test_pulse_pattern_disturbed_and_clean(tmp_path):
    disturbed_csv = tmp_path / "config_c_dwt_disturbed.csv"
    clean_csv = tmp_path / "config_c_dwt_clean.csv"
    _write_synth_dwt(disturbed_csv, n_rows=1001, disturb=True)
    _write_synth_dwt(clean_csv, n_rows=1001, disturb=False)

    res_dist = analyze_dwt_file(disturbed_csv)
    assert res_dist["n_intervals"] == 1000
    assert res_dist["n_disturbed"] == 180
    assert res_dist["gap_set"] == "1;10"
    assert res_dist["late_dev_median_us"] == "50.0"

    res_clean = analyze_dwt_file(clean_csv)
    assert res_clean["n_intervals"] == 1000
    assert res_clean["n_disturbed"] == 0
    assert res_clean["gap_set"] == ""
    assert res_clean["late_dev_median_us"] == ""

    out_md = tmp_path / "pulse_pattern.md"
    run([tmp_path], out_md)
    assert out_md.exists()
    out_csv = out_md.with_suffix(".csv")
    assert out_csv.exists()
    df = pd.read_csv(out_csv, keep_default_na=False)
    assert len(df) == 2

