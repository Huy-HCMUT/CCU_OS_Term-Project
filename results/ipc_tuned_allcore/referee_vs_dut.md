# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 100_ipc_tuned_allcore | dwt | 9999 | 9999 | 10002.7735 | 10002.8265 | 5.29 | 0.5987 | 8.4000 | 0 |
| sanity_ipc_tuned_allcore | dwt | 19 | 19 | 10002.8030 | 10002.8115 | 0.86 | 0.5038 | 3.7687 | 0 |
