#!/usr/bin/env python3
"""TCP ingest ONNX CNN analytics container node and calibration runner."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import socket
import threading
import time

import numpy as np

MODELS_DIR = Path("/opt/realload/models")
CALIBRATION_WIDTHS = (64, 128, 192, 256, 384)
WINDOW_SAMPLES = 1024
WINDOW_BYTES = WINDOW_SAMPLES * 4  # 4096 bytes per 1024 float32 LE samples


class WindowAssembler:
    """Assemble arbitrary incoming byte chunks into (1, 1, 1024) float32-LE windows."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[np.ndarray]:
        if data:
            self._buf.extend(data)
        windows: list[np.ndarray] = []
        while len(self._buf) >= WINDOW_BYTES:
            chunk = bytes(self._buf[:WINDOW_BYTES])
            del self._buf[:WINDOW_BYTES]
            arr = np.frombuffer(chunk, dtype="<f4").astype(np.float32, copy=True).reshape(1, 1, WINDOW_SAMPLES)
            windows.append(arr)
        return windows


class SummaryWindow:
    """Track inference durations (us) within a 1 s reporting window."""

    def __init__(self) -> None:
        self._times_us: list[float] = []

    def add(self, infer_us: float) -> None:
        self._times_us.append(float(infer_us))

    def summary(self, label: str, count: int, last_cls: int) -> dict[str, object]:
        n = len(self._times_us)
        p50 = float(np.median(self._times_us)) if n > 0 else 0.0
        self._times_us.clear()
        return {
            "label": label,
            "count": int(count),
            "last_cls": int(last_cls),
            "infer_p50_us": p50,
            "n": n,
        }


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _create_session(ort_mod, model_path: Path, threads: int):
    opts = ort_mod.SessionOptions()
    opts.intra_op_num_threads = threads
    opts.inter_op_num_threads = 1
    return ort_mod.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])


def _run_calibrate(ort_mod, n_runs: int, threads: int, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    x = rng.normal(0.0, 1.0, size=(1, 1, WINDOW_SAMPLES)).astype(np.float32)

    rows: list[str] = ["width,median_us,p90_us,n"]
    for w in CALIBRATION_WIDTHS:
        model_path = MODELS_DIR / f"cnn1d_w{w}.onnx"
        sess = _create_session(ort_mod, model_path, threads)
        in_name = sess.get_inputs()[0].name
        out_name = sess.get_outputs()[0].name

        for _ in range(5):
            sess.run([out_name], {in_name: x})

        times_us: list[float] = []
        for _ in range(n_runs):
            t0 = time.perf_counter_ns()
            sess.run([out_name], {in_name: x})
            times_us.append((time.perf_counter_ns() - t0) / 1000.0)

        med = float(np.median(times_us))
        p90 = float(np.percentile(times_us, 90))
        print(f"width={w} median_us={med:.1f} p90_us={p90:.1f}", flush=True)
        rows.append(f"{w},{med:.3f},{p90:.3f},{n_runs}")

    _atomic_write_text(out_dir / "calibration.csv", "\n".join(rows) + "\n")
    return 0


def _run_server(
    ort_mod,
    *,
    label: str,
    pc_ip: str,
    threads: int,
    width: int,
    out_dir: Path,
    port: int,
    pc_port: int,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / f"cnn1d_w{width}.onnx"
    sess = _create_session(ort_mod, model_path, threads)
    in_name = sess.get_inputs()[0].name
    out_name = sess.get_outputs()[0].name

    csv_path = out_dir / f"analytics_{label}.csv"
    status_path = out_dir / f"analytics_{label}_status.txt"
    need_header = not csv_path.exists() or csv_path.stat().st_size == 0

    stop_event = threading.Event()

    def _on_signal(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv_sock.bind(("0.0.0.0", port))
    srv_sock.listen(1)
    srv_sock.settimeout(0.5)

    assembler = WindowAssembler()
    summary_win = SummaryWindow()
    count = 0
    last_cls = 0
    _atomic_write_text(status_path, "count=0\n")

    csv_file = open(csv_path, "a", encoding="utf-8")
    if need_header:
        csv_file.write("t_mono_ns,count,cls,infer_us\n")
        csv_file.flush()

    last_fsync = time.monotonic()
    last_report = last_fsync

    def _maybe_report(force: bool = False) -> None:
        nonlocal last_report
        now = time.monotonic()
        if not force and (now - last_report) < 1.0:
            return
        last_report = now
        payload = json.dumps(summary_win.summary(label, count, last_cls)).encode("utf-8")
        try:
            udp_sock.sendto(payload, (pc_ip, pc_port))
        except OSError:
            pass
        _atomic_write_text(status_path, f"count={count}\n")

    try:
        while not stop_event.is_set():
            _maybe_report()
            try:
                conn, _addr = srv_sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            conn.settimeout(0.5)
            try:
                while not stop_event.is_set():
                    _maybe_report()
                    try:
                        data = conn.recv(65536)
                    except TimeoutError:
                        continue
                    except OSError:
                        break
                    if not data:
                        break
                    for win in assembler.feed(data):
                        t0 = time.perf_counter_ns()
                        outputs = sess.run([out_name], {in_name: win})
                        infer_us = (time.perf_counter_ns() - t0) / 1000.0
                        t_mono_ns = time.monotonic_ns()
                        count += 1
                        last_cls = int(np.argmax(outputs[0]))
                        csv_file.write(f"{t_mono_ns},{count},{last_cls},{infer_us:.1f}\n")
                        csv_file.flush()
                        summary_win.add(infer_us)

                        now = time.monotonic()
                        if (now - last_fsync) >= 1.0:
                            os.fsync(csv_file.fileno())
                            last_fsync = now
                        _maybe_report()
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
    finally:
        try:
            _maybe_report(force=True)
        except OSError:
            pass
        try:
            csv_file.flush()
            os.fsync(csv_file.fileno())
        finally:
            csv_file.close()
        for sock in (srv_sock, udp_sock):
            try:
                sock.close()
            except OSError:
                pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibrate", type=int, default=None, help="Run calibration with N timed inferences per width")
    parser.add_argument("--label", type=str, default=None, help="Run label for output files")
    parser.add_argument("--pc-ip", type=str, default=None, help="PC IP address for UDP summaries")
    parser.add_argument("--threads", type=int, default=3, help="ONNX Runtime intra-op thread count")
    parser.add_argument("--width", type=int, default=None, help="Selected CNN channel width")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    parser.add_argument("--port", type=int, default=5555, help="TCP ingest listen port")
    parser.add_argument("--pc-port", type=int, default=5556, help="PC UDP summary port")
    args = parser.parse_args(argv)

    import onnxruntime as ort  # Imported inside main so helpers remain testable without onnxruntime.

    if args.calibrate is not None:
        return _run_calibrate(ort, args.calibrate, args.threads, args.out)

    missing = [name for name, val in (("--label", args.label), ("--pc-ip", args.pc_ip), ("--width", args.width)) if not val]
    if missing:
        parser.error(f"normal mode requires {' '.join(missing)}")

    return _run_server(
        ort,
        label=args.label,
        pc_ip=args.pc_ip,
        threads=args.threads,
        width=args.width,
        out_dir=args.out,
        port=args.port,
        pc_port=args.pc_port,
    )


if __name__ == "__main__":
    raise SystemExit(main())

