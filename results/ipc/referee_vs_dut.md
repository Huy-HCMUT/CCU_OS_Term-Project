# Referee vs DUT Clock Comparison Summary

> Both means are in each board's own CPU-clock units. `ref_vs_dut_ppm` is the inter-board offset after the referee's own cycle loss (if any). It is not an offset against true SI time.

| tag | referee_clock | n_dut | n_ref | dut_period_mean_us | ref_period_mean_us | ref_vs_dut_ppm | ref_period_std_us | ref_max_abs_jitter_us | ref_misses |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc | dwt | 9999 | 9999 | 10005.3951 | 10005.3924 | -0.26 | 56.9067 | 757.9562 | 0 |
| 100_ipc | dwt | 9999 | 9999 | 10005.3981 | 10005.4292 | 3.11 | 72.7626 | 800.8062 | 0 |
| 50_ipc | dwt | 9999 | 9999 | 10005.3945 | 10005.4211 | 2.66 | 70.5107 | 791.6437 | 0 |
| sanity_ipc | dwt | 19 | 19 | 10005.4382 | 10005.4336 | -0.46 | 43.3133 | 142.2250 | 0 |
