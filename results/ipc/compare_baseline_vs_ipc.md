# Config C Baseline vs. IPC Comparison

| Stress | σ_L (µs) | p99.9 (µs) | WCL (µs) | DMR @ 1 ms | ΔWCL IPC − re-run (µs) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 0% | 2.60 / 15.22 / 40.59 | 10.29 / 54.82 / 663.36 | 10.32 / 54.96 / 762.50 | 0.00% / 0.00% / 0.00% | +707.54 |
| 50% | 12.24 / 15.22 / 49.55 | 44.41 / 54.85 / 736.56 | 44.57 / 54.97 / 813.09 | 0.00% / 0.00% / 0.00% | +758.12 |
| 100% | 13.42 / 14.21 / 51.12 | 49.03 / 51.24 / 727.40 | 49.08 / 51.38 / 820.20 | 0.00% / 0.00% / 0.00% | +768.82 |

Cells show `P4.5 / re-run / IPC`.

P4.5 = Config C baseline (no IPC), original runs. Re-run = same sketch, DWT-based referee. IPC = Phase 5. Same timing loop and stress-ng commands; lateness is wake-only, relative to the best cycle, period fitted (see benchmarks/analysis/README.md); one run per condition.
