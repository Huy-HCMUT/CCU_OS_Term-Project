# PWM loopback diagnostic (Phase 6b test 1)

- Raw data: `results/raw/pwm_loopback_2026-11-17`
- Date: 2026-11-17T15:26:39; board role: board3 (pwm loopback, D3 -> D8 jumper); core: arduino:zephyr 1.0.0
- Setup: one jumper D3 (PWM out, TIM3_CH3, 500 Hz) -> D8 (input, EXTI4) on the same board; DWT timestamps at 160 MHz.
- Pass criteria (fixed before the run): mean period 2000 us +-0.1 %; duty +-0.5 points; 0 missed edges; >= 99 % of expected periods; first new period starts <= 2000 us after analogWrite(); analogWrite() <= 100 us.

## Steady captures

| Target duty | Periods (expected) | Mean period (us) | Period min-max (us) | Duty (%) | High min-max (us) | Level repeats | Period outliers | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 80.0 % | 50020 (50000) | 2000.000 | 1999.619-2000.300 | 80.009 | 1599.975-1600.375 | 0 | 0 | PASS |
| 48.0 % | 50020 (50000) | 2000.000 | 1999.612-2000.388 | 47.999 | 959.631-960.381 | 0 | 0 | PASS |

## Switch test

- Switches: 200 (alternating 80 % <-> 48 %, random phase), detected: 200, timeouts: 0
- First period with the new duty starts after the call (us): min 30.2, median 895.3, max 2001.7 (negative = the period that was already running changed)
- New duty visible (its falling edge) after the call (us): min 1001.4, median 2247.4, max 3596.9
- analogWrite() duration (us): min 7.20, median 7.29, max 69.01
- Detected periods whose duty is off the target by > 0.5 points (transitional periods): 0
- Result: **FAIL**

## Overall

**FAIL**

- switch test: first new period started up to 2001.7 us after the call (> 2000 us)
