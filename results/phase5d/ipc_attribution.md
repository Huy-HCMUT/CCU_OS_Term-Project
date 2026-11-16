# Config C IPC Latency Attribution

Late interval definition: `period_us - median(period_us) > 100 µs`. `msg[k]` is true when `applied_seq[k] != applied_seq[k-1]`.

| folder | tag | n_intervals | n_msg | msg_base_rate | n_late | late_with_msg_share | msg_late_share | late_dev_p50_us | late_dev_p90_us | late_dev_max_us |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ipc | 0_ipc | 9999 | 1173 | 0.117 | 91 | 0.747 | 0.058 | 323.6 | 652.6 | 752.7 |
| ipc | 100_ipc | 9999 | 1173 | 0.117 | 121 | 0.752 | 0.078 | 359.4 | 695.4 | 788.1 |
| ipc | 50_ipc | 9999 | 1173 | 0.117 | 120 | 0.717 | 0.073 | 317.5 | 695.5 | 786.3 |
| ipc_r2 | 0_ipc | 9999 | 1173 | 0.117 | 97 | 0.825 | 0.068 | 336.5 | 649.7 | 736.2 |
| ipc_r2 | 100_ipc | 1749 | 205 | 0.117 | 24 | 0.750 | 0.088 | 313.5 | 675.5 | 737.6 |
| ipc_r2 | 50_ipc | 9999 | 1173 | 0.117 | 101 | 0.752 | 0.065 | 339.1 | 732.9 | 787.1 |
| ipc_r3 | 0_ipc | 9999 | 1173 | 0.117 | 87 | 0.816 | 0.061 | 333.4 | 693.6 | 747.1 |
| ipc_r3 | 100_ipc | 9999 | 1173 | 0.117 | 116 | 0.767 | 0.076 | 368.4 | 712.3 | 790.5 |
| ipc_r3 | 50_ipc | 9999 | 1173 | 0.117 | 120 | 0.817 | 0.084 | 350.6 | 702.3 | 749.0 |
| ipc_allcore | 100_ipc_allcore | 9999 | 1172 | 0.117 | 84 | 0.774 | 0.055 | 307.0 | 662.3 | 752.0 |
| ipc_tuned | 0_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned | 100_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned | 50_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned_r2 | 0_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned_r2 | 100_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned_r2 | 50_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned_r3 | 0_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned_r3 | 100_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned_r3 | 50_ipc_tuned | 9999 | 1173 | 0.117 | 0 |  | 0.000 |  |  |  |
| ipc_tuned_allcore | 100_ipc_tuned_allcore | 9999 | 1170 | 0.117 | 0 |  | 0.000 |  |  |  |
