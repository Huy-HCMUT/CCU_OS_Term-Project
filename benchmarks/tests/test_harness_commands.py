import importlib.util
import json
import os
import re
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
    # Simulated boards. "full" (set by record() for variant runs) makes the mock
    # behave like working boards: the referee goes RECORDING/STOPPED, chunks hold
    # data, and `adb pull` writes a complete file. Legacy runs keep the old mock
    # (empty replies), so the golden command list is unchanged.
    state = {"full": False, "n": 0, "ref": "READY 0", "dwt_failed_once": False, "stress": False}

    def flag(name):
        return getattr(mod, name, False)

    def env_text():
        """Output of the harness's ENV_CMD: stress-ng count, two /proc/stat reads, loadavg, governor, freq."""
        if flag("_mock_env_fail"):
            return ""
        procs = 3 if (state["stress"] and not flag("_mock_stress_dead")) else 0
        if flag("_mock_stress_leftover"):
            procs = 2
        busy0 = 1000 if procs else 0          # cpu0 fully busy over the 1 s window when stress runs
        s1 = [[0, 0, 0, 1000, 0, 0, 0, 0] for _ in range(4)]
        s2 = [[busy0, 0, 0, 1000 + (1000 - busy0), 0, 0, 0, 0]] + [[0, 0, 0, 2000, 0, 0, 0, 0] for _ in range(3)]
        def block(rows):
            agg = [sum(col) for col in zip(*rows)]
            lines = ["cpu  " + " ".join(map(str, agg)) + " 0 0"]
            lines += [f"cpu{i} " + " ".join(map(str, r)) + " 0 0" for i, r in enumerate(rows)]
            return "\n".join(lines)
        return "\n".join(["#PG", str(procs), "#S1", block(s1), "#S2", block(s2),
                          "#LA", "0.50 0.40 0.30 1/100 1234",
                          "#GOV", *["schedutil"] * 4, "#FREQ", *["2016000"] * 4, "#END"])

    def chunk(cmd, value_of):
        m = re.search(r"chunk', (\d+)\)", cmd)
        offset = int(m.group(1))
        if offset >= state["n"]:
            return ""
        return ",".join(str(value_of(i)) for i in range(offset, min(offset + 50, state["n"])))

    def mock_run_adb(device, cmd):
        nonlocal dwt_calls
        recorded.append([device, cmd])
        if "/proc/stat" in cmd:
            return env_text()
        if "killall -9 stress-ng" in cmd:
            state["stress"] = False
            return ""
        if "check_dwt_status" in cmd:
            return "" if flag("_mock_dwt_empty") else "8000"
        if state["full"] and device == mod.REF_ID and "/tmp/referee_cmd" in cmd:
            if "echo 'START" in cmd and not flag("_mock_ref_no_record"):
                state["ref"] = f"RECORDING 0 {state['n']}"
            elif "echo 'STOP" in cmd:
                state["ref"] = f"STOPPED {state['n']} /home/arduino/x.csv"
            return ""
        if "cat /tmp/referee_status" in cmd:
            if flag("_mock_ref_empty"):
                return ""
            return state["ref"] if state["full"] else "READY 0"
        if "start_zephyr_pulses" in cmd:
            return "" if flag("_mock_trigger_fail") else "1"
        if "get_dwt_chunk" in cmd:
            dwt_calls += 1
            if state["full"]:
                if flag("_mock_dwt_always_empty"):
                    return ""
                if flag("_mock_dwt_fail_once") and not state["dwt_failed_once"]:
                    state["dwt_failed_once"] = True
                    return ""
                return chunk(cmd, lambda i: 1600000 * i)
            if flag("_mock_dwt_100_200"):
                return "100,200" if dwt_calls == 1 else ""
            return ""
        if "get_seq_chunk" in cmd:
            return chunk(cmd, lambda i: (1 << 8) | 100) if state["full"] else ""
        if "get_rx_count" in cmd:
            return "0"
        return ""

    def mock_popen(args, *a, **kw):
        recorded.append(["popen", args])
        if any("stress-ng" in str(x) for x in args):
            state["stress"] = True
        return None

    def mock_run(args, *a, **kw):
        recorded.append(["run", args])
        if state["full"] and len(args) >= 6 and args[3] == "pull":
            dest = Path(args[5])
            if "referee" in dest.name:
                rows = state["n"] - (5 if flag("_mock_ref_short") else 0)
                lines = ["cycle,interval_cyc,interval_us,interval_ms,jitter_ms,is_miss"]
                lines += [f"{i},1600000,10000.0000,10.000000,0.000000,0" for i in range(rows)]
            else:
                lines = ["# frames_source=cwru period_ns=85333333",
                         "seq,frame_idx,setpoint_pct,release_ns,t_send_ns,t_return_ns,rtt_us,skipped_after,status",
                         "1,0,100,0,0,0,0.0,0,ok"]
            dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
        state["full"] = variant is not None
        state["n"] = kw.get("sample_count", 0)
        state["ref"] = "READY 0"
        state["stress"] = False
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


def test_ipct_rep2_folder(harness_env):
    mod, record, _, tmp_path = harness_env

    cmds = record(sample_count=20, stress_pct=0, tag="sanity_ipc_tuned", variant="ipct", rep=2)

    assert (tmp_path / "ipc_tuned_r2").exists()

    cmd_strings = [entry[1] for entry in cmds if len(entry) == 2 and isinstance(entry[1], str)]
    idx_reset = next((i for i, c in enumerate(cmd_strings) if "reset_ipc" in c), -1)
    idx_start = next((i for i, c in enumerate(cmd_strings) if "echo 'START' > /tmp/sender_cmd" in c), -1)
    idx_trigger = next((i for i, c in enumerate(cmd_strings) if "start_zephyr_pulses" in c), -1)
    idx_stop = next(
        (i for i, c in enumerate(cmd_strings) if "STOP /home/arduino/sender_sanity_ipc_tuned.csv" in c),
        -1,
    )
    assert -1 < idx_reset < idx_start < idx_trigger < idx_stop

    for entry in cmds:
        if len(entry) == 2 and entry[0] == mod.DUT_ID and "docker exec" in entry[1]:
            assert "docker exec config_c_ipc_tuned" in entry[1]


def test_overwrite_guard(harness_env):
    mod, _, recorded, tmp_path = harness_env
    ipc_dir = tmp_path / "ipc"
    ipc_dir.mkdir(parents=True, exist_ok=True)
    (ipc_dir / "config_c_dwt_0_ipc.csv").write_text("cycle\n0\n", encoding="utf-8")

    recorded.clear()
    with pytest.raises(SystemExit):
        mod.run_dual_benchmark(sample_count=20, stress_pct=0, tag="0_ipc", variant="ipc")
    assert len(recorded) == 0


def test_container_mismatch(harness_env, monkeypatch):
    mod, _, _, _ = harness_env
    monkeypatch.setattr(mod, "get_container", lambda device, pattern, default: "config_c_ipc_tuned-main-1")
    with pytest.raises(SystemExit):
        mod.check_preflight(variant="ipc")


def test_b2t_files(harness_env):
    mod, record, _, tmp_path = harness_env
    cmds = record(sample_count=20, stress_pct=50, tag="50_b2_tuned", variant="b2t")

    b2t_csv = tmp_path / "baseline_tuned" / "C_50_b2_tuned.csv"
    assert b2t_csv.exists(), f"Expected {b2t_csv} to exist"

    for entry in cmds:
        if len(entry) == 2 and isinstance(entry[1], str):
            assert "sender_cmd" not in entry[1]
            assert "reset_ipc" not in entry[1]


def test_preflight_aborts_without_dut(harness_env):
    mod, _, _, _ = harness_env
    mod._mock_dwt_empty = True
    with pytest.raises(SystemExit):
        mod.check_preflight(variant="b2")
    mod.check_preflight(variant=None)


def test_preflight_aborts_without_referee(harness_env):
    mod, _, _, _ = harness_env
    mod._mock_ref_empty = True
    with pytest.raises(SystemExit):
        mod.check_preflight(variant="ipc")


# --- Readout robustness (added 2026-11-13 after USB/adb drops, PLAN.md run 3) ---

def _cmd_strings(entries):
    return [e[1] for e in entries if len(e) == 2 and isinstance(e[1], str)]


def test_variant_run_complete_data(harness_env):
    mod, record, _, tmp_path = harness_env
    record(sample_count=120, stress_pct=0, tag="0_ipc", variant="ipc")
    d = tmp_path / "ipc"
    assert mod._count_csv_rows(d / "config_c_dwt_0_ipc.csv") == 120
    assert mod._count_csv_rows(d / "config_c_referee_0_ipc.csv") == 120
    assert mod._count_csv_rows(d / "config_c_ipc_seq_0_ipc.csv") == 120
    assert mod._count_csv_rows(d / "C_0_ipc.csv") == 120


def test_readout_retry_recovers(harness_env):
    mod, record, _, tmp_path = harness_env
    mod._mock_dwt_fail_once = True
    cmds = _cmd_strings(record(sample_count=120, stress_pct=0, tag="0_b2", variant="b2"))
    # 120 values = 3 chunks of up to 50, plus 1 retry of the failed first chunk
    assert sum("get_dwt_chunk" in c for c in cmds) == 4
    assert mod._count_csv_rows(tmp_path / "baseline_dwtref" / "config_c_dwt_0_b2.csv") == 120


def test_incomplete_dwt_exits_and_keeps_files(harness_env):
    mod, record, recorded, tmp_path = harness_env
    mod._mock_dwt_always_empty = True
    with pytest.raises(SystemExit):
        record(sample_count=20, stress_pct=0, tag="0_b2", variant="b2")
    # first attempt + READOUT_RETRIES retries, then give up
    assert sum("get_dwt_chunk" in c for c in _cmd_strings(recorded)) == 1 + mod.READOUT_RETRIES
    assert (tmp_path / "baseline_dwtref" / "config_c_dwt_0_b2.csv").exists()


def test_trigger_failure_aborts_and_cleans_up(harness_env):
    mod, record, recorded, tmp_path = harness_env
    mod._mock_trigger_fail = True
    with pytest.raises(SystemExit):
        record(sample_count=20, stress_pct=50, tag="50_ipc", variant="ipc")
    cmds = _cmd_strings(recorded)
    assert any("killall -9 stress-ng" in c for c in cmds)
    assert any("sender_50_ipc_aborted.csv" in c for c in cmds)
    assert any("referee_50_ipc_aborted.csv" in c for c in cmds)
    assert not any("get_dwt_chunk" in c for c in cmds)
    assert not (tmp_path / "ipc" / "config_c_dwt_50_ipc.csv").exists()


def test_referee_not_armed_exits_before_trigger(harness_env):
    mod, record, recorded, tmp_path = harness_env
    mod._mock_ref_no_record = True
    with pytest.raises(SystemExit):
        record(sample_count=20, stress_pct=0, tag="0_b2", variant="b2")
    assert not any("start_zephyr_pulses" in c for c in _cmd_strings(recorded))
    assert not (tmp_path / "baseline_dwtref" / "config_c_dwt_0_b2.csv").exists()


def test_short_referee_file_retries_then_exits(harness_env):
    mod, record, recorded, _ = harness_env
    mod._mock_ref_short = True
    with pytest.raises(SystemExit):
        record(sample_count=20, stress_pct=0, tag="0_b2", variant="b2")
    pulls = [e for e in recorded if e[0] == "run" and e[1][3] == "pull" and "referee" in e[1][5]]
    assert len(pulls) == 1 + mod.READOUT_RETRIES


# --- Linux load check (added 2026-11-14: stress-ng was never verified, governor not fixed) ---

REAL_ENV_OUTPUT = """#PG
0
#S1
cpu  419255 8 85714 2967022 40223 17530 6515 0 0 0
cpu0 131685 0 26026 716388 1442 5671 2780 0 0 0
cpu1 96046 1 20098 748787 13761 4020 1353 0 0 0
cpu2 95507 0 20070 750033 13462 3909 1166 0 0 0
cpu3 96015 6 19518 751811 11556 3928 1214 0 0 0
#S2
cpu  419285 8 85727 2967379 40223 17532 6515 0 0 0
cpu0 131693 0 26029 716478 1442 5672 2780 0 0 0
cpu1 96052 1 20100 748879 13761 4021 1353 0 0 0
cpu2 95518 0 20074 750118 13462 3910 1167 0 0 0
cpu3 96021 6 19522 751903 11556 3928 1214 0 0 0
#LA
0.22 0.29 0.65 2/354 83350
#GOV
schedutil
schedutil
schedutil
schedutil
#FREQ
2016000
2016000
2016000
2016000
#END
"""


def test_parse_env_real_dut_output(harness_env):
    """Output captured from the DUT on 2026-11-14 (idle, no stress-ng)."""
    mod, _, _, _ = harness_env
    env = mod._parse_env(REAL_ENV_OUTPUT)
    assert env["stress_ng_procs"] == 0
    # cpu0 deltas: 8,0,3,90,0,1,0,0 -> total 102, idle+iowait 90 -> 11.8 % busy
    assert env["busy_pct"]["cpu0"] == 11.8
    # all-CPU line: 30,0,13,357,0,2,0,0 -> total 402, idle+iowait 357 -> 11.2 % busy
    assert env["busy_pct"]["cpu"] == 11.2
    assert env["governor"] == "schedutil,schedutil,schedutil,schedutil"
    assert env["cur_freq_khz"] == "2016000,2016000,2016000,2016000"
    assert env["loadavg"] == "0.22 0.29 0.65"
    assert mod._parse_env("") is None
    assert mod._parse_env(REAL_ENV_OUTPUT.replace("#END", "")) is None


def test_env_file_records_load_under_stress(harness_env):
    mod, record, _, tmp_path = harness_env
    record(sample_count=20, stress_pct=100, tag="100_b2", variant="b2")
    text = (tmp_path / "baseline_dwtref" / "config_c_env_100_b2.txt").read_text(encoding="utf-8")
    assert "sample=start" in text and "sample=mid" in text
    assert text.count("stress_ng_procs=3") == 2
    assert "busy_cpu0=100.0" in text and "governor=schedutil" in text


def test_env_file_at_zero_stress(harness_env):
    mod, record, _, tmp_path = harness_env
    record(sample_count=20, stress_pct=0, tag="0_ipc", variant="ipc")
    text = (tmp_path / "ipc" / "config_c_env_0_ipc.txt").read_text(encoding="utf-8")
    assert text.count("stress_ng_procs=0") == 2
    assert "busy_cpu0=0.0" in text


def test_stress_not_running_aborts_before_trigger(harness_env):
    mod, record, recorded, tmp_path = harness_env
    mod._mock_stress_dead = True
    with pytest.raises(SystemExit):
        record(sample_count=20, stress_pct=50, tag="50_b2", variant="b2")
    cmds = _cmd_strings(recorded)
    assert not any("start_zephyr_pulses" in c for c in cmds)
    assert any("killall -9 stress-ng" in c for c in cmds)
    assert not (tmp_path / "baseline_dwtref" / "config_c_dwt_50_b2.csv").exists()


def test_leftover_stress_at_zero_aborts_and_kills_it(harness_env):
    mod, record, recorded, _ = harness_env
    mod._mock_stress_leftover = True
    with pytest.raises(SystemExit):
        record(sample_count=20, stress_pct=0, tag="0_b2", variant="b2")
    cmds = _cmd_strings(recorded)
    assert not any("start_zephyr_pulses" in c for c in cmds)
    assert any("killall -9 stress-ng" in c for c in cmds)


def test_env_sample_failure_retries_then_aborts(harness_env):
    mod, record, recorded, _ = harness_env
    mod._mock_env_fail = True
    with pytest.raises(SystemExit):
        record(sample_count=20, stress_pct=0, tag="0_b2", variant="b2")
    cmds = _cmd_strings(recorded)
    assert sum("/proc/stat" in c for c in cmds) == 1 + mod.READOUT_RETRIES
    assert not any("start_zephyr_pulses" in c for c in cmds)


def test_legacy_mode_sends_no_env_command(harness_env):
    mod, record, _, _ = harness_env
    cmds = _cmd_strings(record(sample_count=20, stress_pct=100, tag="100"))
    assert not any("/proc/stat" in c for c in cmds)
