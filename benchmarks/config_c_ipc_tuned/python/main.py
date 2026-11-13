import csv
import os
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analytics import load_frames, synthetic_frames, setpoint_for_frame, PERIOD_NS
from arduino.app_utils import App, Bridge

CMD_FILE = "/tmp/sender_cmd"
STATUS_FILE = "/tmp/sender_status"
FRAMES_PATH = Path(__file__).resolve().parent / "cwru_test_frames.bin"

try:
    FRAMES = load_frames(FRAMES_PATH)
    FRAMES_SOURCE = "cwru"
    print(f"[Sender] Loaded {len(FRAMES)} real CWRU frames from {FRAMES_PATH}")
except Exception as e:
    FRAMES = synthetic_frames()
    FRAMES_SOURCE = "synthetic"
    print(f"[Sender] Warning: {e}. Falling back to 40 synthetic frames")

sender_thread = None
stop_event = None
sender_rows = []


def sender_run(stop_evt, rows):
    seq = 0
    frame_idx = 0
    next_ns = time.monotonic_ns()
    while not stop_evt.is_set():
        f = frame_idx % len(FRAMES)
        sp = setpoint_for_frame(FRAMES[f])
        seq += 1
        t0 = time.monotonic_ns()
        try:
            ret = Bridge.call("set_setpoint", seq, sp)
            status = "ok" if int(ret) == seq else f"bad_return:{ret}"
        except Exception as e:
            status = f"error:{type(e).__name__}"
        t1 = time.monotonic_ns()
        release = next_ns
        frame_idx += 1
        next_ns += PERIOD_NS
        now = time.monotonic_ns()
        skipped = 0
        while next_ns <= now:
            next_ns += PERIOD_NS
            skipped += 1
        rows.append([seq, f, sp, release, t0, t1, f"{(t1 - t0) / 1000.0:.1f}", skipped, status])
        stop_evt.wait((next_ns - now) / 1e9)


def check_commands():
    global sender_thread, stop_event, sender_rows

    if not os.path.exists(CMD_FILE):
        return

    try:
        with open(CMD_FILE, "r") as f:
            cmd_line = f.read().strip()
        os.remove(CMD_FILE)
    except Exception as e:
        print(f"[Sender] Error reading command: {e}")
        return

    parts = cmd_line.split()
    if not parts:
        return

    cmd = parts[0].upper()
    if cmd == "START":
        if sender_thread is not None and sender_thread.is_alive():
            with open(STATUS_FILE, "w") as f:
                f.write("ERROR already_running\n")
            print("[Sender] Rejected START: sender thread already running")
            return

        stop_event = threading.Event()
        sender_rows = []
        sender_thread = threading.Thread(
            target=sender_run, args=(stop_event, sender_rows), daemon=True
        )
        sender_thread.start()
        with open(STATUS_FILE, "w") as f:
            f.write("SENDING 0\n")
        print("[Sender] Started sender thread")

    elif cmd == "STOP":
        out_csv = parts[1] if len(parts) > 1 else "/home/arduino/sender_results.csv"
        print(f"[Sender] Stopping sender, outputting to {out_csv}...")
        if stop_event is not None:
            stop_event.set()
        if sender_thread is not None:
            sender_thread.join(timeout=2.0)

        try:
            with open(out_csv, "w", newline="") as f:
                f.write(f"# frames_source={FRAMES_SOURCE} period_ns=85333333\n")
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "seq",
                        "frame_idx",
                        "setpoint_pct",
                        "release_ns",
                        "t_send_ns",
                        "t_return_ns",
                        "rtt_us",
                        "skipped_after",
                        "status",
                    ]
                )
                for row in sender_rows:
                    writer.writerow(row)
        except Exception as e:
            print(f"[Sender] Error writing output CSV: {e}")

        with open(STATUS_FILE, "w") as f:
            f.write(f"STOPPED {len(sender_rows)} {out_csv}\n")
        print(f"[Sender] Saved {len(sender_rows)} records to {out_csv}")


def loop():
    try:
        check_commands()
    except Exception as e:
        print(f"[Sender] Exception in loop: {e}")
    time.sleep(0.05)


print("[Sender] Service initialized. Listening on /tmp/sender_cmd...")
with open(STATUS_FILE, "w") as f:
    f.write("READY 0\n")

App.run(user_loop=loop)

