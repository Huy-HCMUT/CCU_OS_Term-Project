# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc | dwt | 9999 | 9999 | 10005.3938 | 10005.4011 | 0.72 | 58.0257 | 741.4000 | 0 |
| 100_ipc | dwt | 9999 | 9999 | 10005.3986 | 10005.4504 | 5.17 | 65.5521 | 789.0750 | 0 |
| 50_ipc | dwt | 9999 | 9999 | 10005.4039 | 10005.4426 | 3.86 | 67.8037 | 792.3563 | 0 |
| sanity_ipc | dwt | 19 | 19 | 10005.3217 | 10005.3253 | 0.36 | 0.7358 | 7.0187 | 0 |
