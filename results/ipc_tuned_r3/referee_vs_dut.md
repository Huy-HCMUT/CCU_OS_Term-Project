# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc_tuned | dwt | 9999 | 9999 | 10002.7732 | 10002.7812 | 0.80 | 0.5588 | 8.4312 | 0 |
| 100_ipc_tuned | dwt | 9999 | 9999 | 10002.7731 | 10002.8165 | 4.34 | 0.4846 | 7.9250 | 0 |
| 50_ipc_tuned | dwt | 9999 | 9999 | 10002.7732 | 10002.8160 | 4.28 | 0.6127 | 8.4062 | 0 |
| sanity_ipc_tuned | dwt | 19 | 19 | 10002.8138 | 10002.8158 | 0.20 | 0.5792 | 3.5688 | 0 |
