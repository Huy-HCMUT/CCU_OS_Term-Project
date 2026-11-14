# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_b2 | dwt | 9999 | 9999 | 10005.4546 | 10005.4573 | 0.26 | 0.8399 | 7.9813 | 0 |
| 100_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.4970 | 4.25 | 20.9109 | 56.1313 | 0 |
| 50_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.4907 | 3.61 | 12.8181 | 37.4188 | 0 |
| sanity_b2 | dwt | 19 | 19 | 10005.4207 | 10005.4204 | -0.03 | 16.9959 | 57.1500 | 0 |
