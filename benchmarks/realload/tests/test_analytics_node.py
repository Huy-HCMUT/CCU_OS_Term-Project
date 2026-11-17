from __future__ import annotations

import builtins
import importlib
from pathlib import Path
import sys

import numpy as np
import pytest

REALLOAD_DIR = Path(__file__).resolve().parents[1]
if str(REALLOAD_DIR) not in sys.path:
    sys.path.insert(0, str(REALLOAD_DIR))

import analytics_node  # noqa: E402


def test_import_without_onnxruntime(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "onnxruntime" or name.startswith("onnxruntime."):
            raise ModuleNotFoundError("No module named 'onnxruntime'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    mod = importlib.reload(analytics_node)
    assert hasattr(mod, "WindowAssembler")
    assert hasattr(mod, "SummaryWindow")
    assert "onnxruntime" not in sys.modules


def test_window_assembler_splits_across_float_boundary():
    rng = np.random.default_rng(7)
    samples = rng.normal(size=2048).astype("<f4")
    raw = samples.tobytes()
    assert len(raw) == 2 * 4096

    # 1.5 windows + 3 extra bytes (splitting inside a float), then the remaining 0.5 window
    split_idx = 4096 + 2048 + 3
    asm = analytics_node.WindowAssembler()

    w1_list = asm.feed(raw[:split_idx])
    assert len(w1_list) == 1
    assert w1_list[0].shape == (1, 1, 1024)
    assert w1_list[0].dtype == np.float32
    np.testing.assert_allclose(w1_list[0].ravel(), samples[:1024], rtol=0, atol=0)

    w2_list = asm.feed(raw[split_idx:])
    assert len(w2_list) == 1
    assert w2_list[0].shape == (1, 1, 1024)
    assert w2_list[0].dtype == np.float32
    np.testing.assert_allclose(w2_list[0].ravel(), samples[1024:], rtol=0, atol=0)

    # No leftover bytes remain
    assert asm.feed(b"") == []


def test_summary_window_median_and_reset():
    sw = analytics_node.SummaryWindow()
    for val in (1.0, 2.0, 3.0, 4.0):
        sw.add(val)

    s1 = sw.summary("A_0_rdeploy", count=12, last_cls=3)
    assert s1 == {
        "label": "A_0_rdeploy",
        "count": 12,
        "last_cls": 3,
        "infer_p50_us": pytest.approx(2.5),
        "n": 4,
    }

    # Reset after summary()
    s2 = sw.summary("A_0_rdeploy", count=12, last_cls=3)
    assert s2["n"] == 0
    assert s2["infer_p50_us"] == 0.0

