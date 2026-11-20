# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc_tuned | dwt | 9999 | 9999 | 10002.7735 | 10002.7809 | 0.74 | 0.5607 | 8.3687 | 0 |
| 100_ipc_tuned | dwt | 9999 | 9999 | 10002.7732 | 10002.8149 | 4.16 | 0.5001 | 8.0812 | 0 |
| 50_ipc_tuned | dwt | 9999 | 9999 | 10002.7736 | 10002.8157 | 4.21 | 0.5153 | 8.2188 | 0 |
| sanity_ipc_tuned | dwt | 19 | 19 | 10002.7648 | 10002.7691 | 0.43 | 0.5221 | 3.6125 | 0 |
