# referee/ — the external timing referee (board 2)

An Arduino App for a **second UNO Q** that times the DUT's 10 ms loop from outside, so Config C is not judged only by the DUT's own clock.

- **Wiring:** DUT D2 → referee D2, grounds joined. The DUT raises D2 for 500 µs at every tick.
- **MCU (`sketch/`):** an interrupt on each rising edge of D2 stores the time since the previous edge, read from the referee's own DWT cycle counter (160 MHz), for up to 10,000 edges. RPCs for the Linux side: `start_capture`, `stop_capture`, `get_count`, `get_delta_at`, `get_deltas_chunk`.
- **Linux side (`python/main.py`):** polls the command file `/tmp/referee_cmd` (`START <n>`, `STOP <csv path>`) and reports its state in `/tmp/referee_status` (`READY`, `RECORDING`, `STOPPED <n> <file>`). The Config C harness writes these files through `docker exec`.
- **Output:** `config_c_referee_<tag>.csv` in the run's raw folder (row 0 = the gap before the first pulse; excluded from analysis).
- Deployed as the app `referee_bench`. The first referee (Phase 4.5) used `k_cycle_get_32()`; this DWT version is used from Phase 5 on (the `dwtref` runs).
