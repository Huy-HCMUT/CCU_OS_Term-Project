# Config C M3 Demo (`config_c_demo`)

Interactive demonstration app for the M3 presentation showing the Linux-to-MCU setpoint IPC link.
**Not for measurements** (uses LED3 output and continuous pulsing; the harness never selects this container).

## How to run
1. Start `config_c_demo` in Arduino App Lab on the UNO Q.
2. Observe the App Lab Python console logs and the on-board `LED3` RGB LED.

## What to expect
- Every ~2.1 s (25 frames at 85.33 ms cadence), when entering a new vibration block (`Normal`, `Inner race fault`, `Ball fault`, `Outer race fault`), the Linux side logs `[Demo] frame <idx> (<CLASS>) -> setpoint <sp> %`.
- `LED3` is **green** during the `Normal`, `Inner race fault`, and `Ball fault` blocks (`setpoint = 100 %`), and turns **red** during parts of the `Outer race fault` block where the analytics rule drops the speed setpoint to `60 %` (15 of 25 frames).

