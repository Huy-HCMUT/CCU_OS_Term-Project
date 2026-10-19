# Clock Diagnostics Summary

- **Date:** 2026-10-19T16:56:54.559733
- **DUT ID:** `3125036249`
- **Container:** `tmp-pin_test-main-1`
- **Core Version:** `arduino:zephyr 0.90.0`

| Test | Param | Reps | ppm (DWT vs k_cycle) | median ppm (DWT vs k_cycle) | median lost_cyc | median dwt_cyc | outlier reps | k_cycle / (160·micros) | DWT − 160·micros (cycles) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `test_clock_ratio_busy` | 100 | 10/10 | +102.91 ± 263.75 | +19.2 | 307 | 16,000,666 | [9] | 1.0000006 ± 0.0000025 | +1,656.6 ± 4206.2 |
| `test_clock_ratio_busy` | 1000 | 10/10 | +102.17 ± 263.55 | +18.8 | 3,007 | 160,003,432 | [8] | 0.9999999 ± 0.0000004 | +16,337.8 ± 42168.0 |
| `test_clock_ratio_sleep` | 100 | 10/10 | +480.95 ± 2.42 | +482.7 | 7,732 | 16,022,700 | none | 0.9999999 ± 0.0000041 | +7,699.0 ± 101.5 |
| `test_clock_ratio_sleep` | 1000 | 10/10 | +508.23 ± 0.24 | +508.4 | 81,346 | 160,088,460 | none | 1.0000000 ± 0.0000002 | +81,329.1 ± 44.1 |
| `test_loop_sleep_vs_spin` | 0 | 10/10 | +185.51 ± 351.41 | +18.8 | 1,506 | 80,001,596 | [7, 8] | 0.9999999 ± 0.0000009 | +14,831.0 ± 28099.1 |
| `test_loop_sleep_vs_spin` | 1 | 10/10 | +281.03 ± 0.28 | +281.2 | 22,493 | 80,022,522 | none | 1.0000001 ± 0.0000008 | +22,486.6 ± 64.5 |

## Outcome

Criteria from `PLAN.md` step 5. Medians from the table above; outlier reps are reported, not removed.

| Test | Plan criterion (sleep explanation right) | Measured (median) | Verdict |
| :--- | :--- | :--- | :--- |
| `busy` 100 vs 1000 ms | same lost cycles at both durations (fixed read overhead) | lost 307 → 3,007 cycles (scales ×10): a real rate loss of ≈ +19 ppm | **Does not match** |
| `ratio_kcyc_micros` | 1.0000 ± 0.00001 | 0.9999999–1.0000006 | **Matches** |
| `loop` without sleep | ≈ 80,000,000 cycles, \|ppm\| < 50 | 80,001,596 (+19.9 ppm) | **Matches** |
| `loop` with sleep | ≈ 80,043,640 (+545 ppm) ± 4,000 cycles | 80,022,522 (+281.5 ppm) | **Does not match** |
| `sleep` 100 / 1000 ms | clearly positive ppm | +482.7 / +508.4 ppm | **Matches** |

### Findings
1. `micros()` = `k_cycle_get_32()` / 160 exactly (rounding only), as in the Arduino Zephyr core source.
2. Zephyr's cycle counter loses time against DWT: ≈ 19 ppm while the CPU is busy and ≈ 508 ppm while it sleeps in `delay()`. DWT and SysTick count the same 160 MHz clock, so this is cycles dropped by Zephyr's timekeeping, not two clocks running at different rates.
3. Single events lost much more: 13,657 / 136,357 / 68,256 / 68,106 cycles (≈ 85 / 852 / 427 / 426 µs) in 4 of 30 busy or spin reps. The cause is not established; one candidate is interrupts being blocked (e.g. by the RouterBridge serial link) for longer than a SysTick period.
4. The diagnostic 10 ms loop with `delay(6)` loses +281 ppm, close to the ≈ 313 ppm predicted from finding 2 (60 % asleep). The benchmark sketch on the same core shows +536 ppm (sanity run, 19 intervals) and +545.5 ppm (published runs). **About half of the benchmark drift is not reproduced by the diagnostic loop and is still unexplained.**
