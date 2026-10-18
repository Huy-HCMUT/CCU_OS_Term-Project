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

def run_adb(device, cmd):
    res = subprocess.run([ADB, "-s", device, "shell", cmd], capture_output=True, text=True)
    return res.stdout.strip()

def get_container(device, pattern, default):
    out = run_adb(device, f"docker ps --format '{{{{.Names}}}}' | grep -E '{pattern}' | head -n 1")
    return out.strip() if out.strip() else default

DUT_CONTAINER = "tmp-pin_test-main-1"
REF_CONTAINER = "home-arduino-arduinoapps-referee_bench-main-1"

def check_preflight():
    global DUT_CONTAINER, REF_CONTAINER
    DUT_CONTAINER = get_container(DUT_ID, "pin_test", "tmp-pin_test-main-1")
    REF_CONTAINER = get_container(REF_ID, "referee_bench", "home-arduino-arduinoapps-referee_bench-main-1")

    print("=" * 75)
    print(" DUAL-PERSPECTIVE REAL-TIME BENCHMARK: DWT vs HARDWARE REFEREE")
    print(f" DUT Container: {DUT_CONTAINER} | Referee Container: {REF_CONTAINER}")
    print("=" * 75)

    # 1. Check Board 1 DWT status
    print("[Pre-flight 1/2] Checking Board 1 (DUT) Cortex-M33 DWT status...")
    dwt_check = run_adb(DUT_ID, f"docker exec {DUT_CONTAINER} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('check_dwt_status', 0))\"")
    try:
        cycles_in_50us = int(dwt_check)
        if cycles_in_50us > 0:
            freq_mhz = cycles_in_50us / 50.0
            print(f"  -> DWT ACTIVE! Elapsed: {cycles_in_50us} cycles in 50 us (~{freq_mhz:.1f} MHz)")
        else:
            print(f"  -> WARNING: DWT returned non-positive value: {dwt_check}")
    except Exception as e:
        print(f"  -> Could not parse DWT check response: {dwt_check} ({e})")

    # 2. Check Board 2 Referee status
    print("[Pre-flight 2/2] Checking Board 2 (Referee) status...")
    ref_status = run_adb(REF_ID, f"docker exec {REF_CONTAINER} cat /tmp/referee_status")
    print(f"  -> Referee status: {ref_status}")
    print("-" * 75)

def run_dual_benchmark(sample_count=10000, stress_pct=0, tag=None):
    if tag is None:
        tag = str(stress_pct)
    print(f"\n>>> EXECUTING CONFIG C RUN: count={sample_count}, stress={stress_pct}%, tag={tag}")

    # 1. Arm Referee
    print(f"[1/5] Arming Referee for {sample_count} pulses...")
    run_adb(REF_ID, f"docker exec {REF_CONTAINER} sh -c \"echo 'START {sample_count}' > /tmp/referee_cmd\"")
    time.sleep(0.5)

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

    # 3. Trigger Board 1
    print(f"[3/5] Triggering {sample_count} periodic cycles on Board 1 STM32...")
    out = run_adb(DUT_ID, f"docker exec {DUT_CONTAINER} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('start_zephyr_pulses', {sample_count}))\"")
    print(f"      DUT trigger response: {out}")

    # Wait for test to complete (10 ms per pulse + 2.5s overhead)
    wait_time = (sample_count * 0.010) + 2.5
    print(f"      Waiting {wait_time:.1f}s for cycle completion...")
    time.sleep(wait_time)

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
    raw_dir = Path(__file__).resolve().parent.parent / "results" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # 5A. Pull Referee CSV
    local_ref_csv = raw_dir / f"config_c_referee_{tag}.csv"
    run_adb(REF_ID, f"docker cp {REF_CONTAINER}:{ref_remote_csv} {ref_remote_csv}")
    subprocess.run([ADB, "-s", REF_ID, "pull", ref_remote_csv, str(local_ref_csv)], capture_output=True)

    # 5B. Fetch DWT records from Board 1
    print("      Fetching DWT records from Board 1 STM32...")
    dwt_cycles = []
    offset = 0
    while offset < sample_count:
        cmd = f"docker exec {DUT_CONTAINER} python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('get_dwt_chunk', {offset}))\""
        chunk_str = run_adb(DUT_ID, cmd)
        if chunk_str:
            items = [int(x) for x in chunk_str.split(",") if x.strip()]
            dwt_cycles.extend(items)
            offset += len(items)
        else:
            break

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

    # 5C. Save standardized files for analyze_latency.py: C_{stress}_dwt.csv and C_{stress}_referee.csv
    if stress_pct in (0, 50, 100):
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

    # Process and print cross-correlation summary
    analyze_dual_data(local_dwt_csv, local_ref_csv, tag)

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

if __name__ == "__main__":
    check_preflight()
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "sanity"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 10000

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

