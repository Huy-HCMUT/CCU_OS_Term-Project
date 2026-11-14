# Config C IPC Telemetry Summary

| tag | cycles | sent | sent_ok | send_errors | skipped_slots | rx_count | first_cycle_with_ipc | distinct_applied | unobserved_ok | setpoint_mismatch | age_p50_cyc | age_p99_cyc | age_max_cyc | rtt_p50_us | rtt_p99_us | rtt_max_us |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc_tuned | 10000 | 1256 | 1256 | 0 | 0 | 1256 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 8619.6000 | 12822.1050 | 16131.1000 |
| 100_ipc_tuned | 10000 | 1279 | 1279 | 0 | 0 | 1279 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 8492.6000 | 12914.5960 | 20145.1000 |
| 50_ipc_tuned | 10000 | 1281 | 1281 | 0 | 0 | 1281 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 8382.7000 | 12728.0200 | 15693.9000 |
| sanity_ipc_tuned | 20 | 83 | 83 | 0 | 0 | 83 | 0 | 3 | 0 | 0 | 3.0000 | 7.8100 | 8.0000 | 7518.3000 | 9011.1820 | 11836.0000 |

### Observations & Flags

- **Tag `0_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `100_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `50_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `sanity_ipc_tuned`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
