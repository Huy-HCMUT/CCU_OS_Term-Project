#!/usr/bin/env python3
"""
CWRU Bearing Vibration Dataset Ingestion & Preprocessing Script
Project: CCU Operating System Term Project (Heterogeneous OS Benchmarking)
Tracks: Task P2.3 & Task P3.1

Downloads the official CWRU 0 HP baseline files (12 kHz Drive End):
  - 97.mat:  Normal Baseline (1797 rpm)
  - 105.mat: Inner Race Fault (0.007", 1797 rpm)
  - 118.mat: Ball Fault (0.007", 1797 rpm)
  - 130.mat: Outer Race Fault (0.007" centered @ 6:00, 1797 rpm)

Slices signals into fixed 1024-sample windows (85.33 ms of continuous signal),
generates:
  1. data/processed/cwru_1024_windows.npz   (NumPy arrays for Python ML training)
  2. data/processed/cwru_test_frames.bin    (Raw float32 frames for C benchmark replay)
  3. data/processed/cwru_dataset_info.json  (Summary metadata)
"""

import os
import sys
import json
import struct
import urllib.request
from pathlib import Path
import numpy as np
import scipy.io

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw" / "cwru"
PROCESSED_DIR = BASE_DIR / "processed"

FILES_SPEC = [
    {
        "id": "97",
        "filename": "97.mat",
        "url": "https://engineering.case.edu/sites/default/files/97.mat",
        "class_id": 0,
        "class_name": "Normal",
        "speed_rpm": 1797,
        "setpoint": 100,  # 100% nominal speed
    },
    {
        "id": "105",
        "filename": "105.mat",
        "url": "https://engineering.case.edu/sites/default/files/105.mat",
        "class_id": 1,
        "class_name": "InnerRaceFault",
        "speed_rpm": 1797,
        "setpoint": 70,   # Derate to 70% speed
    },
    {
        "id": "118",
        "filename": "118.mat",
        "url": "https://engineering.case.edu/sites/default/files/118.mat",
        "class_id": 2,
        "class_name": "BallFault",
        "speed_rpm": 1797,
        "setpoint": 85,   # Derate to 85% speed
    },
    {
        "id": "130",
        "filename": "130.mat",
        "url": "https://engineering.case.edu/sites/default/files/130.mat",
        "class_id": 3,
        "class_name": "OuterRaceFault",
        "speed_rpm": 1797,
        "setpoint": 60,   # Derate to 60% speed
    },
]

WINDOW_SIZE = 1024     # 1024 samples @ 12 kHz = 85.33 ms
SAMPLING_RATE_HZ = 12000

def download_file(url: str, dest_path: Path, max_retries: int = 5):
    """Download a file with atomic rename and MAT integrity validation."""
    if dest_path.exists():
        try:
            # Verify file integrity by attempting to load it
            _ = scipy.io.loadmat(str(dest_path))
            print(f"  [Cached & Valid] {dest_path.name} ({dest_path.stat().st_size:,} bytes).")
            return
        except Exception:
            print(f"  [Corrupted] Existing {dest_path.name} failed loadmat check. Re-downloading...")
            dest_path.unlink(missing_ok=True)

    tmp_path = dest_path.with_suffix(".tmp")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for attempt in range(1, max_retries + 1):
        print(f"  [Downloading attempt {attempt}/{max_retries}] {url} -> {dest_path.name}...")
        tmp_path.unlink(missing_ok=True)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response, open(tmp_path, "wb") as out_file:
                total_size = int(response.headers.get("Content-Length", 0))
                block_size = 64 * 1024
                downloaded = 0
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r    {downloaded:,} / {total_size:,} bytes ({percent:.1f}%)", end="", flush=True)
                    else:
                        print(f"\r    {downloaded:,} bytes downloaded", end="", flush=True)

            print()
            if total_size > 0 and downloaded < total_size:
                raise IOError(f"Truncated download: got {downloaded:,} of {total_size:,} bytes")

            # Validate MAT integrity
            _ = scipy.io.loadmat(str(tmp_path))
            tmp_path.replace(dest_path)
            print(f"    Validation passed ({dest_path.stat().st_size:,} bytes).")
            return
        except Exception as e:
            print(f"\n    Attempt {attempt} failed: {e}")
            tmp_path.unlink(missing_ok=True)
            if attempt == max_retries:
                raise RuntimeError(f"Failed to download and validate {dest_path.name} after {max_retries} attempts.")


def extract_drive_end_signal(mat_path: Path) -> np.ndarray:
    """Load MAT file and extract the Drive End (DE) acceleration time series."""
    mat_data = scipy.io.loadmat(str(mat_path))
    
    # Locate key containing '_DE_time'
    de_key = None
    for key in mat_data.keys():
        if "DE_time" in key:
            de_key = key
            break
            
    if not de_key:
        # Fallback search for any key containing 'DE'
        for key in mat_data.keys():
            if "DE" in key and not key.startswith("__"):
                de_key = key
                break
                
    if not de_key:
        raise KeyError(f"Could not find Drive End (DE) signal in {mat_path.name}. Keys: {list(mat_data.keys())}")
        
    signal = mat_data[de_key].flatten().astype(np.float32)
    return signal

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" CWRU Bearing Dataset Ingestion (0 HP Baseline @ 12 kHz)")
    print("=" * 70)

    # 1. Download all files
    for spec in FILES_SPEC:
        dest_path = RAW_DIR / spec["filename"]
        download_file(spec["url"], dest_path)

    # 2. Extract signals and slice into 1024-sample windows
    all_windows = []
    all_labels = []
    all_setpoints = []
    dataset_summary = {
        "sampling_rate_hz": SAMPLING_RATE_HZ,
        "window_size": WINDOW_SIZE,
        "window_duration_ms": (WINDOW_SIZE / SAMPLING_RATE_HZ) * 1000.0,
        "classes": {}
    }

    print("\nExtracting and segmenting signals into 1024-sample windows:")
    print(f"{'File':<10} | {'Class':<16} | {'Total Points':<12} | {'Windows (1024)':<14} | {'Setpoint'}")
    print("-" * 70)

    # We will also pick 10 representative windows per class to store in a compact binary for C testing
    demo_c_frames = []

    for spec in FILES_SPEC:
        mat_path = RAW_DIR / spec["filename"]
        raw_signal = extract_drive_end_signal(mat_path)
        
        # Calculate number of non-overlapping windows
        n_windows = len(raw_signal) // WINDOW_SIZE
        truncated_signal = raw_signal[: n_windows * WINDOW_SIZE]
        windows = truncated_signal.reshape(n_windows, WINDOW_SIZE)

        all_windows.append(windows)
        all_labels.append(np.full(n_windows, spec["class_id"], dtype=np.int32))
        all_setpoints.append(np.full(n_windows, spec["setpoint"], dtype=np.int32))

        # Take the first 25 windows of each class for C test replay (100 windows total)
        demo_c_frames.append(windows[:25])

        dataset_summary["classes"][spec["class_name"]] = {
            "class_id": spec["class_id"],
            "source_file": spec["filename"],
            "total_points": int(len(raw_signal)),
            "num_windows": int(n_windows),
            "prescribed_setpoint_percent": spec["setpoint"],
            "rpm": spec["speed_rpm"],
            "mean": float(np.mean(raw_signal)),
            "std": float(np.std(raw_signal)),
        }

        print(f"{spec['filename']:<10} | {spec['class_name']:<16} | {len(raw_signal):<12,d} | {n_windows:<14,d} | {spec['setpoint']}%")

    X = np.vstack(all_windows)
    y = np.concatenate(all_labels)
    setpoints = np.concatenate(all_setpoints)

    print("-" * 70)
    print(f"Total Dataset: {X.shape[0]:,d} windows of size {WINDOW_SIZE} ({X.nbytes / (1024*1024):.2f} MB)")

    # 3. Save combined NumPy archive for Python model training
    npz_path = PROCESSED_DIR / "cwru_1024_windows.npz"
    np.savez_compressed(
        npz_path,
        X=X,
        y=y,
        setpoints=setpoints,
        window_size=WINDOW_SIZE,
        sampling_rate=SAMPLING_RATE_HZ
    )
    print(f"\n[Saved] NumPy archive: {npz_path} ({npz_path.stat().st_size / (1024*1024):.2f} MB)")

    # 4. Save compact binary file for C benchmark replay
    # 100 frames total (25 Normal, 25 Inner, 25 Ball, 25 Outer) -> 100 * 1024 floats = 409.6 KB
    demo_frames_array = np.vstack(demo_c_frames).astype(np.float32)
    bin_path = PROCESSED_DIR / "cwru_test_frames.bin"
    demo_frames_array.tofile(bin_path)
    print(f"[Saved] Binary test frames for C benchmark: {bin_path} ({bin_path.stat().st_size / 1024:.1f} KB)")

    # 5. Save dataset summary JSON
    json_path = PROCESSED_DIR / "cwru_dataset_info.json"
    with open(json_path, "w") as f:
        json.dump(dataset_summary, f, indent=2)
    print(f"[Saved] Dataset summary JSON: {json_path}")

    print("\nCWRU dataset ingestion complete!")

if __name__ == "__main__":
    main()
