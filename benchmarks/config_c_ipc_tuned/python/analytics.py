"""analytics.py - Vibration analytics and prescriptive maintenance setpoint calculation.

Ports the FFT-based peak detection and prescriptive maintenance setpoint rules from
mpu_linux/workload/dual_thread_bench.c:141-151 and fft_math.c:92-117, computed in float64
(the C implementation uses float32).
"""

from pathlib import Path
import numpy as np

FFT_SIZE = 1024
FS_HZ = 12000
PERIOD_NS = 85_333_333


def load_frames(path) -> np.ndarray:
    """Load binary vibration frames (float32, 1024 samples per frame)."""
    p = Path(path)
    data = np.fromfile(p, dtype=np.float32)
    if len(data) == 0 or len(data) % FFT_SIZE != 0:
        raise ValueError(
            f"Invalid frame data length {len(data)} in {path}; must be non-zero multiple of {FFT_SIZE}"
        )
    return data.reshape(-1, FFT_SIZE)


def synthetic_frames() -> np.ndarray:
    """Generate 40 synthetic multi-harmonic vibration frames (port of dual_thread_bench.c:90-102)."""
    num_frames = 40
    frames = np.zeros((num_frames, FFT_SIZE), dtype=np.float32)
    for frame in range(num_frames):
        rem = frame % 4
        if rem == 0:
            f_fault = 0.0
        elif rem == 1:
            f_fault = 135.0
        elif rem == 2:
            f_fault = 95.0
        else:
            f_fault = 175.0

        i = np.arange(FFT_SIZE, dtype=np.float32)
        t = i / float(FS_HZ)
        sig = 0.05 * np.sin(2.0 * np.pi * 30.0 * t)
        if f_fault > 0.0:
            sig = sig + 0.35 * np.sin(2.0 * np.pi * f_fault * t)
        frames[frame] = sig.astype(np.float32)

    return frames


def peak_of_frame(frame: np.ndarray) -> tuple[int, float]:
    """Compute single-sided Hanning FFT spectrum and return (peak_bin, peak_magnitude)."""
    w = frame.astype(np.float64) * np.hanning(FFT_SIZE)
    mag = np.abs(np.fft.fft(w))[: FFT_SIZE // 2] / FFT_SIZE
    mag[1:] *= 2.0
    peak_bin = 1 + int(np.argmax(mag[1:]))
    return (peak_bin, float(mag[peak_bin]))


def setpoint_for_frame(frame: np.ndarray) -> int:
    """Determine motor speed setpoint percentage based on dominant fault frequency."""
    peak_bin, peak_mag = peak_of_frame(frame)
    if peak_mag > 0.15:
        if peak_bin >= 150:
            return 60
        elif peak_bin >= 115:
            return 70
        elif peak_bin >= 75:
            return 85
    return 100

