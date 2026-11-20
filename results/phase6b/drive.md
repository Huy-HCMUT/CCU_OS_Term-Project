# Phase 6b Full-Chain Drive Actuation Summary

## Tier Summary (`C act tuned`)

| Tier | n runs | writes | lost | wrong | extra | drive_seen p50 µs | drive_seen p99 µs | drive_seen max µs | write_cost max µs | rtt_p99 µs | chain_bound upper bound ms |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2 | 480 | 0 | 0 | 0 | 2774.5 | 4083.2 | 4106.8 | 7.96 | 12841.6 | 26.925 |
| rdeploy | 2 | 480 | 0 | 0 | 0 | 2858.6 | 4083.7 | 4107.1 | 7.96 | 14688.3 | 28.767 |
| rnet | 2 | 480 | 0 | 0 | 0 | 2787.4 | 4069.8 | 4102.8 | 8.02 | 12657.6 | 26.712 |
| rboth | 2 | 480 | 0 | 0 | 0 | 2786.8 | 4080.0 | 4099.8 | 8.02 | 15744.8 | 29.818 |

## Per-Run Details & Drive Health

| Folder | Tier | Rep | writes match | pre_run | lost / wrong / extra | drive_start p50/p99/max µs | drive_seen p50/p99/max µs | write_offset min/p50/max µs | write_cost max µs | ticks (10k?) | pout / lerr / drop | initial_duty | board3 tick min–max µs | age_p99 cyc | unobs_ok |
| :--- | :--- | ---: | :--- | ---: | :--- | :--- | :--- | :--- | ---: | :--- | :--- | ---: | :--- | ---: | ---: |
| act_tuned | 0 | 1 | True | 0 | 0 / 0 / 0 | 1536.9 / 2491.2 / 2506.8 | 2826.4 / 4083.2 / 4106.8 | 500.70 / 500.73 / 500.73 | 7.96 | 10000 (OK) | 0 / 0 / 0 | 0.8002 | 9997.5–10007.7 | 8.0 | 0 |
| act_tuned_r2 | 0 | 2 | True | 0 | 0 / 0 / 0 | 1423.7 / 2470.7 / 2499.4 | 2722.7 / 4035.5 / 4086.9 | 500.70 / 500.73 / 500.73 | 7.96 | 10000 (OK) | 0 / 0 / 0 | 0.8002 | 9997.4–10008.0 | 8.0 | 0 |
| act_tuned_rdeploy | rdeploy | 1 | True | 0 | 0 / 0 / 0 | 1599.9 / 2489.2 / 2507.2 | 2856.1 / 4079.2 / 4107.1 | 500.70 / 500.73 / 500.73 | 7.96 | 10000 (OK) | 0 / 0 / 0 | 0.8001 | 9996.5–10008.3 | 8.0 | 0 |
| act_tuned_rdeploy_r2 | rdeploy | 2 | True | 0 | 0 / 0 / 0 | 1584.5 / 2497.1 / 2503.2 | 2861.2 / 4083.7 / 4100.0 | 500.70 / 500.73 / 500.73 | 7.96 | 10000 (OK) | 0 / 0 / 0 | 0.8002 | 9997.4–10007.5 | 8.0 | 0 |
| act_tuned_rnet | rnet | 1 | True | 0 | 0 / 0 / 0 | 1607.3 / 2479.8 / 2502.8 | 2858.9 / 4054.7 / 4102.8 | 500.70 / 500.73 / 500.73 | 7.96 | 10000 (OK) | 0 / 0 / 0 | 0.8001 | 9996.6–10007.3 | 8.0 | 0 |
| act_tuned_rnet_r2 | rnet | 2 | True | 0 | 0 / 0 / 0 | 1429.1 / 2489.6 / 2501.1 | 2715.8 / 4069.8 / 4089.9 | 500.70 / 500.73 / 500.73 | 8.02 | 10000 (OK) | 0 / 0 / 0 | 0.8001 | 9997.7–10007.8 | 8.0 | 0 |
| act_tuned_rboth | rboth | 1 | True | 0 | 0 / 0 / 0 | 1417.5 / 2485.1 / 2502.0 | 2698.2 / 4072.8 / 4099.8 | 500.70 / 500.73 / 500.73 | 7.96 | 10000 (OK) | 0 / 0 / 0 | 0.8001 | 9997.3–10008.0 | 8.0 | 0 |
| act_tuned_rboth_r2 | rboth | 2 | True | 0 | 0 / 0 / 0 | 1585.4 / 2486.2 / 2496.6 | 2875.5 / 4080.0 / 4096.5 | 500.70 / 500.73 / 500.73 | 8.02 | 10000 (OK) | 0 / 0 / 0 | 0.8001 | 9996.7–10008.0 | 8.0 | 0 |

## Notes

- **Chain bound (`chain_bound_ms`):** `rtt_p99_us / 1000 + 10 + drive_seen_p99_us / 1000` — **upper bound (sum of p99s: send → stored, ≤ 1 tick wait, tick → drive sees it)**.
- **Duty encoding:** `duty = 0.8 × setpoint`, so the emulated drive decodes `decoded_pct = 125 × high_cyc / period_cyc`. A matched event is counted as `wrong` if `|decoded_pct − setpoint_pct| > 2`. Events with `tick_idx < 0` occur before tick 0 (the `reset_ipc` write back to 100%) and are counted separately as `pre_run_events`.
- **PWM modulation delay:** The PWM portion of `drive_seen_us` (waiting for the next 2 ms period boundary plus the 0.96–1.60 ms high pulse) is fixed by 500 Hz PWM hardware modulation and is not OS behavior.
- **Clock domains:** `drive_start_us` and `drive_seen_us` use Board 3's 160 MHz DWT clock (signed 32-bit differences, no cross-board clock subtraction). `write_offset_us` and `write_cost_us` use the DUT MCU's 160 MHz DWT clock. `rtt_p99_us` uses Linux monotonic time.
- **Scope:** Configs A, B, and B-iso have no physical drive output; Phase 6b drive measurements apply only to `C act tuned`.
