"""Tests for analyze_latency.py on small synthetic runs. Run: pytest benchmarks/analysis"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import analyze_latency as al

PERIOD_NS = 10_000_000


def write(path: Path, **cols) -> Path:
    pd.DataFrame(cols).to_csv(path, index=False)
    return path


def test_parse_filename():
    assert al.parse_filename(Path("A_0.csv")) == ("A", 0)
    assert al.parse_filename(Path("b_stress100_run2.csv")) == ("B", 100)
    assert al.parse_filename(Path("C_50_referee-d2.csv")) == ("C", 50)
    assert al.parse_filename(Path("summary.csv")) is None


def test_lateness_column_units(tmp_path):
    run = al.load_run(write(tmp_path / "A_0.csv", lateness_ns=[0, 1500, 250_000]))
    np.testing.assert_allclose(run.lateness_us, [0.0, 1.5, 250.0])
    assert run.source_format == "lateness"


def test_release_and_wake_keep_precision_on_large_timestamps(tmp_path):
    t0 = 9_876_543_210_123_456_789 // 1000  # ~10^16 ns, like a long-running CLOCK_MONOTONIC
    k = np.arange(5)
    release = t0 + k * PERIOD_NS
    wake = release + np.array([1, 2, 3, 400_001, 5])
    run = al.load_run(write(tmp_path / "B_50.csv", release_ns=release, wake_ns=wake))
    np.testing.assert_allclose(run.lateness_us, [0.001, 0.002, 0.003, 400.001, 0.005])
    np.testing.assert_allclose(run.period_us[:3], [10_000.001, 10_000.001, 10_399.998])


def test_wake_only_fit_removes_clock_drift(tmp_path):
    # Referee clock runs 50 ppm fast: without fitting, lateness would ramp to ~5 ms.
    k = np.arange(10_000)
    true_late_ns = np.zeros(k.size)
    true_late_ns[5000] = 300_000
    wake = ((k * PERIOD_NS + true_late_ns) * (1 + 50e-6)).astype(np.int64)
    path = write(tmp_path / "C_100.csv", wake_ns=wake)

    fitted = al.load_run(path, period_mode="fit")
    assert fitted.lateness_us.max() == pytest.approx(300.0 * (1 + 50e-6), abs=0.5)
    assert np.percentile(fitted.lateness_us, 99) < 1.0
    assert "+50.0 ppm" in " ".join(fitted.notes)

    nominal = al.load_run(path, period_mode="nominal")
    assert nominal.lateness_us.max() > 4_000.0


def test_wake_cycles_unwrap_32bit_counter(tmp_path):
    clock_hz = 160e6
    k = np.arange(4000)  # 40 s at 10 ms: wraps the 32-bit counter once
    ticks = (k * 1_600_000 + 123) % (1 << 32)
    ticks[1000] += 16_000  # one cycle 100 us late
    run = al.load_run(write(tmp_path / "C_0.csv", wake_cyc=ticks),
                      clock_hz=clock_hz, period_mode="nominal")
    assert run.lateness_us.max() == pytest.approx(100.0)
    assert np.sum(run.lateness_us > 1e-6) == 1


def test_cycles_need_clock_rate(tmp_path):
    with pytest.raises(ValueError, match="--clock-hz"):
        al.load_run(write(tmp_path / "C_0.csv", wake_cyc=[0, 1_600_000]))


def test_cycle_column_accounts_for_missing_samples(tmp_path):
    k = np.array([0, 1, 3, 4])
    run = al.load_run(write(tmp_path / "A_0.csv", cycle=k, wake_ns=k * PERIOD_NS),
                      period_mode="nominal")
    np.testing.assert_allclose(run.lateness_us, 0.0)
    assert "1 cycle(s) missing" in " ".join(run.notes)


def test_dmr_is_strictly_greater_than_tolerance():
    lat = np.array([999.0, 1000.0, 1000.001, 50.0])
    assert al.dmr(lat, 1.0) == 25.0
    assert al.dmr(lat, 0.2) == 75.0


def test_warmup_and_max_cycles(tmp_path):
    lat = np.r_[np.full(10, 5_000_000), np.zeros(100)]
    run = al.load_run(write(tmp_path / "A_0.csv", lateness_ns=lat))
    trimmed = al.trim(run, warmup=10, max_cycles=50)
    assert trimmed.lateness_us.size == 50
    assert trimmed.lateness_us.max() == 0.0


def test_summary_metrics():
    lat = np.r_[np.full(997, 100.0), 300.0, 1_500.0, 45_000.0]
    run = al.Run("B", 100, Path("B_100.csv"), lat, np.full(999, 10_000.0), "lateness")
    row = al.summarize("B", 100, [run], (1.0, 0.2))
    assert row["cycles"] == 1000
    assert row["wcl_max_us"] == 45_000.0
    assert row["misses_1000us"] == 2 and row["dmr_1000us_pct"] == pytest.approx(0.2)
    assert row["misses_200us"] == 3 and row["dmr_200us_pct"] == pytest.approx(0.3)
    assert row["severe_starvation_40ms"] == 1


def test_cli_end_to_end(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rng = np.random.default_rng(0)
    for cfg, scale in [("A", 400_000), ("B", 20_000), ("C", 1_000)]:
        for stress in (0, 100):
            write(raw / f"{cfg}_{stress}.csv",
                  lateness_ns=rng.exponential(scale, 2_000).astype(np.int64))
    (raw / "notes.csv").write_text("ignored\n")

    out = tmp_path / "out"
    assert al.main(["--raw", str(raw), "--out", str(out), "--warmup", "100"]) == 0
    summary = pd.read_csv(out / "summary.csv")
    assert len(summary) == 6
    assert set(summary["cycles"]) == {1_900}
    assert {"dmr_1000us_pct", "dmr_200us_pct"} <= set(summary.columns)
    assert (out / "summary.md").read_text().startswith("| Config")
    for name in ("dmr_vs_tolerance", "lateness_cdf", "lateness_boxplot", "lateness_timeseries"):
        assert (out / "plots" / f"{name}.png").stat().st_size > 0


def test_tags_become_separate_series():
    assert al.parse_tag(Path("C_50.csv")) == ""
    assert al.parse_tag(Path("C_50_IPC.csv")) == "ipc"
    assert al.parse_tag(Path("C_50_ipc_run2.csv")) == "ipc"
    assert al.parse_tag(Path("C_50_rep3.csv")) == ""
    assert al.parse_tag(Path("C_50_referee.csv")) == "referee"
    assert al.series_label("C") == "C · Zephyr baseline (no IPC)"
    assert al.series_label("C-ipc") == "C · Zephyr · with IPC"
    assert al.series_label("C-ipc_referee") == "C · Zephyr · with IPC, referee board"
    assert al.series_label("C-ipc", {"C-ipc": "custom"}) == "custom"


def test_variant_colors_are_stable_and_distinct():
    colors = al._color_map(["A", "B", "C", "C-ipc", "C-rerun"])
    assert colors["A"] == al.CONFIG_COLORS[0] and colors["C"] == al.CONFIG_COLORS[2]
    assert len(set(colors.values())) == 5
    # Dropping A must not repaint C or the variants' base slots.
    assert al._color_map(["C", "C-ipc"])["C"] == colors["C"]


def test_cli_keeps_baseline_ipc_and_referee_apart(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    k = np.arange(1_000)
    base = k * PERIOD_NS
    write(raw / "C_100.csv", wake_ns=base)
    write(raw / "C_100_ipc.csv", wake_ns=base + np.where(k == 500, 80_000, 0))
    write(raw / "C_100_ipc_run2.csv", wake_ns=base)
    write(raw / "C_100_referee.csv", wake_us=base / 1000)
    write(raw / "B_100.csv", lateness_ns=np.full(1_000, 50_000))

    out = tmp_path / "out"
    assert al.main(["--raw", str(raw), "--out", str(out), "--period-mode", "nominal"]) == 0
    summary = pd.read_csv(out / "summary.csv", keep_default_na=False)
    assert list(summary["series"]) == ["B", "C", "C-ipc", "C-referee"]
    by = summary.set_index("series")
    assert by.loc["C", "cycles"] == 1_000 and by.loc["C", "wcl_max_us"] == 0
    assert by.loc["C-ipc", "cycles"] == 2_000          # the run2 repeat is pooled
    assert by.loc["C-ipc", "wcl_max_us"] == pytest.approx(80.0)
    assert "C · Zephyr · with IPC" in (out / "summary.md").read_text()

    out2 = tmp_path / "out2"
    assert al.main(["--raw", str(raw), "--out", str(out2), "--period-mode", "nominal",
                    "--series", "c", "C-IPC", "--label", "C-ipc=C · IPC run"]) == 0
    s2 = pd.read_csv(out2 / "summary.csv", keep_default_na=False)
    assert list(s2["series"]) == ["C", "C-ipc"]
    assert "C · IPC run" in (out2 / "summary.md").read_text()
    assert (out2 / "plots" / "lateness_boxplot.png").stat().st_size > 0
