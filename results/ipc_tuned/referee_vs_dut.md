# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc_tuned | dwt | 9999 | 9999 | 10002.7732 | 10002.7723 | -0.09 | 0.6057 | 7.9250 | 0 |
| 100_ipc_tuned | dwt | 9999 | 9999 | 10002.7729 | 10002.8072 | 3.43 | 0.4832 | 7.7563 | 0 |
| 50_ipc_tuned | dwt | 9999 | 9999 | 10002.7734 | 10002.8104 | 3.70 | 0.4937 | 7.8875 | 0 |
| sanity_ipc_tuned | dwt | 19 | 19 | 10002.7730 | 10002.7628 | -1.02 | 0.5800 | 3.6750 | 0 |
