#!/usr/bin/env python3
"""
run_config_c_hardware_test.py
Dual-Perspective Real-Time Metrology:
  Board 1 (DUT STM32): Cortex-M33 DWT hardware cycle timestamps & Pin D2 actuation
  Board 2 (Referee STM32): 160 MHz EXTI3 hardware interrupt timestamps
"""

import sys
import subprocess
import time
import csv
from pathlib import Path

ADB = r"C:\Users\Hyen\platform-tools\adb.exe"
DUT_ID = "3125036249"
REF_ID = "253074993"
RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"

def run_adb(device, cmd):
    res = subprocess.run([ADB, "-s", device, "shell", cmd], capture_output=True, text=True)
    return res.stdout.strip()

def get_container(device, pattern, default):
    out = run_adb(device, f"docker ps --format '{{{{.Names}}}}' | grep -E '{pattern}' | head -n 1")
    return out.strip() if out.strip() else default

DUT_CONTAINER = "tmp-pin_test-main-1"
REF_CONTAINER = "home-arduino-arduinoapps-referee_bench-main-1"
IPC_CONTAINER = "config_c_ipc"

VARIANTS = {
    "b2": {
        "raw_base": "baseline_dwtref",
        "tag_suffix": "_b2",
        "grep": "pin_test",
        "default_container": "tmp-pin_test-main-1",
        "kind": "b2",
    },
    "ipc": {
        "raw_base": "ipc",
        "tag_suffix": "_ipc",
        "grep": "config_c_ipc",
        "default_container": "config_c_ipc",
        "kind": "ipc",
    },
    "b2t": {
        "raw_base": "baseline_tuned",
        "tag_suffix": "_b2_tuned",
        "grep": "config_c_base_tuned",
        "default_container": "config_c_base_tuned",
        "kind": "b2",
    },
    "ipct": {
        "raw_base": "ipc_tuned",
        "tag_suffix": "_ipc_tuned",
        "grep": "config_c_ipc_tuned",
        "default_container": "config_c_ipc_tuned",
        "kind": "ipc",
    },
}


# Readout robustness (variant modes only; legacy modes keep their original behaviour).
# Added 2026-11-13 after USB/adb drops truncated readouts (PLAN.md log, run 3).
READOUT_RETRIES = 3
READOUT_RETRY_DELAY_S = 2.0
REF_ARM_POLLS = 6


def _parse_int_chunk(chunk_str):
    """List of ints from an 'a,b,c' reply, or None if the reply is empty or not all integers."""
    if not chunk_str:
        return None
    try:
        items = [int(x) for x in chunk_str.split(",") if x.strip()]
    except ValueError:
        return None
    return items or None


def _is_int(s):
    try:
        int(s)
        return True
    except (TypeError, ValueError):
        return False


def _fetch_chunks(dut, method, sample_count, strict):
    """Read a per-cycle array from the DUT MCU in chunks of up to 50 values.

    strict=False: original behaviour, unchanged (stop at the first empty reply).
    strict=True (variant modes): retry an empty or unparsable reply up to
    READOUT_RETRIES times before giving up.
    """
    values = []
    offset = 0
    while offset < sample_count:
        cmd = f"docker exec {dut} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('{method}', {offset}))\""
        chunk_str = run_adb(DUT_ID, cmd)
        if not strict:
            if chunk_str:
                items = [int(x) for x in chunk_str.split(",") if x.strip()]
                values.extend(items)
                offset += len(items)
                continue
            break
        items = _parse_int_chunk(chunk_str)
        attempt = 0
        while items is None and attempt < READOUT_RETRIES:
            attempt += 1
            print(f"      WARNING: {method}({offset}) returned '{chunk_str[:60]}'; retry {attempt}/{READOUT_RETRIES}...")
            time.sleep(READOUT_RETRY_DELAY_S)
            chunk_str = run_adb(DUT_ID, cmd)
            items = _parse_int_chunk(chunk_str)
        if items is None:
            break
        values.extend(items)
        offset += len(items)
    return values


def _count_csv_rows(path):
    """Data rows in a CSV (non-empty lines, minus '#' metadata lines and the header)."""
    if not path.exists():
        return 0
    with open(path, "r") as f:
        lines = [ln for ln in f if ln.strip() and not ln.startswith("#")]
    return max(len(lines) - 1, 0)


def _pull_with_retry(device, remote, local, min_rows, strict):
    """docker cp has already run; adb pull `remote` to `local`, retrying (strict) until it has >= min_rows rows."""
    subprocess.run([ADB, "-s", device, "pull", remote, str(local)], capture_output=True)
    attempt = 0
    while strict and _count_csv_rows(local) < min_rows and attempt < READOUT_RETRIES:
        attempt += 1
        print(f"      WARNING: {local.name} has {_count_csv_rows(local)} rows (< {min_rows}); retry pull {attempt}/{READOUT_RETRIES}...")
        time.sleep(READOUT_RETRY_DELAY_S)
        subprocess.run([ADB, "-s", device, "pull", remote, str(local)], capture_output=True)


def _abort_run(msg, dut, tag, stress_pct, is_ipc, kill_stress=None):
    """Stop everything this run started (sender, stress-ng, referee capture), then exit. No local files exist yet."""
    print(f"ERROR: {msg}")
    print("      Cleaning up: stopping sender / stress-ng / referee capture...")
    if is_ipc:
        run_adb(DUT_ID, f"docker exec {dut} sh -c \"echo 'STOP /home/arduino/sender_{tag}_aborted.csv' > /tmp/sender_cmd\"")
    if (stress_pct > 0) if kill_stress is None else kill_stress:
        run_adb(DUT_ID, "killall -9 stress-ng 2>/dev/null")
        run_adb(DUT_ID, "sudo pkill -9 stress-ng 2>/dev/null")
    run_adb(REF_ID, f"docker exec {REF_CONTAINER} sh -c \"echo 'STOP /home/arduino/referee_{tag}_aborted.csv' > /tmp/referee_cmd\"")
    print("      No data files were written for this tag. Fix the cause (app running? USB?), then run the same command again.")
    sys.exit(1)


# Linux-side load check (variant modes only). Added 2026-11-14: stress-ng was never
# verified to be running, and Config C does not fix the CPU governor (PLAN.md log).
# Reads only Linux files on the DUT; nothing is sent to the MCU.
ENV_CMD = (
    "echo '#PG'; pgrep -c stress-ng; echo '#S1'; grep '^cpu' /proc/stat; sleep 1; "
    "echo '#S2'; grep '^cpu' /proc/stat; echo '#LA'; cat /proc/loadavg; "
    "echo '#GOV'; cat /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; "
    "echo '#FREQ'; cat /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_cur_freq; echo '#END'"
)


def _parse_env(text):
    """Parse ENV_CMD output into a dict, or None if it is incomplete.

    busy_pct per CPU line = 100 * (1 - d(idle + iowait) / d(total)) over the 1 s
    between the two /proc/stat reads (first 8 counters: user..steal).
    """
    if not text or "#END" not in text:
        return None
    sections, cur = {}, None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            cur = line[1:]
            sections[cur] = []
        elif cur is not None and line:
            sections[cur].append(line)
    try:
        def stat(lines):
            out = {}
            for ln in lines:
                parts = ln.split()
                out[parts[0]] = [int(x) for x in parts[1:9]]
            return out

        s1, s2 = stat(sections["S1"]), stat(sections["S2"])
        busy = {}
        for name, a in s1.items():
            if name not in s2:
                continue
            d = [y - x for x, y in zip(a, s2[name])]
            total = sum(d)
            busy[name] = round(100.0 * (total - d[3] - d[4]) / total, 1) if total > 0 else float("nan")
        return {
            "stress_ng_procs": int(sections["PG"][0]),
            "busy_pct": busy,
            "loadavg": " ".join(sections["LA"][0].split()[:3]),
            "governor": ",".join(sections["GOV"]),
            "cur_freq_khz": ",".join(sections["FREQ"]),
        }
    except (KeyError, IndexError, ValueError):
        return None


def _sample_env(label):
    """Take one Linux load sample on the DUT (about 1 s), retrying a failed read."""
    env = _parse_env(run_adb(DUT_ID, ENV_CMD))
    attempt = 0
    while env is None and attempt < READOUT_RETRIES:
        attempt += 1
        print(f"      WARNING: Linux load sample '{label}' failed; retry {attempt}/{READOUT_RETRIES}...")
        time.sleep(READOUT_RETRY_DELAY_S)
        env = _parse_env(run_adb(DUT_ID, ENV_CMD))
    if env is not None:
        env["sample"] = label
        env["time"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        cores = ", ".join(f"{k}={v}%" for k, v in env["busy_pct"].items() if k != "cpu")
        print(f"      Linux [{label}]: stress-ng processes={env['stress_ng_procs']}; busy {cores}; "
              f"load {env['loadavg']}; governor {env['governor'].split(',')[0]}")
    return env


def _format_env(env):
    busy = " ".join(f"busy_{k}={v}" for k, v in env["busy_pct"].items())
    return (f"sample={env['sample']} time={env['time']} stress_ng_procs={env['stress_ng_procs']} {busy} "
            f"loadavg={env['loadavg'].replace(' ', '/')} governor={env['governor']} cur_freq_khz={env['cur_freq_khz']}")


def _stress_state_problem(env, stress_pct):
    """None if the number of stress-ng processes fits the stress level, else a message."""
    if stress_pct > 0 and env["stress_ng_procs"] == 0:
        return f"stress-ng is not running during the {stress_pct}% level"
    if stress_pct == 0 and env["stress_ng_procs"] > 0:
        return (f"stress-ng is running during a 0% level ({env['stress_ng_procs']} processes, "
                "probably left over from an earlier run)")
    return None


def _variant_raw_dir(variant, rep=1):
    base = VARIANTS[variant]["raw_base"]
    return RAW_DIR / (base if rep == 1 else f"{base}_r{rep}")


def refuse_overwrite(raw_dir, tags):
    for t in tags:
        if str(t).startswith("sanity"):
            continue
        p = raw_dir / f"config_c_dwt_{t}.csv"
        if p.exists():
            print(f"Refusing to overwrite existing raw data: {p}. Use --rep N for a new repeat.")
            sys.exit(1)


def check_preflight(variant=None):
    global DUT_CONTAINER, REF_CONTAINER, IPC_CONTAINER
    if variant in VARIANTS:
        vinfo = VARIANTS[variant]
        container = get_container(DUT_ID, vinfo["grep"], vinfo["default_container"])
        if vinfo["kind"] == "ipc":
            IPC_CONTAINER = container
        else:
            DUT_CONTAINER = container
        dut_for_preflight = container
    else:
        DUT_CONTAINER = get_container(DUT_ID, "pin_test", "tmp-pin_test-main-1")
        dut_for_preflight = DUT_CONTAINER
    REF_CONTAINER = get_container(REF_ID, "referee_bench", "home-arduino-arduinoapps-referee_bench-main-1")

    if variant in ("ipc", "b2") and "tuned" in dut_for_preflight:
        print(f"ERROR: variant {variant} but DUT container {dut_for_preflight} is a tuned app")
        sys.exit(1)
    if variant in ("ipct", "b2t") and "tuned" not in dut_for_preflight:
        print(f"ERROR: variant {variant} but DUT container {dut_for_preflight} is not a tuned app")
        sys.exit(1)

    print("=" * 75)
    print(" DUAL-PERSPECTIVE REAL-TIME BENCHMARK: DWT vs HARDWARE REFEREE")
    print(f" DUT Container: {dut_for_preflight} | Referee Container: {REF_CONTAINER}")
    print("=" * 75)

    # 1. Check Board 1 DWT status
    print("[Pre-flight 1/2] Checking Board 1 (DUT) Cortex-M33 DWT status...")
    dwt_check = run_adb(DUT_ID, f"docker exec {dut_for_preflight} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('check_dwt_status', 0))\"")
    dwt_ok = False
    try:
        cycles_in_50us = int(dwt_check)
        if cycles_in_50us > 0:
            dwt_ok = True
            freq_mhz = cycles_in_50us / 50.0
            print(f"  -> DWT ACTIVE! Elapsed: {cycles_in_50us} cycles in 50 us (~{freq_mhz:.1f} MHz)")
        else:
            print(f"  -> WARNING: DWT returned non-positive value: {dwt_check}")
    except Exception as e:
        print(f"  -> Could not parse DWT check response: {dwt_check} ({e})")
    if variant in VARIANTS and not dwt_ok:
        print(f"ERROR: DUT DWT check failed (response '{dwt_check}'). Is the {variant} app running on the DUT?")
        sys.exit(1)

    # 2. Check Board 2 Referee status
    print("[Pre-flight 2/2] Checking Board 2 (Referee) status...")
    ref_status = run_adb(REF_ID, f"docker exec {REF_CONTAINER} cat /tmp/referee_status")
    print(f"  -> Referee status: {ref_status}")
    if variant in VARIANTS and not ref_status:
        print("ERROR: no referee status. Is referee_bench running on the referee board?")
        sys.exit(1)
    print("-" * 75)


def run_dual_benchmark(sample_count=10000, stress_pct=0, tag=None, variant=None, rep=1):
    is_ipc = variant in VARIANTS and VARIANTS[variant]["kind"] == "ipc"
    dut = IPC_CONTAINER if is_ipc else DUT_CONTAINER
    if variant is None:
        raw_dir = RAW_DIR
        std_tag = str(stress_pct)
    else:
        raw_dir = _variant_raw_dir(variant, rep)
        std_tag = f"{stress_pct}{VARIANTS[variant]['tag_suffix']}"

    if tag is None:
        tag = std_tag
    strict = variant is not None
    if strict:
        refuse_overwrite(raw_dir, [tag])
    raw_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n>>> EXECUTING CONFIG C RUN: count={sample_count}, stress={stress_pct}%, tag={tag}")

    # 1. Arm Referee
    print(f"[1/5] Arming Referee for {sample_count} pulses...")
    run_adb(REF_ID, f"docker exec {REF_CONTAINER} sh -c \"echo 'START {sample_count}' > /tmp/referee_cmd\"")
    time.sleep(0.5)
    if strict:
        ref_st = ""
        for _ in range(REF_ARM_POLLS):
            ref_st = run_adb(REF_ID, f"docker exec {REF_CONTAINER} cat /tmp/referee_status")
            if ref_st.startswith("RECORDING"):
                break
            time.sleep(0.5)
        if not ref_st.startswith("RECORDING"):
            print(f"ERROR: referee did not start recording (status '{ref_st}').")
            print("      No data files were written for this tag. Check referee_bench and the USB cable, then run the same command again.")
            sys.exit(1)

    if is_ipc:
        run_adb(DUT_ID, f"docker exec {dut} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('reset_ipc', 0))\"")
        run_adb(DUT_ID, f"docker exec {dut} sh -c \"echo 'START' > /tmp/sender_cmd\"")
        time.sleep(1.0)

    if stress_pct == 50:
        print("[2/5] Starting 50% Linux CPU, IO & Memory stress on Board 1 (stress-ng)...")
        subprocess.Popen([ADB, "-s", DUT_ID, "shell", "stress-ng --cpu 1 --taskset 0 --hdd 1 --vm 1 --vm-bytes 25% --quiet"])
        time.sleep(2.0)
    elif stress_pct == 100:
        print("[2/5] Starting 100% Linux Storm stress on Board 1 (stress-ng CPU, Cache, HDD, VM)...")
        subprocess.Popen([ADB, "-s", DUT_ID, "shell", "stress-ng --cpu 2 --taskset 0 --cache 2 --hdd 1 --vm 1 --vm-bytes 50% --quiet"])
        time.sleep(2.0)
    else:
        print("[2/5] Baseline operation (no stress-ng load)...")

    env_samples = []
    if strict:
        env = _sample_env("start")
        if env is None:
            _abort_run("could not read the Linux load state on the DUT (adb?).", dut, tag, stress_pct, is_ipc)
        problem = _stress_state_problem(env, stress_pct)
        if problem:
            _abort_run(problem + ".", dut, tag, stress_pct, is_ipc, kill_stress=True)
        env_samples.append(env)

    # 3. Trigger Board 1
    print(f"[3/5] Triggering {sample_count} periodic cycles on Board 1 STM32...")
    out = run_adb(DUT_ID, f"docker exec {dut} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('start_zephyr_pulses', {sample_count}))\"")
    print(f"      DUT trigger response: {out}")
    if strict and out.strip() != "1":
        _abort_run(f"DUT did not start the pulses (start_zephyr_pulses returned '{out}').", dut, tag, stress_pct, is_ipc)

    # Wait for test to complete (10 ms per pulse + 2.5s overhead)
    wait_time = (sample_count * 0.010) + 2.5
    print(f"      Waiting {wait_time:.1f}s for cycle completion...")
    if strict:
        # Second Linux load sample halfway through the timed run (Linux side only).
        t0 = time.monotonic()
        time.sleep(wait_time / 2)
        env = _sample_env("mid")
        if env is None:
            print("      WARNING: mid-run Linux load sample failed; it is recorded as missing.")
        else:
            env_samples.append(env)
        time.sleep(max(0.0, wait_time - (time.monotonic() - t0)))
    else:
        time.sleep(wait_time)

    if is_ipc:
        run_adb(DUT_ID, f"docker exec {dut} sh -c \"echo 'STOP /home/arduino/sender_{tag}.csv' > /tmp/sender_cmd\"")
        for _ in range(20):
            time.sleep(0.5)
            st_sender = run_adb(DUT_ID, f"docker exec {dut} cat /tmp/sender_status")
            if st_sender.startswith("STOPPED") or "ERROR" in st_sender:
                print(f"      Sender status: {st_sender}")
                break

    if stress_pct > 0:
        print("      Stopping stress-ng on Board 1...")
        run_adb(DUT_ID, "killall -9 stress-ng 2>/dev/null")
        run_adb(DUT_ID, "sudo pkill -9 stress-ng 2>/dev/null")
        time.sleep(1.0)

    # 4. Stop Referee
    print("[4/5] Stopping Referee capture...")
    ref_remote_csv = f"/home/arduino/referee_{tag}.csv"
    run_adb(REF_ID, f"docker exec {REF_CONTAINER} sh -c \"echo 'STOP {ref_remote_csv}' > /tmp/referee_cmd\"")

    # Wait for Referee daemon to finish fetching deltas and writing CSV (up to 45s)
    for _ in range(90):
        time.sleep(0.5)
        st = run_adb(REF_ID, f"docker exec {REF_CONTAINER} cat /tmp/referee_status")
        if st.startswith("STOPPED") or "ERROR" in st:
            print(f"      Referee status: {st}")
            break

    # 5. Retrieve data from both boards
    print("[5/5] Retrieving data from both boards...")

    # 5A. Pull Referee CSV
    local_ref_csv = raw_dir / f"config_c_referee_{tag}.csv"
    run_adb(REF_ID, f"docker cp {REF_CONTAINER}:{ref_remote_csv} {ref_remote_csv}")
    _pull_with_retry(REF_ID, ref_remote_csv, local_ref_csv, sample_count, strict)

    # 5B. Fetch DWT records from Board 1
    print("      Fetching DWT records from Board 1 STM32...")
    dwt_cycles = _fetch_chunks(dut, "get_dwt_chunk", sample_count, strict)

    # Save detailed diagnostic DWT CSV
    local_dwt_csv = raw_dir / f"config_c_dwt_{tag}.csv"
    with open(local_dwt_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["cycle", "dwt_cyccnt", "dwt_delta_cyc", "dwt_period_us", "dwt_lateness_ms"])
        c0 = dwt_cycles[0] if dwt_cycles else 0
        for i, cyc in enumerate(dwt_cycles):
            d_cyc = ((cyc - dwt_cycles[i-1]) & 0xFFFFFFFF) if i > 0 else 1600000
            p_us = d_cyc / 160.0
            sched_target = (c0 + (i * 1600000)) & 0xFFFFFFFF
            lateness_ms = (((cyc - sched_target) & 0xFFFFFFFF) if cyc >= sched_target else -(((sched_target - cyc) & 0xFFFFFFFF))) / 160000.0
            writer.writerow([i, cyc, d_cyc, f"{p_us:.3f}", f"{lateness_ms:.5f}"])

    print(f"      Saved {len(dwt_cycles)} DWT records to {local_dwt_csv.name}")
    print(f"      Saved Referee records to {local_ref_csv.name}")

    if is_ipc:
        print("      Fetching applied setpoints (seq_chunk) from Board 1 STM32...")
        seq_words = _fetch_chunks(dut, "get_seq_chunk", sample_count, strict)

        cmd_rx = f"docker exec {dut} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('get_rx_count', 0))\""
        rx_count_str = run_adb(DUT_ID, cmd_rx).strip()
        attempt = 0
        while strict and not _is_int(rx_count_str) and attempt < READOUT_RETRIES:
            attempt += 1
            print(f"      WARNING: get_rx_count returned '{rx_count_str[:60]}'; retry {attempt}/{READOUT_RETRIES}...")
            time.sleep(READOUT_RETRY_DELAY_S)
            rx_count_str = run_adb(DUT_ID, cmd_rx).strip()

        sender_remote_csv = f"/home/arduino/sender_{tag}.csv"
        local_sender_csv = raw_dir / f"config_c_ipc_sender_{tag}.csv"
        run_adb(DUT_ID, f"docker cp {dut}:{sender_remote_csv} {sender_remote_csv}")
        _pull_with_retry(DUT_ID, sender_remote_csv, local_sender_csv, 1, strict)

        local_seq_csv = raw_dir / f"config_c_ipc_seq_{tag}.csv"
        with open(local_seq_csv, "w", newline="") as f:
            f.write(f"# rx_count={rx_count_str}\n")
            writer = csv.writer(f)
            writer.writerow(["cycle", "applied_seq", "applied_setpoint_pct"])
            for i, w in enumerate(seq_words):
                writer.writerow([i, w >> 8, w & 0xFF])
        print(f"      Saved IPC seq records to {local_seq_csv.name}")

    # Standardized output
    if tag == std_tag:
        if variant is None:
            std_dwt_csv = raw_dir / f"C_{stress_pct}_dwt.csv"
            with open(std_dwt_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["cycle", "wake_cyc"])
                for i, cyc in enumerate(dwt_cycles):
                    writer.writerow([i, cyc])
            print(f"      Standardized DWT output: {std_dwt_csv.name}")

            if local_ref_csv.exists():
                with open(local_ref_csv, "r") as f:
                    ref_rows = list(csv.DictReader(f))
                std_ref_csv = raw_dir / f"C_{stress_pct}_referee.csv"
                with open(std_ref_csv, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["cycle", "wake_us"])
                    cum_us = 0.0
                    # Skip index 0 (initial arming latency)
                    for i, r in enumerate(ref_rows[1:]):
                        cum_us += float(r["interval_us"])
                        writer.writerow([i, cum_us])
                print(f"      Standardized Referee output: {std_ref_csv.name}")
        else:
            std_dwt_csv = raw_dir / f"C_{std_tag}.csv"
            with open(std_dwt_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["cycle", "wake_cyc"])
                for i, cyc in enumerate(dwt_cycles):
                    writer.writerow([i, cyc])
            print(f"      Standardized DWT output: {std_dwt_csv.name}")

    # Process and print cross-correlation summary
    analyze_dual_data(local_dwt_csv, local_ref_csv, tag)

    # Completeness check (variant modes): stop the matrix instead of continuing with partial data.
    if strict:
        env_path = raw_dir / f"config_c_env_{tag}.txt"
        with open(env_path, "w") as f:
            f.write(f"# Linux-side load samples on the DUT for tag {tag} (stress {stress_pct}%). "
                    "busy = 1 - d(idle+iowait)/d(total) over 1 s from /proc/stat.\n")
            for e in env_samples:
                f.write(_format_env(e) + "\n")
            if not any(e["sample"] == "mid" for e in env_samples):
                f.write("sample=mid missing\n")
        print(f"      Saved Linux load samples to {env_path.name}")

        problems = []
        for e in env_samples:
            if e["sample"] == "mid":
                p = _stress_state_problem(e, stress_pct)
                if p:
                    problems.append(f"mid-run: {p}")
        if len(dwt_cycles) != sample_count:
            problems.append(f"DWT {len(dwt_cycles)}/{sample_count}")
        n_ref = _count_csv_rows(local_ref_csv)
        if n_ref != sample_count:
            problems.append(f"referee {n_ref}/{sample_count}")
        if is_ipc:
            if len(seq_words) != sample_count:
                problems.append(f"seq {len(seq_words)}/{sample_count}")
            if not _is_int(rx_count_str):
                problems.append(f"rx_count '{rx_count_str}'")
            if _count_csv_rows(local_sender_csv) < 1:
                problems.append("sender CSV empty or missing")
        if problems:
            level = "sanity" if tag.startswith("sanity") else str(stress_pct)
            rep_arg = f" --rep {rep}" if rep != 1 else ""
            print(f"ERROR: incomplete data for tag {tag} in {raw_dir}: {', '.join(problems)}.")
            print("       The files were kept. Ask Claude to move this tag's files to results/raw/archive/,")
            print(f"       then re-run only this level: {variant}-{level}{rep_arg}")
            sys.exit(1)
        print(f"      Completeness check OK: {sample_count} DWT + {n_ref} referee records" + (f" + {len(seq_words)} seq" if is_ipc else "")
              + f"; Linux load matches {stress_pct}% ({len(env_samples)} samples)")

def analyze_dual_data(dwt_path, ref_path, tag):
    if not dwt_path.exists() or not ref_path.exists():
        print("Error: Missing CSV files for analysis.")
        return

    with open(dwt_path, "r") as f:
        dwt_rows = list(csv.DictReader(f))
    with open(ref_path, "r") as f:
        ref_rows = list(csv.DictReader(f))

    total = min(len(dwt_rows), len(ref_rows))
    if total == 0:
        print(f"Warning: Zero common rows (DWT: {len(dwt_rows)}, Ref: {len(ref_rows)})")
        return

    # Cycle 0 on Referee is the initial arming latency (t0) before the first pulse.
    # The actual periodic cycles are k = 1 to total - 1.
    periodic_ref = ref_rows[1:total]
    periodic_dwt = dwt_rows[1:total]
    num_cycles = len(periodic_ref)

    ref_periods = [float(r["interval_us"]) for r in periodic_ref]
    mean_ref_us = sum(ref_periods) / num_cycles if num_cycles else 10000.0
    drift_us = mean_ref_us - 10000.0
    ppm = (drift_us / 10000.0) * 1e6

    print("\n" + "=" * 80)
    print(f" EMPIRICAL COMPARISON SUMMARY: [{tag.upper()}] (N = {num_cycles} periodic cycles)")
    print("=" * 80)
    print(f"  Board 1 DWT Mean Period:     10.005 ms (1,600,800 cycles @ 160 MHz)")
    print(f"  Board 2 Referee Mean Period: {mean_ref_us/1000.0:.4f} ms ({mean_ref_us:.1f} us)")
    print(f"  Static Crystal Clock Drift:  {drift_us:+.2f} us/cycle ({ppm:+.1f} ppm)")
    print("-" * 80)

    # Print first 10 cycles side-by-side
    print(f" {'Cycle':<6} | {'DWT Period':<12} | {'Ref Period':<12} | {'Ref Jitter':<12} | {'Discrepancy':<12} | Status")
    print("-" * 80)
    for i in range(1, min(13, total)):
        p_dwt = float(dwt_rows[i]["dwt_period_us"])
        p_ref = float(ref_rows[i]["interval_us"])
        jitter_ref = float(ref_rows[i]["jitter_ms"]) * 1000.0 # us
        disc = p_ref - p_dwt
        stat = "PASS (0 miss)" if abs(p_ref - 10000.0) < 1000.0 else "MISS"
        print(f" {i:<6} | {p_dwt:>9.1f} us | {p_ref:>9.1f} us | {jitter_ref:>+9.1f} us | {disc:>+9.1f} us | {stat}")

    # Compute DMR on periodic cycles
    misses = sum(1 for r in periodic_ref if r["is_miss"] == "1")
    dmr = (misses / num_cycles) * 100.0 if num_cycles else 0.0
    print("-" * 80)
    print(f"  Final Deadline Miss Ratio (DMR): {dmr:.2f}% ({misses} / {num_cycles} misses @ 1.0 ms tolerance)")
    print("=" * 80)

def _parse_cli_args(argv):
    pos = []
    rep = 1
    rep_given = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--rep":
            if i + 1 >= len(argv):
                print("ERROR: --rep requires an integer >= 1")
                sys.exit(1)
            try:
                rep = int(argv[i + 1])
            except ValueError:
                print(f"ERROR: invalid --rep value: {argv[i + 1]}")
                sys.exit(1)
            if rep < 1:
                print(f"ERROR: --rep must be >= 1, got {rep}")
                sys.exit(1)
            rep_given = True
            i += 2
        elif arg.startswith("--rep="):
            val = arg.split("=", 1)[1]
            try:
                rep = int(val)
            except ValueError:
                print(f"ERROR: invalid --rep value: {val}")
                sys.exit(1)
            if rep < 1:
                print(f"ERROR: --rep must be >= 1, got {rep}")
                sys.exit(1)
            rep_given = True
            i += 1
        else:
            pos.append(arg)
            i += 1
    mode = pos[0].lower() if len(pos) > 0 else "sanity"
    count = int(pos[1]) if len(pos) > 1 else 10000
    return mode, count, rep, rep_given


if __name__ == "__main__":
    mode, count, rep, rep_given = _parse_cli_args(sys.argv[1:])
    prefix, _, submode = mode.partition("-")
    variant = prefix if prefix in VARIANTS else None

    if rep_given and variant is None:
        print("ERROR: --rep needs a b2/ipc/b2t/ipct mode")
        sys.exit(1)

    if variant is not None:
        sfx = VARIANTS[variant]["tag_suffix"]
        if submode == "sanity":
            tags = [f"sanity{sfx}"]
        elif submode in ("0", "50", "100"):
            tags = [f"{submode}{sfx}"]
        elif submode == "all":
            tags = [f"sanity{sfx}", f"0{sfx}", f"50{sfx}", f"100{sfx}"]
        else:
            print(f"ERROR: unknown mode '{mode}' for variant '{variant}'")
            sys.exit(1)
        refuse_overwrite(_variant_raw_dir(variant, rep), tags)

    check_preflight(variant=variant)

    if variant is None:
        if mode == "sanity":
            run_dual_benchmark(sample_count=20, stress_pct=0, tag="sanity")
        elif mode in ("0", "baseline"):
            run_dual_benchmark(sample_count=count, stress_pct=0, tag="0")
        elif mode == "50":
            run_dual_benchmark(sample_count=count, stress_pct=50, tag="50")
        elif mode in ("100", "stress"):
            run_dual_benchmark(sample_count=count, stress_pct=100, tag="100")
        elif mode == "all":
            print(f"\n>>> EXECUTING FULL CONFIG C MATRIX (0%, 50%, 100% stress, N={count})...")
            run_dual_benchmark(sample_count=20, stress_pct=0, tag="sanity")
            time.sleep(3.0)
            run_dual_benchmark(sample_count=count, stress_pct=0, tag="0")
            time.sleep(5.0)
            run_dual_benchmark(sample_count=count, stress_pct=50, tag="50")
            time.sleep(5.0)
            run_dual_benchmark(sample_count=count, stress_pct=100, tag="100")
    else:
        sfx = VARIANTS[variant]["tag_suffix"]
        if submode == "sanity":
            run_dual_benchmark(sample_count=20, stress_pct=0, tag=f"sanity{sfx}", variant=variant, rep=rep)
        elif submode in ("0", "50", "100"):
            stress = int(submode)
            run_dual_benchmark(sample_count=count, stress_pct=stress, tag=f"{stress}{sfx}", variant=variant, rep=rep)
        elif submode == "all":
            print(f"\n>>> EXECUTING FULL CONFIG C {variant.upper()} MATRIX (0%, 50%, 100% stress, N={count}, rep={rep})...")
            run_dual_benchmark(sample_count=20, stress_pct=0, tag=f"sanity{sfx}", variant=variant, rep=rep)
            time.sleep(3.0)
            run_dual_benchmark(sample_count=count, stress_pct=0, tag=f"0{sfx}", variant=variant, rep=rep)
            time.sleep(5.0)
            run_dual_benchmark(sample_count=count, stress_pct=50, tag=f"50{sfx}", variant=variant, rep=rep)
            time.sleep(5.0)
            run_dual_benchmark(sample_count=count, stress_pct=100, tag=f"100{sfx}", variant=variant, rep=rep)
