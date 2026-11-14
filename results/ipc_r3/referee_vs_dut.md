# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc | dwt | 9999 | 9999 | 10005.3953 | 10005.3980 | 0.27 | 59.2090 | 752.3687 | 0 |
| 100_ipc | dwt | 9999 | 9999 | 10005.3922 | 10005.4372 | 4.49 | 72.4221 | 795.7812 | 0 |
| 50_ipc | dwt | 9999 | 9999 | 10005.3965 | 10005.4396 | 4.30 | 67.3971 | 754.1812 | 0 |
| sanity_ipc | dwt | 19 | 19 | 10006.8234 | 10006.8188 | -0.46 | 176.0569 | 532.2812 | 0 |
