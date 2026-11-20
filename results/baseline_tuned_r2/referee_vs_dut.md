# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_b2_tuned | dwt | 9999 | 9999 | 10002.8125 | 10002.8151 | 0.26 | 0.4727 | 3.7250 | 0 |
| 100_b2_tuned | dwt | 9999 | 9999 | 10002.8125 | 10002.8556 | 4.30 | 0.5107 | 3.8062 | 0 |
| 50_b2_tuned | dwt | 9999 | 9999 | 10002.8124 | 10002.8509 | 3.84 | 0.5076 | 3.8188 | 0 |
| sanity_b2_tuned | dwt | 19 | 19 | 10002.8263 | 10002.8280 | 0.16 | 0.3664 | 3.6250 | 0 |
