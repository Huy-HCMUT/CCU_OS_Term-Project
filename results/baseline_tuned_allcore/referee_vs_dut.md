# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 100_b2_tuned_allcore | dwt | 9999 | 9999 | 10002.8125 | 10002.8417 | 2.91 | 0.4128 | 4.1000 | 0 |
| sanity_b2_tuned_allcore | dwt | 19 | 19 | 10002.8076 | 10002.7990 | -0.86 | 0.3822 | 3.6250 | 0 |
