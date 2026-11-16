# Phase 5d Cross-Configuration Comparison

| Series | 0% n | 0% WCL µs mean [min–max] | 0% σ_L µs mean | 0% DMR@1 ms max % | 50% n | 50% WCL µs mean [min–max] | 50% σ_L µs mean | 50% DMR@1 ms max % | 100% n | 100% WCL µs mean [min–max] | 100% σ_L µs mean | 100% DMR@1 ms max % | all-core n | all-core WCL µs mean [min–max] | all-core σ_L µs mean | all-core DMR@1 ms max % |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 3 | 544.9 [520.5–562.6] | 35.9 | 0.00 | 3 | 5304.1 [4616.0–5843.5] | 783.6 | 12.08 | 3 | 6320.5 [5991.9–6974.9] | 1408.0 | 39.23 | 3 | 21579.7 [18000.4–27851.9] | 960.7 | 10.09 |
| B | 3 | 470.5 [433.2–516.4] | 30.5 | 0.00 | 3 | 755.2 [352.7–973.3] | 45.0 | 0.00 | 3 | 489.2 [378.0–652.8] | 38.2 | 0.00 | 3 | 661.0 [552.4–769.9] | 29.9 | 0.00 |
| B-iso | 3 | 95.9 [90.0–107.6] | 2.2 | 0.00 | 3 | 324.0 [302.5–357.4] | 17.3 | 0.00 | 3 | 328.7 [315.9–354.2] | 19.7 | 0.00 | 3 | 323.6 [275.0–388.1] | 23.3 | 0.00 |
| C baseline stock | 4 | 20.3 [3.4–55.0] | 5.5 | 0.00 | 4 | 36.4 [2.9–55.0] | 10.0 | 0.00 | 4 | 41.2 [9.2–52.6] | 11.4 | 0.00 | 2 | 8.7 [3.4–14.0] | 2.2 | 0.00 |
| C IPC stock | 3 | 759.2 [755.6–762.5] | 41.2 | 0.00 | 3 | 795.3 [772.3–813.1] | 48.2 | 0.00 | 3 | 809.1 [802.3–820.2] | 49.4 | 0.00 | 1 | 758.6 [758.6–758.6] | 38.3 | 0.00 |
| C baseline tuned | 3 | 1.7 [1.5–2.1] | 0.3 | 0.00 | 3 | 1.6 [1.5–1.9] | 0.3 | 0.00 | 3 | 1.5 [1.5–1.5] | 0.4 | 0.00 | 1 | 1.6 [1.6–1.6] | 0.3 | 0.00 |
| C IPC tuned | 3 | 8.1 [6.7–9.3] | 1.2 | 0.00 | 3 | 7.9 [7.7–8.1] | 0.7 | 0.00 | 3 | 7.7 [7.3–8.1] | 0.6 | 0.00 | 1 | 7.8 [7.8–7.8] | 0.7 | 0.00 |

**Relative lateness definition:** For Linux runs (`A`, `B`, `B-iso`), relative lateness is `L_rel = L_abs - min(L_abs)` within each run (wake-up floor `floor_us = min(L_abs)` subtracted). For Config C runs, lateness is wake-only (`wake_cyc` @ 160 MHz) relative to each run's best-case cycle using a least-squares fitted period (`analyze_latency.load_run(..., period_mode='fit')`).

**Additional Linux columns:** Absolute Linux metrics (`wcl_abs_us`, `dmr_1000_abs_pct`) and each run's wake-up floor (`floor_us`) are recorded in `compare_long.csv`.

**Excluded runs:** Phase 2 single runs (`results/raw/A_*.csv`, `results/raw/B_*.csv`) are not included here because they used an earlier binary logging per-process `getrusage(RUSAGE_SELF)` counters; they remain in `results/summary.*`.

**Measured Linux load per tier (median across runs from `config_c_env_*.txt` / `env_*.txt`):**

| Tier | env files | stress-ng procs | cpu0 % | cpu1 % | cpu2 % | cpu3 % |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0% | 15 | 0 | 0.5 | 0.5 | 0.5 | 0.9 |
| 50% | 15 | 5 | 100.0 | 1.5 | 2.0 | 2.0 |
| 100% | 15 | 8 | 100.0 | 1.0 | 1.9 | 1.5 |
| all-core | 11 | 10 | 100.0 | 100.0 | 100.0 | 100.0 |
| allcore (B-iso) | 3 | 9 | 100.0 | 100.0 | 100.0 | 4.5 |
