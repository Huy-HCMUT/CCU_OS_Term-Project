# Config C IPC Telemetry Summary

| tag | cycles | sent | sent_ok | send_errors | skipped_slots | rx_count | first_cycle_with_ipc | distinct_applied | unobserved_ok | setpoint_mismatch | age_p50_cyc | age_p99_cyc | age_max_cyc | rtt_p50_us | rtt_p99_us | rtt_max_us |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc_tuned | 10000 | 1238 | 1238 | 0 | 0 | 1238 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 8654.5500 | 12964.9280 | 22717.0000 |
| 100_ipc_tuned | 10000 | 1263 | 1263 | 0 | 0 | 1263 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 8521.4000 | 12728.7900 | 13954.7000 |
| 50_ipc_tuned | 10000 | 1291 | 1291 | 0 | 0 | 1291 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 8373.6000 | 12891.7200 | 15756.8000 |
| sanity_ipc_tuned | 20 | 69 | 69 | 0 | 0 | 69 | 0 | 3 | 0 | 0 | 3.0000 | 7.8100 | 8.0000 | 7200.9000 | 10953.9360 | 11215.6000 |

### Observations & Flags

- **Tag `0_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `100_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `50_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `sanity_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
