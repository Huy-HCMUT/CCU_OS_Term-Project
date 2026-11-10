import importlib.util
import json
import os
from pathlib import Path
import pytest

HARNESS_PATH = Path(__file__).resolve().parents[1] / "run_config_c_hardware_test.py"
GOLDEN_PATH = Path(__file__).resolve().parent / "baseline_commands.json"


def load_harness():
    spec = importlib.util.spec_from_file_location("harness", HARNESS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sanitize(obj, tmp_str):
    if isinstance(obj, str):
        res = obj.replace(tmp_str, "<RAW>")
        res = res.replace(tmp_str.replace("\\", "/"), "<RAW>")
        res = res.replace("<RAW>\\", "<RAW>/")
        return res
    elif isinstance(obj, list):
        return [sanitize(x, tmp_str) for x in obj]
    elif isinstance(obj, dict):
        return {k: sanitize(v, tmp_str) for k, v in obj.items()}
    return obj


@pytest.fixture
def harness_env(tmp_path, monkeypatch):
    mod = load_harness()
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)

    recorded = []
    dwt_calls = 0

    def mock_run_adb(device, cmd):
        nonlocal dwt_calls
        recorded.append([device, cmd])
        if "check_dwt_status" in cmd:
            return "8000"
        if "start_zephyr_pulses" in cmd:
            return "1"
        if "get_dwt_chunk" in cmd:
            dwt_calls += 1
            if getattr(mod, "_mock_dwt_100_200", False):
                return "100,200" if dwt_calls == 1 else ""
            return ""
        if "get_seq_chunk" in cmd:
            return ""
        if "get_rx_count" in cmd:
            return "0"
        return ""

    def mock_popen(args, *a, **kw):
        recorded.append(["popen", args])
        return None

    def mock_run(args, *a, **kw):
        recorded.append(["run", args])
        return None

    def mock_sleep(sec):
        pass

    monkeypatch.setattr(mod, "run_adb", mock_run_adb)
    monkeypatch.setattr(mod.subprocess, "Popen", mock_popen)
    monkeypatch.setattr(mod.subprocess, "run", mock_run)
    monkeypatch.setattr(mod.time, "sleep", mock_sleep)

    def record(**kw):
        recorded.clear()
        variant = kw.get("variant", None)
        mod.check_preflight(variant=variant)
        mod.run_dual_benchmark(**kw)
        tmp_str = str(tmp_path)
        return sanitize(list(recorded), tmp_str)

    return mod, record, recorded, tmp_path


def test_baseline_commands(harness_env):
    mod, record, _, _ = harness_env

    cases = {
        "sanity": record(sample_count=20, stress_pct=0, tag="sanity"),
        "s0": record(sample_count=10000, stress_pct=0, tag="0"),
        "s50": record(sample_count=10000, stress_pct=50, tag="50"),
        "s100": record(sample_count=10000, stress_pct=100, tag="100"),
    }

    if os.environ.get("WRITE_GOLDEN") == "1":
        with open(GOLDEN_PATH, "w") as f:
            json.dump(cases, f, indent=1)
        print(f"Wrote golden baseline commands to {GOLDEN_PATH}")
    else:
        assert GOLDEN_PATH.exists(), f"Golden file {GOLDEN_PATH} does not exist"
        with open(GOLDEN_PATH, "r") as f:
            expected = json.load(f)
        assert cases == expected


def test_ipc_sanity_commands(harness_env):
    mod, record, recorded, tmp_path = harness_env

    cmds = record(sample_count=20, stress_pct=0, tag="sanity_ipc", variant="ipc")

    # Flatten command strings for sequential check
    cmd_strings = []
    for entry in cmds:
        if len(entry) == 2 and isinstance(entry[1], str):
            cmd_strings.append(entry[1])

    idx_reset = -1
    idx_start = -1
    idx_trigger = -1
    idx_stop = -1

    for i, c in enumerate(cmd_strings):
        if "reset_ipc" in c and idx_reset == -1:
            idx_reset = i
        elif "echo 'START' > /tmp/sender_cmd" in c and idx_start == -1:
            idx_start = i
        elif "start_zephyr_pulses" in c and idx_trigger == -1:
            idx_trigger = i
        elif "STOP /home/arduino/sender_sanity_ipc.csv" in c and idx_stop == -1:
            idx_stop = i

    assert -1 < idx_reset < idx_start < idx_trigger < idx_stop, (
        f"Expected order reset_ipc < START < start_zephyr_pulses < STOP, got indices "
        f"{idx_reset}, {idx_start}, {idx_trigger}, {idx_stop}"
    )

    # Assert every DUT docker exec uses config_c_ipc
    for entry in cmds:
        if len(entry) == 2 and entry[0] == mod.DUT_ID and "docker exec" in entry[1]:
            assert "docker exec config_c_ipc" in entry[1], f"DUT docker exec did not use config_c_ipc: {entry[1]}"

    # Assert tmp_path / "ipc" exists afterwards
    assert (tmp_path / "ipc").exists()


def test_b2_files(harness_env):
    mod, record, recorded, tmp_path = harness_env
    mod._mock_dwt_100_200 = True

    cmds = record(sample_count=20, stress_pct=50, tag="50_b2", variant="b2")

    # Assert tmp_path / "baseline_dwtref" / "C_50_b2.csv" exists
    b2_csv = tmp_path / "baseline_dwtref" / "C_50_b2.csv"
    assert b2_csv.exists(), f"Expected {b2_csv} to exist"

    # Assert that no C_*referee* file exists anywhere under tmp_path
    referee_std_files = list(tmp_path.glob("**/C_*referee*"))
    assert len(referee_std_files) == 0, f"Found unexpected referee standard files: {referee_std_files}"

    # Assert no command contains sender_cmd or reset_ipc
    for entry in cmds:
        if len(entry) == 2 and isinstance(entry[1], str):
            assert "sender_cmd" not in entry[1]
            assert "reset_ipc" not in entry[1]
