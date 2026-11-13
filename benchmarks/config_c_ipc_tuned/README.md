# Config C IPC Tuned (`config_c_ipc_tuned`)

Config C Linux-to-MCU setpoint IPC DUT app for Phase 5b.
Its sketch differs from `benchmarks/config_c_ipc/sketch/sketch.ino` only by setting the Arduino `loop()` thread priority to `4` (above RouterBridge `bridge` thread priority `5`) and updating `g_main_prio` at the end of `setup()`.
See `DECISIONS.md` (D7) for design rationale and priority details.

