# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_b2 | dwt | 9999 | 9999 | 10005.4562 | 10005.4575 | 0.13 | 7.2937 | 23.7875 | 0 |
| 100_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.5046 | 5.00 | 21.5760 | 57.1750 | 0 |
| 50_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.4944 | 3.99 | 22.2897 | 59.5312 | 0 |
| sanity_b2 | dwt | 19 | 19 | 10005.4069 | 10005.4049 | -0.20 | 6.3243 | 25.2125 | 0 |
