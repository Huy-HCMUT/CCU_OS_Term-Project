# Config C IPC Telemetry Summary

| tag | cycles | sent | sent_ok | send_errors | skipped_slots | rx_count | first_cycle_with_ipc | distinct_applied | unobserved_ok | setpoint_mismatch | age_p50_cyc | age_p99_cyc | age_max_cyc | rtt_p50_us | rtt_p99_us | rtt_max_us |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 0_ipc | 10000 | 1238 | 1238 | 0 | 0 | 1238 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 8158.4000 | 9219.9930 | 15479.5000 |
| 100_ipc | 1750 | 1258 | 1258 | 0 | 7 | -1 | 0 | 206 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 7978.5500 | 9817.9690 | 12282.9000 |
| 50_ipc | 10000 | 1262 | 1262 | 0 | 0 | 1262 | 0 | 1174 | 0 | 0 | 4.0000 | 8.0000 | 8.0000 | 7809.2000 | 9458.7830 | 13745.4000 |
| sanity_ipc | 20 | 69 | 69 | 0 | 0 | 69 | 0 | 3 | 0 | 0 | 3.0000 | 7.0000 | 7.0000 | 7567.5000 | 11634.0880 | 16948.9000 |

### Observations & Flags

- **Tag `0_ipc`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `100_ipc`:** Flagged: rx_count=unknown
- **Tag `50_ipc`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
- **Tag `sanity_ipc`:** Clean execution (0 errors, 0 mismatches, IPC active from cycle 0).
