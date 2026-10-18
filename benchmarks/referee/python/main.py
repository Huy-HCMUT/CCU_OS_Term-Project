import time
import os
import csv
from arduino.app_utils import App, Bridge

CMD_FILE = "/tmp/referee_cmd"
STATUS_FILE = "/tmp/referee_status"

def safe_bridge_call(method, *args, retries=5, delay=0.5):
    last_err = None
    for attempt in range(retries):
        try:
            return Bridge.call(method, *args)
        except Exception as e:
            last_err = e
            print(f"[Referee] Bridge.call('{method}') attempt {attempt+1}/{retries} failed: {e}")
            time.sleep(delay)
    raise last_err

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
        try:
            ret = safe_bridge_call("start_capture", count)
            with open(STATUS_FILE, "w") as f:
                f.write(f"RECORDING 0 {count}\n")
            print(f"[Referee] Capture started (Bridge returned {ret})")
        except Exception as e:
            print(f"[Referee] Failed to start capture: {e}")
            with open(STATUS_FILE, "w") as f:
                f.write(f"ERROR {e}\n")

    elif cmd == "STOP":
        out_csv = parts[1] if len(parts) > 1 else "/home/arduino/referee_results.csv"
        print(f"[Referee] Stopping capture, outputting to {out_csv}...")
        try:
            total = safe_bridge_call("stop_capture", 0)
        except Exception as e:
            print(f"[Referee] Error stopping capture: {e}")
            total = 0

        print(f"[Referee] Total pulses recorded: {total}")

        # Fetch recorded deltas using chunked API (50 per call)
        deltas = []
        offset = 0
        while offset < total:
            try:
                chunk_str = safe_bridge_call("get_deltas_chunk", offset, retries=3, delay=0.2)
                if chunk_str:
                    items = [int(x) for x in chunk_str.split(",") if x.strip()]
                    deltas.extend(items)
                    offset += len(items)
                else:
                    d = safe_bridge_call("get_delta_at", offset, retries=3, delay=0.2)
                    deltas.append(d)
                    offset += 1
            except Exception as e:
                print(f"[Referee] Chunk fetch error at offset {offset}: {e}")
                break

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
        try:
            cur = safe_bridge_call("get_count", 0, retries=2, delay=0.2)
            with open(STATUS_FILE, "w") as f:
                f.write(f"COUNT {cur}\n")
            print(f"[Referee] Current count: {cur}")
        except Exception as e:
            print(f"[Referee] Status error: {e}")

def loop():
    try:
        check_commands()
    except Exception as e:
        print(f"[Referee] Exception in loop: {e}")
    time.sleep(0.05)

print("[Referee] Service initialized. Listening on /tmp/referee_cmd...")
with open(STATUS_FILE, "w") as f:
    f.write("READY 0\n")

App.run(user_loop=loop)
