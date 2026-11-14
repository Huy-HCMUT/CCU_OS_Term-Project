# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.4730 | 1.85 | 0.8314 | 7.8375 | 0 |
| 100_b2 | dwt | 9999 | 9999 | 10005.4552 | 10005.4985 | 4.33 | 3.2223 | 14.0312 | 0 |
| 50_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.4959 | 4.14 | 0.7004 | 6.9625 | 0 |
| sanity_b2 | dwt | 19 | 19 | 10008.1303 | 10008.1438 | 1.35 | 20.5137 | 56.8375 | 0 |
