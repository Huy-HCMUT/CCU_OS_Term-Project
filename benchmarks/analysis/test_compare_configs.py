from pathlib import Path
import pandas as pd
import pytest

from compare_configs import _parse_linux_file, compare


def _write_linux_csv(path: Path, lateness_ms_vals: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# rusage=thread affinity=-1 analytics_affinity=-1 no_cstates=0",
        "cycle,scheduled_ns,actual_wake_ns,lateness_ms,is_miss,is_starvation,setpoint,nivcsw,minflt",
    ]
    for k, lat in enumerate(lateness_ms_vals):
        sched = k * 10_000_000
        wake = sched + int(round(lat * 1_000_000))
        lines.append(f"{k},{sched},{wake},{lat:.6f},0,0,100,0,0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_c_wake_csv(path: Path, wake_cyc_vals: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"cycle": k, "wake_cyc": cyc} for k, cyc in enumerate(wake_cyc_vals)]
    pd.DataFrame(rows).to_csv(path, index=False)


def test_parse_linux_file_iso_allcore():
    assert _parse_linux_file(Path("B_100_iso_allcore.csv")) == ("B-iso", "allcore")
    assert _parse_linux_file(Path("A_100_allcore.csv")) == ("A", "allcore")
    assert _parse_linux_file(Path("B_50_iso.csv")) == ("B-iso", "50")
    assert _parse_linux_file(Path("A_0.csv")) == ("A", "0")


def test_compare_configs_synthetic_and_archive_ignored(tmp_path):
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "phase5d"

    # Linux run: floor = 0.05 ms = 50.0 us, max = 0.07 ms = 70.0 us -> relative WCL = 20.0 us
    _write_linux_csv(raw_dir / "linux_r1" / "A_0.csv", [0.050, 0.055, 0.060, 0.070])
    _write_linux_csv(raw_dir / "linux_r1" / "B_100_iso_allcore.csv", [0.020, 0.025, 0.030])

    # Config C run: 11 cycles at 1,600,000-cycle steps, midpoint k=5 displaced +1600 cycles (+10.0 us).
    # Because k=5 is the exact center of symmetry, fitted period stays 10000.0 us and wcl_us == 10.0 us.
    wake_cyc = [k * 1_600_000 + (1600 if k == 5 else 0) for k in range(11)]
    _write_c_wake_csv(raw_dir / "ipc_tuned" / "C_0_ipc_tuned.csv", wake_cyc)

    # Ignored files under archive/
    _write_linux_csv(raw_dir / "archive" / "A_0.csv", [9.999, 9.999])
    _write_c_wake_csv(raw_dir / "archive" / "C_0_ipc_tuned.csv", [k * 1_600_000 for k in range(5)])

    long_df, md_text, charts = compare(raw_dir, out_dir)

    assert len(long_df) == 3
    assert all("archive" not in f for f in long_df["file"])

    a_row = long_df[(long_df["series"] == "A") & (long_df["tier"] == "0")].iloc[0]
    assert a_row["floor_us"] == pytest.approx(50.0)
    assert a_row["wcl_us"] == pytest.approx(20.0)
    assert a_row["wcl_abs_us"] == pytest.approx(70.0)

    b_iso_row = long_df[(long_df["series"] == "B-iso") & (long_df["tier"] == "allcore")].iloc[0]
    assert b_iso_row["floor_us"] == pytest.approx(20.0)
    assert b_iso_row["wcl_us"] == pytest.approx(10.0)

    c_row = long_df[(long_df["series"] == "C IPC tuned") & (long_df["tier"] == "0")].iloc[0]
    assert c_row["wcl_us"] == pytest.approx(10.0, abs=1e-6)
    assert pd.isna(c_row["floor_us"])

    assert (out_dir / "compare_long.csv").exists()
    assert (out_dir / "compare_configs.md").exists()
    assert (out_dir / "cdf_100.png").exists()
    assert (out_dir / "cdf_allcore.png").exists()
    assert (out_dir / "wcl_by_tier.png").exists()
    assert len(charts) == 3
    assert "C IPC tuned" in md_text
    assert "B-iso" in md_text

