# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_b2_tuned | dwt | 9999 | 9999 | 10002.8126 | 10002.8205 | 0.80 | 0.4045 | 3.9625 | 0 |
| 100_b2_tuned | dwt | 9999 | 9999 | 10002.8125 | 10002.8649 | 5.24 | 0.4640 | 3.8188 | 0 |
| 50_b2_tuned | dwt | 9999 | 9999 | 10002.8125 | 10002.8599 | 4.74 | 0.4472 | 4.0125 | 0 |
| sanity_b2_tuned | dwt | 19 | 19 | 10002.8322 | 10002.8378 | 0.56 | 0.5530 | 3.6750 | 0 |
