# diagnostics/ — one-off hardware checks

Checks that answer a design question before or beside the main runs. Each runner can also recompute its summary from saved raw data without hardware.

| Check | Files | Question | Raw data → summary |
| :--- | :--- | :--- | :--- |
| Clock check (2026-10-19) | `clock_check/` (sketch), `run_clock_check.py` | Why does the MCU's Zephyr clock (`k_cycle_get_32()`, `micros()`) drift against its DWT cycle counter? (It loses cycles, mostly while asleep.) | `results/raw/clock_diagnostics_2026-10-19.csv` → `results/clock_diagnostics_summary.md`; recompute with `--from-csv` |
| PWM loopback (2026-11-17) | `pwm_loopback/` (app), `run_pwm_loopback.py` | Can a 500 Hz PWM signal carry the speed command from the DUT to the drive board, and when does a new duty take effect? (Jumper D3 → D8 on one board.) | `results/raw/pwm_loopback_2026-11-17/` → `results/diagnostics/pwm_loopback_summary.md`; recompute with `--from-raw` |

Both runners drive a real board when not given saved data; see each script's header for the exact usage.
