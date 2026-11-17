import time
import os
import csv
from arduino.app_utils import App, Bridge

CMD_FILE = "/tmp/drive_cmd"
STATUS_FILE = "/tmp/drive_status"


def safe_bridge_call(method, *args, retries=5, delay=0.5):
    last_err = None
    for attempt in range(retries):
        try:
            return Bridge.call(method, *args)
        except Exception as e:
            last_err = e
            print(f"[Drive] Bridge.call('{method}') attempt {attempt+1}/{retries} failed: {e}")
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
        print(f"[Drive] Error reading command: {e}")
        return

    parts = cmd_line.split()
    if not parts:
        return

    cmd = parts[0].upper()
    if cmd == "START":
        print("[Drive] Starting capture...")
        try:
            ret = safe_bridge_call("start_capture", 0)
            with open(STATUS_FILE, "w") as f:
                f.write("RECORDING 0\n")
            print(f"[Drive] Capture started (Bridge returned {ret})")
        except Exception as e:
            print(f"[Drive] Failed to start capture: {e}")
            with open(STATUS_FILE, "w") as f:
                f.write(f"ERROR {e}\n")

    elif cmd == "STOP":
        out_csv = parts[1] if len(parts) > 1 else "/home/arduino/drive_results.csv"
        print(f"[Drive] Stopping capture, writing to {out_csv}...")
        try:
            total = int(safe_bridge_call("stop_capture", 0))
            info_str = str(safe_bridge_call("get_info", 0, retries=3, delay=0.2)).strip()
            info_vals = [int(x.strip()) for x in info_str.split(",")]
            if len(info_vals) != 9:
                raise ValueError(f"Expected 9 info fields, got {len(info_vals)}: {info_str!r}")
            ticks, tick_min, tick_max, periods, pout, level_errors, initial_high, ev_n, ev_dropped = info_vals
        except Exception as e:
            print(f"[Drive] Error stopping capture or fetching info: {e}")
            with open(STATUS_FILE, "w") as f:
                f.write(f"ERROR {e}\n")
            return

        print(f"[Drive] Events recorded: {total} (ev_n={ev_n}, dropped={ev_dropped})")

        vals = []
        total_values = total * 6
        offset = 0
        while offset < total_values:
            try:
                chunk_str = safe_bridge_call("get_events_chunk", offset, retries=3, delay=0.2)
                if not chunk_str:
                    break
                items = [int(x) for x in str(chunk_str).split(",") if x.strip()]
                if not items:
                    break
                vals.extend(items)
                offset += len(items)
            except Exception as e:
                print(f"[Drive] Chunk fetch error at offset {offset}: {e}")
                with open(STATUS_FILE, "w") as f:
                    f.write(f"ERROR {e}\n")
                return

        n_rows = len(vals) // 6
        with open(out_csv, "w", newline="") as f:
            f.write(
                f"# ticks={ticks} tick_min_cyc={tick_min} tick_max_cyc={tick_max} "
                f"periods={periods} period_outliers={pout} level_errors={level_errors} "
                f"initial_high_cyc={initial_high} events={ev_n} events_dropped={ev_dropped}\n"
            )
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["event", "tick_idx", "tick_cyc", "rise_cyc", "fall_cyc", "high_cyc", "period_cyc"])
            for i in range(n_rows):
                writer.writerow([i] + vals[6 * i : 6 * (i + 1)])

        with open(STATUS_FILE, "w") as f:
            f.write(f"STOPPED {n_rows} {out_csv}\n")
        print(f"[Drive] Saved {n_rows} events to {out_csv}")

    elif cmd == "STATUS":
        try:
            info_str = safe_bridge_call("get_info", 0, retries=2, delay=0.2)
            with open(STATUS_FILE, "w") as f:
                f.write(f"INFO {info_str}\n")
            print(f"[Drive] Status: {info_str}")
        except Exception as e:
            print(f"[Drive] Status error: {e}")


def loop():
    try:
        check_commands()
    except Exception as e:
        print(f"[Drive] Exception in loop: {e}")
    time.sleep(0.05)


print("[Drive] Service initialized. Listening on /tmp/drive_cmd...")
with open(STATUS_FILE, "w") as f:
    f.write("READY 0\n")

App.run(user_loop=loop)

