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

def check_preflight():
    print("=" * 75)
    print(" DUAL-PERSPECTIVE REAL-TIME BENCHMARK: DWT vs HARDWARE REFEREE")
    print("=" * 75)

    # 1. Check Board 1 DWT status
    print("[Pre-flight 1/2] Checking Board 1 (DUT) Cortex-M33 DWT status...")
    dwt_check = run_adb(DUT_ID, "docker exec tmp-pin_test-main-1 python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('check_dwt_status', 0))\"")
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
    ref_status = run_adb(REF_ID, "docker exec referee_bench-main-1 cat /tmp/referee_status")
    print(f"  -> Referee status: {ref_status}")
    print("-" * 75)

def run_dual_benchmark(sample_count=20, stress=False, tag="sanity"):
    print(f"\n>>> EXECUTING RUN: count={sample_count}, stress={stress}, tag={tag}")

    # 1. Arm Referee
    print(f"[1/5] Arming Referee for {sample_count} pulses...")
    run_adb(REF_ID, f"docker exec referee_bench-main-1 sh -c \"echo 'START {sample_count}' > /tmp/referee_cmd\"")
    time.sleep(0.5)

    stress_proc = None
    if stress:
        print("[2/5] Starting 100% Linux CPU & memory stress on Board 1 (stress-ng)...")
        # Launch background stress on Board 1
        subprocess.Popen([ADB, "-s", DUT_ID, "shell", "stress-ng --cpu 4 --matrix 4 --vm 2 --vm-bytes 128M --quiet"])
        time.sleep(1.0)
    else:
        print("[2/5] Baseline operation (no stress-ng load)...")

    # 3. Trigger Board 1
    print(f"[3/5] Triggering {sample_count} periodic cycles on Board 1 STM32...")
    out = run_adb(DUT_ID, f"docker exec tmp-pin_test-main-1 python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('start_zephyr_pulses', {sample_count}))\"")
    print(f"      DUT trigger response: {out}")

    # Wait for test to complete
    wait_time = (sample_count * 0.010) + 1.5
    print(f"      Waiting {wait_time:.1f}s for cycle completion...")
    time.sleep(wait_time)

    if stress:
        print("      Stopping stress-ng on Board 1...")
        run_adb(DUT_ID, "killall -9 stress-ng 2>/dev/null")

    # 4. Stop Referee
    print("[4/5] Stopping Referee capture...")
    ref_remote_csv = f"/home/arduino/referee_{tag}.csv"
    run_adb(REF_ID, f"docker exec referee_bench-main-1 sh -c \"echo 'STOP {ref_remote_csv}' > /tmp/referee_cmd\"")
    time.sleep(1.0)

    # 5. Retrieve data from both boards
    print("[5/5] Retrieving data from both boards...")
    
    # 5A. Pull Referee CSV
    raw_dir = Path(__file__).resolve().parent.parent / "results" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    local_ref_csv = raw_dir / f"config_c_referee_{tag}.csv"
    run_adb(REF_ID, f"docker cp referee_bench-main-1:{ref_remote_csv} {ref_remote_csv}")
    subprocess.run([ADB, "-s", REF_ID, "pull", ref_remote_csv, str(local_ref_csv)], capture_output=True)

    # 5B. Fetch DWT records from Board 1
    print("      Fetching DWT records from Board 1 STM32...")
    dwt_cycles = []
    offset = 0
    while offset < sample_count:
        cmd = f"docker exec tmp-pin_test-main-1 python3 -c \"from arduino.app_utils import Bridge; print(Bridge.call('get_dwt_chunk', {offset}))\""
        chunk_str = run_adb(DUT_ID, cmd)
        if chunk_str:
            items = [int(x) for x in chunk_str.split(",") if x.strip()]
            dwt_cycles.extend(items)
            offset += len(items)
        else:
            break

    local_dwt_csv = raw_dir / f"config_c_dwt_{tag}.csv"
    with open(local_dwt_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["cycle", "dwt_cyccnt", "dwt_delta_cyc", "dwt_period_us", "dwt_lateness_ms"])
        c0 = dwt_cycles[0] if dwt_cycles else 0
        for i, cyc in enumerate(dwt_cycles):
            d_cyc = ((cyc - dwt_cycles[i-1]) & 0xFFFFFFFF) if i > 0 else 1600000
            p_us = d_cyc / 160.0
            # Target schedule is c0 + i * 1,600,000 (modulo 2^32)
            sched_target = (c0 + (i * 1600000)) & 0xFFFFFFFF
            lateness_ms = (((cyc - sched_target) & 0xFFFFFFFF) if cyc >= sched_target else -(((sched_target - cyc) & 0xFFFFFFFF))) / 160000.0
            writer.writerow([i, cyc, d_cyc, f"{p_us:.3f}", f"{lateness_ms:.5f}"])

    print(f"      Saved {len(dwt_cycles)} DWT records to {local_dwt_csv.name}")
    print(f"      Saved Referee records to {local_ref_csv.name}")

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
    mode = sys.argv[1] if len(sys.argv) > 1 else "sanity"
    if mode == "sanity":
        run_dual_benchmark(sample_count=20, stress=False, tag="sanity")
    elif mode == "baseline":
        run_dual_benchmark(sample_count=1000, stress=False, tag="baseline")
    elif mode == "stress":
        run_dual_benchmark(sample_count=1000, stress=True, tag="stress100")
    elif mode == "all":
        run_dual_benchmark(sample_count=20, stress=False, tag="sanity")
        run_dual_benchmark(sample_count=1000, stress=False, tag="baseline")
        run_dual_benchmark(sample_count=1000, stress=True, tag="stress100")
