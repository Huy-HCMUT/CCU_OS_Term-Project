# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.4517 | -0.28 | 22.2895 | 59.4312 | 0 |
| 100_b2 | dwt | 9999 | 9999 | 10005.4546 | 10005.4841 | 2.95 | 20.6885 | 55.8625 | 0 |
| 50_b2 | dwt | 9999 | 9999 | 10005.4545 | 10005.4805 | 2.60 | 22.2918 | 59.5250 | 0 |
| sanity_b2 | dwt | 19 | 19 | 10005.4115 | 10005.4099 | -0.16 | 9.0142 | 33.2000 | 0 |
