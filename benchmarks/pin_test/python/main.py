"""Linux side of the Config C baseline DUT app (no IPC).

Intentionally idle: it only keeps the App container running. The harness
(benchmarks/run_config_c_hardware_test.py) talks to the MCU itself through
`docker exec <container> python3 -c "... Bridge.call(...)"`, and nothing
here sends messages to the MCU during a run.
"""

import time

from arduino.app_utils import App


def loop():
    time.sleep(1.0)


print("[pin_test] Baseline DUT app running (idle Linux side, no IPC).")
App.run(user_loop=loop)
