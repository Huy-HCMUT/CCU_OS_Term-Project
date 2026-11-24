#!/usr/bin/env python3
"""Uncertainty for the headline realistic-load claims (Phase 6a/6b).

Adds the error bars that `compare_realload.py` does not report, using exactly the
same runs and the same lateness definition (L_rel, 10,000-cycle blocks):

1. Deadline misses (L_rel > 1 ms): pooled miss ratio with a 95 % Wilson interval,
   or, for zero misses, the exact one-sided 95 % upper bound 1 - 0.05**(1/n)
   (about 3/n, the "rule of three"). Per-run ratios are listed too: when they
   disagree by more than their intervals, run-to-run variation, not counting
   noise, is the real uncertainty.
2. Typical worst case per 10,000-cycle block: median of the pooled block WCLs
   with a 95 % bootstrap interval (blocks resampled with replacement).
3. Ratio of a Linux config's block median to Config C's. Config C has only one
   block per run (10,000 cycles), so its uncertainty cannot be bootstrapped; the
   ratio range divides the Linux interval by C's worst and best block.

Caveat: blocks within one run are not independent (load phases last longer than
100 s), so the bootstrap interval is narrower than a repeat-level interval would be.

Writes results/phase6b/headline_stats.{md,csv}.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_realload import _collect_realload_runs  # noqa: E402

DEADLINE_US = 1000.0
TIERS = ["rnet", "rdeploy", "rboth"]
LINUX = ["A", "B", "B-iso"]
C_SERIES = "C act tuned"
N_BOOT = 10_000


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95 % Wilson score interval for a binomial proportion k/n."""
    if n <= 0:
        return (math.nan, math.nan)
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def zero_upper(n: int, conf: float = 0.95) -> float:
    """Exact one-sided upper bound on the miss probability after 0 misses in n trials."""
    return 1.0 - (1.0 - conf) ** (1.0 / n)


def bootstrap_median_ci(x: np.ndarray, n_boot: int = N_BOOT, seed: int = 0) -> tuple[float, float]:
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        return (math.nan, math.nan)
    rng = np.random.default_rng(seed)
    meds = np.median(rng.choice(x, size=(n_boot, x.size), replace=True), axis=1)
    return (float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5)))


def summarize(records: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """records: dicts with series, tier, rep, _l_rel (µs), _block_wcls (µs)."""
    rows = []
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        groups.setdefault((r["series"], r["tier"]), []).append(r)
    for (series, tier), runs in groups.items():
        runs = sorted(runs, key=lambda r: r["rep"])
        n = int(sum(r["_l_rel"].size for r in runs))
        k = int(sum(int(np.sum(r["_l_rel"] > DEADLINE_US)) for r in runs))
        blocks = np.concatenate([r["_block_wcls"] for r in runs])
        lo, hi = wilson(k, n) if k else (0.0, zero_upper(n))
        b_lo, b_hi = bootstrap_median_ci(blocks) if blocks.size > 2 else (math.nan, math.nan)
        rows.append({
            "series": series, "tier": tier, "runs": len(runs), "cycles": n, "misses": k,
            "dmr_pct": 100.0 * k / n, "dmr_lo_pct": 100.0 * lo, "dmr_hi_pct": 100.0 * hi,
            "dmr_per_run_pct": ";".join(f"{100.0 * np.mean(r['_l_rel'] > DEADLINE_US):.4f}" for r in runs),
            "blocks": int(blocks.size),
            "block_median_us": float(np.median(blocks)), "block_median_lo_us": b_lo,
            "block_median_hi_us": b_hi,
            "block_min_us": float(blocks.min()), "block_max_us": float(blocks.max()),
            "block_median_per_run_us": ";".join(f"{np.median(r['_block_wcls']):.1f}" for r in runs),
        })
    stats = pd.DataFrame(rows)

    ratios = []
    for tier in TIERS:
        c = stats[(stats.series == C_SERIES) & (stats.tier == tier)]
        if c.empty:
            continue
        c = c.iloc[0]
        for s in LINUX:
            l = stats[(stats.series == s) & (stats.tier == tier)]
            if l.empty:
                continue
            l = l.iloc[0]
            ratios.append({
                "tier": tier, "linux": s,
                "ratio": l.block_median_us / c.block_median_us,
                "ratio_lo": l.block_median_lo_us / c.block_max_us,
                "ratio_hi": l.block_median_hi_us / c.block_min_us,
            })
    return stats, pd.DataFrame(ratios)


def _order(df: pd.DataFrame) -> pd.DataFrame:
    s_rank = {s: i for i, s in enumerate(LINUX + [C_SERIES])}
    t_rank = {t: i for i, t in enumerate(["0"] + TIERS)}
    return df.assign(_s=df.series.map(s_rank), _t=df.tier.map(t_rank)).sort_values(
        ["_t", "_s"]).drop(columns=["_s", "_t"])


def _pct(v: float) -> str:
    return f"{v:.4f}" if v < 0.1 else f"{v:.2f}"


def build_markdown(stats: pd.DataFrame, ratios: pd.DataFrame) -> str:
    out = ["# Headline Uncertainty: Realistic Load (Phase 6a/6b)", "",
           "Same runs and lateness definition (`L_rel`) as `realload.md`; generated by "
           "`benchmarks/analysis/headline_stats.py`.", "",
           "## Deadline misses (L_rel > 1 ms)", "",
           "| Series | Tier | Runs | Cycles | Misses | Miss ratio % | 95 % interval % | Per run % |",
           "| :--- | :--- | ---: | ---: | ---: | ---: | :--- | :--- |"]
    for _, r in _order(stats).iterrows():
        ci = (f"≤ {_pct(r.dmr_hi_pct)} (one-sided, 0 misses)" if r.misses == 0
              else f"{_pct(r.dmr_lo_pct)}–{_pct(r.dmr_hi_pct)}")
        per = ", ".join(_pct(float(v)) for v in r.dmr_per_run_pct.split(";"))
        out.append(f"| {r.series} | {r.tier} | {r.runs} | {r.cycles:,} | {r.misses:,} | "
                   f"{_pct(r.dmr_pct)} | {ci} | {per} |")
    out += ["", "## Typical worst case per 10,000-cycle block", "",
            "| Series | Tier | Blocks | Block median µs | 95 % bootstrap interval µs | Per-run medians µs | Block min–max µs |",
            "| :--- | :--- | ---: | ---: | :--- | :--- | :--- |"]
    for _, r in _order(stats).iterrows():
        ci = ("n/a (1 block per run)" if math.isnan(r.block_median_lo_us)
              else f"{r.block_median_lo_us:.1f}–{r.block_median_hi_us:.1f}")
        per = ", ".join(r.block_median_per_run_us.split(";"))
        out.append(f"| {r.series} | {r.tier} | {r.blocks} | {r.block_median_us:.1f} | {ci} | "
                   f"{per} | {r.block_min_us:.1f}–{r.block_max_us:.1f} |")
    out += ["", "## Linux block median ÷ Config C block median", "",
            "| Tier | Linux config | Ratio | Range |", "| :--- | :--- | ---: | :--- |"]
    for _, r in ratios.iterrows():
        out.append(f"| {r.tier} | {r.linux} | {r.ratio:.0f}× | {r.ratio_lo:.0f}–{r.ratio_hi:.0f}× |")
    out += ["", "## Notes", "",
            "- **Miss intervals:** Wilson score interval (95 %); with 0 misses, the exact one-sided "
            "95 % upper bound `1 − 0.05^(1/n)` (≈ 3/n).",
            "- **Runs disagree more than counting noise allows** when the per-run ratios fall outside "
            "each other's intervals (e.g. A under `rboth`). Then the pooled interval understates the "
            "uncertainty; quote the per-run range.",
            "- **Block intervals:** bootstrap of the median over pooled blocks (10,000 resamples). "
            "Blocks in one run are correlated, so this interval is optimistic.",
            "- **Ratio range:** Linux bootstrap interval divided by Config C's worst and best block "
            "(C has 1 block per run, 2 per tier).", ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--raw", type=Path, default=repo / "results" / "raw")
    p.add_argument("--out", type=Path, default=repo / "results" / "phase6b")
    args = p.parse_args(argv)

    records = [r for r in _collect_realload_runs(args.raw) if r["series"] in LINUX + [C_SERIES]]
    if not records:
        print(f"no realistic-load runs under {args.raw}", file=sys.stderr)
        return 1
    stats, ratios = summarize(records)
    args.out.mkdir(parents=True, exist_ok=True)
    md = build_markdown(stats, ratios)
    (args.out / "headline_stats.md").write_text(md, encoding="utf-8")
    _order(stats).to_csv(args.out / "headline_stats.csv", index=False, float_format="%.6g")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
