# Config C Baseline Tuned (`config_c_base_tuned`)

Config C baseline (no IPC) DUT app for Phase 5b.
Its sketch differs from `benchmarks/config_c_sender_sketch.ino` only by setting the Arduino `loop()` thread priority to `4` (above RouterBridge `bridge` thread priority `5`) at the end of `setup()`.
See `DECISIONS.md` (D7) for design rationale and priority details.

