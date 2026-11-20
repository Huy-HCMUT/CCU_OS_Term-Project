"""PWM loopback diagnostic: idle Linux side.

All work happens on the MCU; the PC runner (benchmarks/diagnostics/run_pwm_loopback.py)
calls the sketch's RPCs through `docker exec` into this app's container.
"""
import time

from arduino.app_utils import App


def loop():
    time.sleep(1.0)


print("[pwm_loopback] ready (Linux side idle; tests are driven from the PC)")
App.run(user_loop=loop)
