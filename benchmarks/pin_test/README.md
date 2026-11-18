# pin_test/ — Config C stock baseline DUT app (no IPC)

The DUT app for the **Config C baseline**: the MCU runs the 10 ms loop (DWT timestamps + a 500 µs pulse on D2 each tick) while Linux sends nothing.

- **MCU (`sketch/`):** built from `benchmarks/config_c_sender_sketch.ino`, stock priorities (loop thread below RouterBridge's `bridge` thread).
- **Linux side (`python/main.py`):** intentionally idle; it only keeps the app container running. The harness talks to the MCU itself (`docker exec … Bridge.call(...)`).
- **Used by:** harness modes `sanity`, `0`, `50`, `100` (Phase 4.5) and `b2-*` (baseline re-run with the DWT referee, Phase 5 on: raw folders `baseline_dwtref*`), and the clock diagnostics.
- The tuned baseline (loop above the bridge thread) is `benchmarks/config_c_base_tuned/`.
