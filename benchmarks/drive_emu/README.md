# drive_emu/ — emulated motor drive (board 3, Phase 6b)

An Arduino App for a **third UNO Q** that plays the motor drive in the full chain: the DUT's MCU sends the speed command as a 500 Hz PWM signal, and this board records when each new command arrives.

- **Wiring:** DUT D3 (PWM speed command) → board 3 D8; DUT D2 (tick) → board 3 D2; grounds joined.
- **MCU (`sketch/`):** interrupts on D2 (tick) and on both edges of D8 (PWM), timestamped with the DWT cycle counter (160 MHz). A **change event** is a PWM period whose high time differs from the previous one by more than 20 µs (1 % of the 2 ms period). Duty = 0.8 × setpoint, so the drive decodes `setpoint = 125 × high / period`. RPCs: `start_capture`, `stop_capture`, `get_info`, `get_events_chunk`.
- **Linux side (`python/main.py`):** command file `/tmp/drive_cmd` (`START`, `STOP <csv path>`), status file `/tmp/drive_status` (`READY`, `RECORDING`, `STOPPED <n> <file>`), driven by the Config C harness (`act-*` modes).
- **Output:** `config_c_drive_<tag>.csv` in the run's raw folder; analysed by `benchmarks/analysis/analyze_drive.py`.
- Deployed at `/tmp/drive_emu` on board 3. While the wires are connected, only this app may run on board 3.
