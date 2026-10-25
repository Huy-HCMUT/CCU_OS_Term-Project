#!/usr/bin/env python3
"""
benchmarks/diagnostics/run_clock_check.py
Automated runner and analyzer for clock diagnostics on the DUT board.
Measures DWT, k_cycle_get_32(), and micros() counter deltas across:
  - test_clock_ratio_busy(100, 1000)
  - test_clock_ratio_sleep(100, 1000)
  - test_loop_sleep_vs_spin(0, 1)

Supports --from-csv <path> to recompute robust statistics and summary without hardware.
"""

import argparse
import csv
import datetime
import math
import statistics
import subprocess
import time
from pathlib import Path

ADB = r"C:\Users\Hyen\platform-tools\adb.exe"
DUT_ID = "3125036249"
DIAG_CONTAINER_PATTERN = "pin_test|clock_check"
CORE_VERSION = "0.90.0"

def run_adb(device, cmd):
    res = subprocess.run([ADB, "-s", device, "shell", cmd], capture_output=True, text=True)
    return res.stdout.strip()

def get_container(device, pattern, default):
    out = run_adb(device, f"docker ps --format '{{{{.Names}}}}' | grep -E '{pattern}' | head -n 1")
    return out.strip() if out.strip() else default

def call_bridge(container, method, param):
    py_cmd = f"from arduino.app_utils import Bridge; print(Bridge.call('{method}', {param}))"
    cmd = f"docker exec {container} python3 -c \"{py_cmd}\""
    return run_adb(DUT_ID, cmd)

def calc_mean_std(values):
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(var)

def compute_group_stats(matching):
    """
    Computes mean/std and robust median/MAD outlier statistics for a test group.
    """
    ppm_vals = [((r["dwt_cyc"] / r["kcyc_cyc"]) - 1.0) * 1e6 for r in matching]
    ratio_vals = [r["kcyc_cyc"] / (160.0 * r["micros_us"]) for r in matching]
    diff_vals = [r["dwt_cyc"] - 160 * r["micros_us"] for r in matching]
    lost_vals = [r["dwt_cyc"] - r["kcyc_cyc"] for r in matching]
    dwt_vals = [r["dwt_cyc"] for r in matching]

    ppm_m, ppm_s = calc_mean_std(ppm_vals)
    rat_m, rat_s = calc_mean_std(ratio_vals)
    dif_m, dif_s = calc_mean_std(diff_vals)

    med_ppm = statistics.median(ppm_vals)
    med_lost = statistics.median(lost_vals)
    med_dwt = statistics.median(dwt_vals)

    # MAD of lost_cyc (if MAD is 0, use 1)
    devs = [abs(x - med_lost) for x in lost_vals]
    mad = statistics.median(devs)
    if mad == 0:
        mad = 1.0

    # Outlier criterion: |lost_cyc - median| > 5 * MAD and |lost_cyc - median| > 1000
    outlier_reps = [
        int(r["rep"])
        for r, l in zip(matching, lost_vals)
        if abs(l - med_lost) > 5.0 * mad and abs(l - med_lost) > 1000.0
    ]

    return {
        "ppm_mean": ppm_m,
        "ppm_std": ppm_s,
        "ratio_mean": rat_m,
        "ratio_std": rat_s,
        "diff_mean": dif_m,
        "diff_std": dif_s,
        "med_ppm": med_ppm,
        "med_lost": med_lost,
        "med_dwt": med_dwt,
        "outlier_reps": outlier_reps,
    }

def main():
    parser = argparse.ArgumentParser(description="Run clock diagnostics or analyze saved results.")
    parser.add_argument("--from-csv", type=str, default=None, help="Path to raw CSV file to recompute summary from")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    default_csv_path = repo_root / "results" / "raw" / "clock_diagnostics_2026-10-19.csv"
    summary_path = repo_root / "results" / "clock_diagnostics_summary.md"

    tests = [
        ("test_clock_ratio_busy", 100),
        ("test_clock_ratio_busy", 1000),
        ("test_clock_ratio_sleep", 100),
        ("test_clock_ratio_sleep", 1000),
        ("test_loop_sleep_vs_spin", 0),
        ("test_loop_sleep_vs_spin", 1),
    ]

    records = []

    if args.from_csv:
        csv_path = Path(args.from_csv).resolve()
        print(f"Recomputing summary from saved CSV: {csv_path}")

        date_time_str = "N/A"
        dut_id_str = DUT_ID
        container_str = "N/A"
        core_version_str = CORE_VERSION

        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                line_s = line.strip()
                if line_s.startswith("#"):
                    if "date_time:" in line_s:
                        date_time_str = line_s.split("date_time:", 1)[1].strip()
                    elif "dut_id:" in line_s:
                        dut_id_str = line_s.split("dut_id:", 1)[1].strip()
                    elif "container:" in line_s:
                        container_str = line_s.split("container:", 1)[1].strip()
                    elif "core_version:" in line_s:
                        core_version_str = line_s.split("core_version:", 1)[1].strip()
                    continue
                if not line_s or line_s.startswith("test,"):
                    continue

                parts = [p.strip() for p in line_s.split(",")]
                if len(parts) >= 6:
                    t_name = parts[0]
                    param = int(parts[1])
                    rep = int(parts[2])
                    dwt = int(parts[3]) if parts[3] else None
                    kcyc = int(parts[4]) if parts[4] else None
                    micros = int(parts[5]) if parts[5] else None
                    note = parts[6] if len(parts) > 6 else ""
                    records.append({
                        "test": t_name,
                        "param": param,
                        "rep": rep,
                        "dwt_cyc": dwt,
                        "kcyc_cyc": kcyc,
                        "micros_us": micros,
                        "note": note
                    })
    else:
        csv_path = default_csv_path
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.parent.mkdir(parents=True, exist_ok=True)

        container = get_container(DUT_ID, DIAG_CONTAINER_PATTERN, "tmp-pin_test-main-1")
        now_iso = datetime.datetime.now().isoformat()
        date_time_str = now_iso
        dut_id_str = DUT_ID
        container_str = container
        core_version_str = CORE_VERSION

        print("=" * 80)
        print("CLOCK DIAGNOSTICS: LIVE DUT HARDWARE COUNTER MEASUREMENT")
        print(f"DUT ID: {DUT_ID} | Container: {container} | Core: arduino:zephyr {CORE_VERSION}")
        print("=" * 80)

        for test_name, param in tests:
            print(f"\nRunning {test_name}({param}) [10 repetitions]...")
            for rep in range(10):
                reply = call_bridge(container, test_name, param)
                note = ""
                dwt_cyc = None
                kcyc_cyc = None
                micros_us = None

                try:
                    parts = [p.strip() for p in reply.split(",")]
                    if len(parts) == 3:
                        dwt_cyc = int(parts[0])
                        kcyc_cyc = int(parts[1])
                        micros_us = int(parts[2])
                    else:
                        note = reply
                except Exception:
                    note = reply

                records.append({
                    "test": test_name,
                    "param": param,
                    "rep": rep,
                    "dwt_cyc": dwt_cyc,
                    "kcyc_cyc": kcyc_cyc,
                    "micros_us": micros_us,
                    "note": note
                })

                status_str = f"dwt={dwt_cyc:,}, kcyc={kcyc_cyc:,}, u={micros_us:,}" if dwt_cyc is not None else f"ERR: {note}"
                print(f"  Rep {rep+1}/10: {status_str}")
                time.sleep(0.5)

        # Write CSV
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(f"# date_time: {date_time_str}\n")
            f.write(f"# dut_id: {dut_id_str}\n")
            f.write(f"# container: {container_str}\n")
            f.write(f"# core_version: {core_version_str}\n")
            f.write("test,param,rep,dwt_cyc,kcyc_cyc,micros_us,note\n")
            for r in records:
                dwt_s = str(r["dwt_cyc"]) if r["dwt_cyc"] is not None else ""
                kcyc_s = str(r["kcyc_cyc"]) if r["kcyc_cyc"] is not None else ""
                u_s = str(r["micros_us"]) if r["micros_us"] is not None else ""
                f.write(f"{r['test']},{r['param']},{r['rep']},{dwt_s},{kcyc_s},{u_s},{r['note']}\n")

        print(f"\n[OK] Raw results saved to: {csv_path}")

    # Build summary lines
    summary_lines = []
    summary_lines.append("# Clock Diagnostics Summary")
    summary_lines.append(f"\n- **Date:** {date_time_str}")
    summary_lines.append(f"- **DUT ID:** `{dut_id_str}`")
    summary_lines.append(f"- **Container:** `{container_str}`")
    summary_lines.append(f"- **Core Version:** `arduino:zephyr {core_version_str}`\n")
    summary_lines.append("| Test | Param | Reps | ppm (DWT vs k_cycle) | median ppm (DWT vs k_cycle) | median lost_cyc | median dwt_cyc | outlier reps | k_cycle / (160·micros) | DWT − 160·micros (cycles) |")
    summary_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    print("\n" + "=" * 125)
    print("SUMMARY RESULTS TABLE")
    print("=" * 125)
    header_fmt = "{:<24} {:<6} {:<5} {:<18} {:<12} {:<12} {:<16} {:<14} {:<16} {:<18}"
    print(header_fmt.format("Test", "Param", "Reps", "ppm (mean±std)", "med ppm", "med lost", "med dwt", "outliers", "kcyc/(160*u)", "DWT-160*u (mean)"))
    print("-" * 145)

    for test_name, param in tests:
        matching = [r for r in records if r["test"] == test_name and r["param"] == param and r["dwt_cyc"] is not None]
        if not matching:
            print(f"{test_name:<24} {param:<6} 0/10  FAILED (No valid samples)")
            summary_lines.append(f"| `{test_name}` | {param} | 0/10 | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED | FAILED |")
            continue

        stats = compute_group_stats(matching)

        ppm_str = f"{stats['ppm_mean']:+.2f} ± {stats['ppm_std']:.2f}"
        med_ppm_str = f"{stats['med_ppm']:+.1f}"
        med_lost_str = f"{stats['med_lost']:,.0f}"
        med_dwt_str = f"{stats['med_dwt']:,.0f}"
        outliers_str = str(stats['outlier_reps']) if stats['outlier_reps'] else "none"
        rat_str = f"{stats['ratio_mean']:.7f} ± {stats['ratio_std']:.7f}"
        dif_str = f"{stats['diff_mean']:+,.1f} ± {stats['diff_std']:.1f}"

        print(header_fmt.format(
            test_name, param, f"{len(matching)}/10", ppm_str, med_ppm_str, med_lost_str, med_dwt_str, outliers_str, rat_str, dif_str
        ))
        summary_lines.append(
            f"| `{test_name}` | {param} | {len(matching)}/10 | {ppm_str} | {med_ppm_str} | {med_lost_str} | {med_dwt_str} | {outliers_str} | {rat_str} | {dif_str} |"
        )

    # Preserve any existing Outcome section in results/clock_diagnostics_summary.md
    existing_outcome = ""
    if summary_path.exists():
        content = summary_path.read_text(encoding="utf-8")
        if "## Outcome" in content:
            existing_outcome = content[content.index("## Outcome"):]

    output_text = "\n".join(summary_lines) + "\n\n"
    if existing_outcome:
        output_text += existing_outcome
    else:
        output_text += "\n"

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(output_text)

    print(f"\n[OK] Summary saved to: {summary_path}")

if __name__ == "__main__":
    main()
