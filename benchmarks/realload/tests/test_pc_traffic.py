from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
import threading
import time

import pytest

REALLOAD_DIR = Path(__file__).resolve().parents[1]
if str(REALLOAD_DIR) not in sys.path:
    sys.path.insert(0, str(REALLOAD_DIR))

import pc_traffic  # noqa: E402


def _start_sink_server(close_after_s: float | None = None, restart_after_s: float | None = None):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    port = srv.getsockname()[1]

    state = {"bytes_rx": 0, "stop": False, "conns": 0}
    lock = threading.Lock()

    def serve():
        srv.settimeout(0.1)
        rebind_pending = False
        rebind_at = 0.0
        cur_srv = srv
        while not state["stop"]:
            if rebind_pending and time.monotonic() >= rebind_at:
                cur_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cur_srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                cur_srv.bind(("127.0.0.1", port))
                cur_srv.listen(4)
                cur_srv.settimeout(0.1)
                rebind_pending = False
            if cur_srv is None:
                time.sleep(0.05)
                continue
            try:
                conn, _ = cur_srv.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            with lock:
                state["conns"] += 1
                conn_idx = state["conns"]
            conn_start = time.monotonic()
            conn.settimeout(0.1)
            try:
                while not state["stop"]:
                    if close_after_s is not None and conn_idx == 1 and (time.monotonic() - conn_start) >= close_after_s:
                        break
                    try:
                        chunk = conn.recv(65536)
                    except TimeoutError:
                        continue
                    except OSError:
                        break
                    if not chunk:
                        break
                    with lock:
                        state["bytes_rx"] += len(chunk)
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
                if close_after_s is not None and conn_idx == 1 and restart_after_s is not None:
                    cur_srv.close()
                    cur_srv = None
                    rebind_at = time.monotonic() + restart_after_s
                    rebind_pending = True

        if cur_srv is not None:
            try:
                cur_srv.close()
            except OSError:
                pass

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    def stop():
        state["stop"] = True
        t.join(timeout=2.0)

    return port, state, stop


def test_refuses_existing_out(tmp_path):
    out = tmp_path / "existing.json"
    out.write_text("{}", encoding="utf-8")
    rc = pc_traffic.main(["bulk", "--host", "127.0.0.1", "--duration", "0.5", "--out", str(out)])
    assert rc == 1


def test_ingest_rate_2s(tmp_path):
    data_bin = tmp_path / "frames.bin"
    data_bin.write_bytes(b"A" * 4096)
    out = tmp_path / "ingest.json"

    port, state, stop = _start_sink_server()
    try:
        rc = pc_traffic.main(
            [
                "ingest",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--duration",
                "2.0",
                "--out",
                str(out),
                "--data",
                str(data_bin),
            ]
        )
    finally:
        stop()

    assert rc == 0
    stats = json.loads(out.read_text(encoding="utf-8"))
    assert stats["mode"] == "ingest"
    assert 96000 * 0.95 <= stats["bytes_sent"] <= 96000 * 1.05
    assert state["bytes_rx"] == stats["bytes_sent"]
    for key in ("mode", "host", "port", "start_iso", "last_iso", "elapsed_s", "bytes_sent", "avg_rate_Bps", "reconnects", "late_skips"):
        assert key in stats


def test_bulk_rate_1s(tmp_path):
    out = tmp_path / "bulk.json"
    port, state, stop = _start_sink_server()
    try:
        rc = pc_traffic.main(
            [
                "bulk",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--duration",
                "1.0",
                "--out",
                str(out),
            ]
        )
    finally:
        stop()

    assert rc == 0
    stats = json.loads(out.read_text(encoding="utf-8"))
    assert stats["mode"] == "bulk"
    assert stats["bytes_sent"] > 1_000_000
    assert state["bytes_rx"] > 1_000_000


def test_reconnect_on_server_drop(tmp_path):
    out = tmp_path / "reconn.json"
    # Close client connection after 0.5 s and restart listener immediately, run for 2.5 s
    port, state, stop = _start_sink_server(close_after_s=0.5, restart_after_s=0.1)
    try:
        rc = pc_traffic.main(
            [
                "bulk",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--duration",
                "2.5",
                "--out",
                str(out),
            ]
        )
    finally:
        stop()

    assert rc == 0
    stats = json.loads(out.read_text(encoding="utf-8"))
    assert stats["reconnects"] >= 1
    assert state["conns"] >= 2

