# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_b2_tuned | dwt | 9999 | 9999 | 10002.8126 | 10002.8237 | 1.11 | 0.4506 | 3.9438 | 0 |
| 100_b2_tuned | dwt | 9999 | 9999 | 10002.8124 | 10002.8475 | 3.52 | 0.5038 | 3.8000 | 0 |
| 50_b2_tuned | dwt | 9999 | 9999 | 10002.8125 | 10002.8481 | 3.56 | 0.3787 | 3.9188 | 0 |
| sanity_b2_tuned | dwt | 19 | 19 | 10002.8138 | 10002.8194 | 0.56 | 0.4673 | 3.5875 | 0 |
