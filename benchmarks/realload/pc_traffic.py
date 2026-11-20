#!/usr/bin/env python3
"""PC-side TCP traffic generator for Phase 6a realistic load tiers (R-net and R-deploy)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import socket
import sys
import threading
import time

DEFAULT_PORTS = {
    "ingest": 5555,
    "bulk": 5557,
}
INGEST_CHUNK_BYTES = 480  # 120 float32 samples @ 12 kHz = 48,000 B/s every 10 ms
INGEST_PERIOD_S = 0.010
BULK_CHUNK = b"\x00" * (64 * 1024)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _atomic_write_json(out_path: Path, payload: dict) -> None:
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, out_path)


def _default_data_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "processed" / "cwru_test_frames.bin"


def _build_payload(
    *,
    mode: str,
    host: str,
    port: int,
    start_iso: str,
    t0: float,
    bytes_sent: int,
    reconnects: int,
    late_skips: int,
) -> dict:
    elapsed_s = max(0.0, time.perf_counter() - t0)
    avg_rate = (bytes_sent / elapsed_s) if elapsed_s > 0.0 else 0.0
    return {
        "mode": mode,
        "host": host,
        "port": port,
        "start_iso": start_iso,
        "last_iso": _now_iso(),
        "elapsed_s": round(elapsed_s, 3),
        "bytes_sent": int(bytes_sent),
        "avg_rate_Bps": round(avg_rate, 1),
        "reconnects": int(reconnects),
        "late_skips": int(late_skips),
    }


def _next_ingest_chunk(raw_data: bytes, offset: int) -> tuple[bytes, int]:
    n = len(raw_data)
    end = offset + INGEST_CHUNK_BYTES
    if end <= n:
        return raw_data[offset:end], (end % n)
    first = raw_data[offset:]
    rem = INGEST_CHUNK_BYTES - len(first)
    # Repeat if raw_data is shorter than one chunk; standard CWRU file is 409,600 B.
    second = (raw_data * ((rem // n) + 1))[:rem]
    return first + second, rem % n


def _connect_tcp(host: str, port: int, timeout_s: float, nodelay: bool) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    if nodelay:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    try:
        sock.connect((host, port))
        return sock
    except Exception:
        sock.close()
        raise


def run_traffic(
    *,
    mode: str,
    host: str,
    port: int,
    duration: float,
    out_path: Path,
    data_path: Path,
) -> int:
    if out_path.exists():
        print(f"ERROR: refusing to overwrite existing --out file: {out_path}", file=sys.stderr)
        return 1

    raw_data = b""
    if mode == "ingest":
        if not data_path.exists():
            print(f"ERROR: data file not found: {data_path}", file=sys.stderr)
            return 1
        raw_data = data_path.read_bytes()
        if not raw_data:
            print(f"ERROR: data file is empty: {data_path}", file=sys.stderr)
            return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)

    stop_event = threading.Event()

    def _on_signal(_signum, _frame) -> None:
        stop_event.set()

    prev_sigint = signal.getsignal(signal.SIGINT)
    prev_sigterm = signal.getsignal(signal.SIGTERM)
    try:
        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)
    except ValueError:
        pass  # Non-main thread (e.g. unit tests)

    start_iso = _now_iso()
    t0 = time.perf_counter()
    deadline = t0 + duration
    last_write = t0
    last_print = t0

    bytes_sent = 0
    reconnects = 0
    late_skips = 0
    slot_k = 0
    data_offset = 0
    sock: socket.socket | None = None

    def flush_stats(force_write: bool = False, force_print: bool = False) -> None:
        nonlocal last_write, last_print
        now = time.perf_counter()
        need_write = force_write or (now - last_write >= 5.0)
        need_print = force_print or (now - last_print >= 30.0)
        if not need_write and not need_print:
            return
        payload = _build_payload(
            mode=mode,
            host=host,
            port=port,
            start_iso=start_iso,
            t0=t0,
            bytes_sent=bytes_sent,
            reconnects=reconnects,
            late_skips=late_skips,
        )
        if need_write:
            _atomic_write_json(out_path, payload)
            last_write = now
        if need_print:
            print(json.dumps(payload), flush=True)
            last_print = now

    try:
        while not stop_event.is_set() and time.perf_counter() < deadline:
            flush_stats()
            if sock is None:
                rem = deadline - time.perf_counter()
                if rem <= 0:
                    break
                try:
                    sock = _connect_tcp(
                        host,
                        port,
                        timeout_s=min(2.0, max(0.2, rem)),
                        nodelay=(mode == "ingest"),
                    )
                except OSError:
                    wait_s = min(1.0, max(0.0, deadline - time.perf_counter()))
                    if wait_s <= 0:
                        break
                    stop_event.wait(wait_s)
                    if not stop_event.is_set() and time.perf_counter() < deadline:
                        reconnects += 1
                    continue

            try:
                if mode == "bulk":
                    sock.sendall(BULK_CHUNK)
                    bytes_sent += len(BULK_CHUNK)
                else:
                    target = t0 + slot_k * INGEST_PERIOD_S
                    if target >= deadline:
                        break
                    now = time.perf_counter()
                    if now - target > 10 * INGEST_PERIOD_S:
                        slot_k = int((now - t0) // INGEST_PERIOD_S)
                        late_skips += 1
                        target = t0 + slot_k * INGEST_PERIOD_S
                        if target >= deadline:
                            break
                    while not stop_event.is_set():
                        rem_wait = target - time.perf_counter()
                        if rem_wait <= 0.0:
                            break
                        if rem_wait > 0.002:
                            time.sleep(rem_wait - 0.002)
                    if stop_event.is_set() or time.perf_counter() >= deadline:
                        break
                    chunk, next_offset = _next_ingest_chunk(raw_data, data_offset)
                    sock.sendall(chunk)
                    bytes_sent += len(chunk)
                    data_offset = next_offset
                    slot_k += 1
            except OSError:
                try:
                    sock.close()
                except OSError:
                    pass
                sock = None
                wait_s = min(1.0, max(0.0, deadline - time.perf_counter()))
                if wait_s <= 0:
                    break
                stop_event.wait(wait_s)
                if not stop_event.is_set() and time.perf_counter() < deadline:
                    reconnects += 1
    except KeyboardInterrupt:
        pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        flush_stats(force_write=True)
        try:
            signal.signal(signal.SIGINT, prev_sigint)
            signal.signal(signal.SIGTERM, prev_sigterm)
        except (ValueError, TypeError):
            pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ingest", "bulk"), help="Traffic mode")
    parser.add_argument("--host", required=True, help="Target DUT IP/hostname")
    parser.add_argument("--duration", type=float, required=True, help="Run duration in seconds")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON summary path")
    parser.add_argument("--port", type=int, default=None, help="Target TCP port")
    parser.add_argument(
        "--data",
        type=Path,
        default=_default_data_path(),
        help="Input CWRU float32 binary file (for ingest)",
    )
    args = parser.parse_args(argv)
    port = args.port if args.port is not None else DEFAULT_PORTS[args.mode]
    return run_traffic(
        mode=args.mode,
        host=args.host,
        port=port,
        duration=args.duration,
        out_path=args.out,
        data_path=args.data,
    )


if __name__ == "__main__":
    raise SystemExit(main())

