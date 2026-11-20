# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 100_b2_allcore | dwt | 9999 | 9999 | 10005.4547 | 10005.5043 | 4.97 | 0.7239 | 7.9750 | 0 |
| sanity_b2_allcore | dwt | 19 | 19 | 10005.3638 | 10005.3697 | 0.59 | 0.7066 | 6.8062 | 0 |
