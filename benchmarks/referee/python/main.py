import time
import os
import csv
from arduino.app_utils import App, Bridge

CMD_FILE = "/tmp/referee_cmd"
STATUS_FILE = "/tmp/referee_status"

def check_commands():
    if not os.path.exists(CMD_FILE):
        return

    try:
        with open(CMD_FILE, "r") as f:
            cmd_line = f.read().strip()
        os.remove(CMD_FILE)
    except Exception as e:
        print(f"[Referee] Error reading command: {e}")
        return

    parts = cmd_line.split()
    if not parts:
        return

    cmd = parts[0].upper()
    if cmd == "START":
        count = int(parts[1]) if len(parts) > 1 else 10000
        print(f"[Referee] Starting capture for {count} pulses...")
        ret = Bridge.call("start_capture", count)
        with open(STATUS_FILE, "w") as f:
            f.write(f"RECORDING 0 {count}\n")
        print(f"[Referee] Capture started (Bridge returned {ret})")

    elif cmd == "STOP":
        out_csv = parts[1] if len(parts) > 1 else "/home/arduino/referee_results.csv"
        print(f"[Referee] Stopping capture, outputting to {out_csv}...")
        total = Bridge.call("stop_capture", 0)
        print(f"[Referee] Total pulses recorded: {total}")

        # Fetch recorded deltas using chunked API (50 per call)
        deltas = []
        offset = 0
        while offset < total:
            chunk_str = Bridge.call("get_deltas_chunk", offset)
            if chunk_str:
                items = [int(x) for x in chunk_str.split(",") if x.strip()]
                deltas.extend(items)
                offset += len(items)
            else:
                # Fallback to individual fetch if needed
                d = Bridge.call("get_delta_at", offset)
                deltas.append(d)
                offset += 1

        with open(out_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["cycle", "interval_us", "interval_ms", "jitter_ms", "is_miss"])
            for i, delta_us in enumerate(deltas):
                delta_ms = delta_us / 1000.0
                jitter_ms = delta_ms - 10.0
                is_miss = 1 if (abs(jitter_ms) > 1.0) else 0
                writer.writerow([i, delta_us, f"{delta_ms:.4f}", f"{jitter_ms:.4f}", is_miss])

        with open(STATUS_FILE, "w") as f:
            f.write(f"STOPPED {len(deltas)} {out_csv}\n")
        print(f"[Referee] Saved {len(deltas)} records to {out_csv}")

    elif cmd == "STATUS":
        cur = Bridge.call("get_count", 0)
        with open(STATUS_FILE, "w") as f:
            f.write(f"COUNT {cur}\n")
        print(f"[Referee] Current count: {cur}")

def loop():
    check_commands()
    time.sleep(0.05)

print("[Referee] Service initialized. Listening on /tmp/referee_cmd...")
with open(STATUS_FILE, "w") as f:
    f.write("READY 0\n")

App.run(user_loop=loop)
