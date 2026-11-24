"""Tests for headline_stats.py. Run: cd benchmarks/analysis && python -m pytest -q"""

import math

import numpy as np
import pytest

import headline_stats as hs


def test_wilson_known_value():
    # 10 of 100: textbook Wilson 95 % interval is about 5.5 %–17.4 %.
    lo, hi = hs.wilson(10, 100)
    assert lo == pytest.approx(0.0552, abs=5e-4)
    assert hi == pytest.approx(0.1744, abs=5e-4)


def test_zero_upper_is_rule_of_three():
    assert hs.zero_upper(20_000) == pytest.approx(3 / 20_000, rel=0.01)
    assert hs.zero_upper(360_000) < hs.zero_upper(20_000)


def test_bootstrap_median_ci_brackets_the_median():
    x = np.arange(1, 101, dtype=float)
    lo, hi = hs.bootstrap_median_ci(x, n_boot=2_000)
    assert lo < np.median(x) < hi
    assert hs.bootstrap_median_ci(np.full(10, 5.0), n_boot=200) == (5.0, 5.0)


def _rec(series, tier, rep, l_rel, blocks):
    return {"series": series, "tier": tier, "rep": rep,
            "_l_rel": np.asarray(l_rel, dtype=float), "_block_wcls": np.asarray(blocks, dtype=float)}


def test_summarize_counts_misses_and_ratios():
    lin = np.r_[np.full(9_990, 100.0), np.full(10, 1500.0)]          # 10 misses of 10,000
    recs = [
        _rec("B", "rboth", 1, lin, [300.0, 320.0, 1500.0]),
        _rec("B", "rboth", 2, np.full(10_000, 100.0), [280.0, 310.0, 330.0]),
        _rec("C act tuned", "rboth", 1, np.full(10_000, 5.0), [8.0]),
        _rec("C act tuned", "rboth", 2, np.full(10_000, 5.0), [10.0]),
    ]
    stats, ratios = hs.summarize(recs)
    b = stats.set_index("series").loc["B"]
    assert b.cycles == 20_000 and b.misses == 10
    assert b.dmr_pct == pytest.approx(0.05)
    assert b.dmr_lo_pct < 0.05 < b.dmr_hi_pct
    assert b.dmr_per_run_pct == "0.1000;0.0000"
    assert b.block_median_us == pytest.approx(315.0)

    c = stats.set_index("series").loc["C act tuned"]
    assert c.misses == 0 and c.dmr_lo_pct == 0.0
    assert c.dmr_hi_pct == pytest.approx(100 * hs.zero_upper(20_000))
    assert math.isnan(c.block_median_lo_us)                          # 2 blocks: no bootstrap

    r = ratios.set_index("linux").loc["B"]
    assert r.ratio == pytest.approx(315.0 / 9.0)
    assert r.ratio_lo <= r.ratio <= r.ratio_hi

    md = hs.build_markdown(stats, ratios)
    assert "≤ " in md and "35×" in md
