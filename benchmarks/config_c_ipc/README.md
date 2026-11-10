# Config C IPC Arduino App (Phase 5)

This directory contains the DUT Arduino App for Phase 5 benchmarking on the Arduino UNO Q.
It implements Config C with a Linux-to-MCU setpoint IPC link over Arduino_RouterBridge.

The Linux Python service reads replayed CWRU vibration frames, computes FFT peak frequency,
and sends updated setpoint commands to the MCU core every 85.33 ms.

Before deploying this app with Arduino App Lab, `cwru_test_frames.bin` must be copied from
`data/processed/` into `benchmarks/config_c_ipc/python/` (binary frames are gitignored by `*.bin`).

The MCU sketch exposes the following RPC methods:
- `set_setpoint(int seq, int sp)`: Updates latest setpoint word `(seq << 8) | sp` atomically.
- `reset_ipc(int dummy)`: Resets IPC sequence, setpoint word, and counters to default.
- `get_rx_count(int dummy)`: Returns the total count of received IPC setpoints.
- `get_thread_prios(int dummy)`: Returns thread priority string `main=<prio>,bridge=<prio>`.
- `get_seq_chunk(int start_idx)`: Retrieves comma-separated chunk of applied setpoint words.
- Baseline methods: `start_zephyr_pulses`, `check_dwt_status`, `get_dwt_chunk`.

