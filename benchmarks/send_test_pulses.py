import time
from arduino.app_utils import Bridge

print("[PulseTest] Initializing test pulses...")
for i in range(10):
    Bridge.call("set_pin_by_name", "D2", True)
    time.sleep(0.002)
    Bridge.call("set_pin_by_name", "D2", False)
    time.sleep(0.010)
    print(f"  Pulse {i+1} sent")
print("[PulseTest] Done sending 10 pulses!")
