# Config C IPC Tuned + Drive Output (`config_c_act_tuned`)

Phase 6b DUT app. Identical to `benchmarks/config_c_ipc_tuned/` (loop thread priority 4, above the RouterBridge `bridge` thread 5) plus one addition: the applied speed setpoint is sent to the drive board (board 3, `benchmarks/drive_emu/`) as a 500 Hz hardware-PWM signal on D3, duty = 0.8 × setpoint.
- The PWM is written in the 10 ms tick **after the D2 pulse**, and only when the applied setpoint changes; each write is logged (cycle, DWT time, call duration, setpoint) and read back with `get_act_count` / `get_act_chunk`.
- `reset_ipc` sets the PWM back to 100 % (80 % duty) before a run; nothing is written at the start of the timed loop.
- Wiring: DUT D3 → board 3 D8, DUT D2 → referee D2 and board 3 D2, common GND.
See `DECISIONS.md` (D11, D12) for the design rationale.
