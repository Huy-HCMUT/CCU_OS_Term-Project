# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 100_ipc_allcore | dwt | 9999 | 9999 | 10005.3951 | 10005.4486 | 5.34 | 53.7393 | 757.3000 | 0 |
| sanity_ipc_allcore | dwt | 19 | 19 | 10005.4263 | 10005.4316 | 0.53 | 0.8922 | 7.0063 | 0 |
