from collections import Counter
from pathlib import Path
import numpy as np
import pytest

from analytics import (
    FFT_SIZE,
    load_frames,
    peak_of_frame,
    setpoint_for_frame,
    synthetic_frames,
)


def tone(bin_: int, amp: float) -> np.ndarray:
    t = np.arange(FFT_SIZE) / 12000.0
    freq_hz = bin_ * 12000.0 / 1024.0
    return amp * np.sin(2.0 * np.pi * freq_hz * t)


def test_setpoint_rules():
    assert setpoint_for_frame(tone(160, 1.0)) == 60
    assert setpoint_for_frame(tone(130, 1.0)) == 70
    assert setpoint_for_frame(tone(100, 1.0)) == 85
    assert setpoint_for_frame(tone(40, 1.0)) == 100
    assert setpoint_for_frame(tone(160, 0.1)) == 100


def test_peak_of_frame():
    peak_bin, peak_mag = peak_of_frame(tone(160, 1.0))
    assert peak_bin == 160
    assert 0.49 <= peak_mag <= 0.51


def test_load_frames_invalid_length(tmp_path):
    bad_file = tmp_path / "bad.bin"
    bad_data = np.zeros(1000, dtype=np.float32)
    bad_data.tofile(bad_file)

    with pytest.raises(ValueError):
        load_frames(bad_file)


def test_synthetic_frames_shape():
    frames = synthetic_frames()
    assert frames.shape == (40, 1024)
    assert frames.dtype == np.float32


def test_real_frames_report():
    repo_root = Path(__file__).resolve().parents[3]
    real_path = repo_root / "data" / "processed" / "cwru_test_frames.bin"
    if not real_path.exists():
        pytest.skip(f"{real_path} not found")

    frames = load_frames(real_path)
    assert frames.shape == (100, 1024)

    block_names = ["Normal (0-24)", "Inner Race (25-49)", "Ball Fault (50-74)", "Outer Race (75-99)"]
    print("\n--- Real CWRU Frame Setpoints by 25-Frame Block ---")
    for b_idx, name in enumerate(block_names):
        block_frames = frames[b_idx * 25 : (b_idx + 1) * 25]
        sps = [setpoint_for_frame(f) for f in block_frames]
        counts = dict(Counter(sps))
        print(f"Block {b_idx} [{name}]: {counts}")

