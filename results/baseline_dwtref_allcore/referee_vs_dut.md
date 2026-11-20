# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 100_b2_allcore | dwt | 9999 | 9999 | 10005.4546 | 10005.4848 | 3.02 | 5.2669 | 19.0125 | 0 |
| sanity_b2_allcore | dwt | 19 | 19 | 10005.3895 | 10005.3747 | -1.48 | 8.6883 | 31.6125 | 0 |
