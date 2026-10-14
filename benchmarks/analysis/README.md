# Latency analysis

`analyze_latency.py` turns raw per-cycle logs from the benchmark runs into the
KPIs defined in `docs/Project_Scope_Statement.md` §4.3.2 and the figures listed in §5.

```bash
pip install -r benchmarks/analysis/requirements.txt
python3 benchmarks/analysis/analyze_latency.py --warmup 2000 --max-cycles 10000
```

By default it reads `results/raw/*.csv` and writes `results/summary.csv`,
`results/summary.md` and four figures under `results/plots/`.

## Input files

One CSV per run, named `<config>_<stress>[_<tag>].csv`, e.g. `A_0.csv`,
`B_100.csv`, `C_50_referee.csv`. Files with the same config and stress level
are pooled. Lines starting with `#` are ignored, so run metadata (kernel
version, CPU affinity, `stress-ng` command) can sit at the top of the file.

Any one of these column layouts works (units: `ns`, `us`, `ms`, `s`, or `cyc`):

| Columns | Use when | How lateness is computed |
| :--- | :--- | :--- |
| `lateness_<unit>` | the device already computed `L_k` | used as is |
| `release_<unit>`, `wake_<unit>` | Linux: `R_k` from the absolute schedule, `t_k` from `clock_gettime` | `t_k − R_k` |
| `wake_<unit>` | only wake timestamps: Zephyr DWT dump, or edges seen by the external referee board on D2 | release schedule rebuilt, see below |

An optional `cycle` column (the index `k`) keeps the schedule correct if
samples were dropped. `*_cyc` columns need `--clock-hz` (STM32U585 DWT:
`--clock-hz 160e6`). A 32-bit counter that wraps around is unwrapped
automatically; at 160 MHz this happens every 26.8 s.

### Wake-only files

When only wake times are known, the script rebuilds `R_k = t0 + k·T`:

- **`T`** is fitted by least squares (`--period-mode fit`, the default). This
  matters for the external referee board: its crystal differs from the
  STM32's by tens of ppm. At 50 ppm that's 0.5 µs per cycle, which would
  add up to about 5 ms of fake lateness over 10,000 cycles. The fitted
  offset is printed as a note. Use `--period-mode nominal` only when the
  timestamps come from the same clock that drives the timer (e.g. DWT on
  the MCU itself).
- **`t0`** is set so the earliest wake has zero lateness. Lateness is then
  relative to the best-case cycle, and any constant offset shared by all
  cycles cannot be seen. State this when comparing to Linux numbers from
  `release+wake` files.

## Options

| Option | Default | Purpose |
| :--- | :--- | :--- |
| `--tolerances MS ...` | `1.0 0.2` | deadline tiers; a miss is `L_k > tolerance` |
| `--warmup N` | `0` | drop the first N cycles of every run |
| `--max-cycles N` | all | keep at most N cycles after warm-up |
| `--raw DIR` / `--out DIR` | `results/raw` / `results` | input and output folders |
| `--plot-floor-us` | `0.1` | lateness below this is drawn at this value on log axes |
| `--no-plots` | off | write only the tables |

## Outputs

- `summary.csv` / `summary.md`: one row per config × stress level. Columns:
  cycle count, mean lateness, jitter `σ_L`, p50/p99/p99.9, worst-case
  lateness, misses and DMR at each tolerance, cycles over 40 ms (severe
  starvation), measured period mean/std, and notes (fitted clock offset,
  missing cycles).
- `plots/dmr_vs_tolerance.png`: miss ratio as a function of tolerance (the
  complementary CDF of lateness), one panel per stress level. Shows where
  each config starts missing deadlines, not just the miss ratio at one
  threshold.
- `plots/lateness_cdf.png`: CDF curves (§5).
- `plots/lateness_boxplot.png`: box plots, whiskers at p0.1/p99.9 (§5).
- `plots/lateness_timeseries.png`: lateness per cycle. Use it to check for
  warm-up transients, drift, and periodic bursts before trusting the
  summary.

## Tests

```bash
cd benchmarks/analysis && python3 -m pytest -q
```

The tests generate small synthetic runs. No synthetic data is committed
under `results/`.
