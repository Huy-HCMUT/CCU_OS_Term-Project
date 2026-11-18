#!/usr/bin/env python3
"""benchmarks/diagnostics/run_pwm_loopback.py

Phase 6b test 1: PWM loopback on board 3 (one jumper D3 -> D8 on the same board).
Runs the `pwm_loopback` app's tests and checks whether the "speed command as PWM" design works:

  1. Steady capture at 80 % and 48 % duty: period, duty, missed edges.
  2. Switch test: delay from analogWrite() to the first PWM period with the new duty,
     and the duration of one analogWrite() call.

Usage (board 3 running the pwm_loopback app, nothing else wired):
  .venv\\Scripts\\python benchmarks\\diagnostics\\run_pwm_loopback.py --serial <BOARD3_SERIAL>
Recompute the summary from saved raw files (no hardware):
  .venv\\Scripts\\python benchmarks\\diagnostics\\run_pwm_loopback.py --from-raw results\\raw\\pwm_loopback_<date>

Raw files go to results/raw/pwm_loopback_<date>/ (never overwritten); the summary goes to
results/diagnostics/pwm_loopback_summary.md. The board serial is not written to any file.
"""

import argparse
import datetime
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ADB = r"C:\Users\Hyen\platform-tools\adb.exe"
CLOCK_HZ = 160e6
CYC_PER_US = CLOCK_HZ / 1e6
NOMINAL_PERIOD_CYC = 320_000          # 2 ms at 160 MHz (500 Hz PWM)
REMOTE_HELPER = "/tmp/pwm_loopback_helper.py"
CONTAINER_PATTERN = "pwm_loopback"
DUTIES = (800, 480)                   # permille

# Pass criteria (decided before the test)
PERIOD_TOL_REL = 0.001                # mean period within 0.1 % of 2.000 ms
DUTY_TOL = 0.005                      # duty within +-0.5 percentage points
MIN_PERIOD_FRACTION = 0.99            # at least 99 % of the expected periods captured
SWITCH_START_MAX_US = 2000.0          # first new period starts within one PWM period of the call
COST_MAX_US = 100.0                   # one analogWrite() call

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SUMMARY_PATH = REPO_ROOT / "results" / "diagnostics" / "pwm_loopback_summary.md"

HELPER = r'''
import json, sys, time
from arduino.app_utils import Bridge

def call(method, *args, retries=5, delay=0.5):
    last = None
    for _ in range(retries):
        try:
            return Bridge.call(method, *args)
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last

def wait_idle(timeout_s):
    t_end = time.time() + timeout_s
    while time.time() < t_end:
        try:
            if int(call("get_state", 0, retries=1)) == 0:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False

def fetch_chunks(method, total):
    rows, off = [], 0
    while off < total:
        s = str(call(method, off))
        items = [x for x in s.split(";") if x]
        if not items:
            break
        rows.extend(items)
        off += len(items)
    return rows

act = sys.argv[1]
out = {}
if act == "dwt":
    out["dwt_50us_cyc"] = int(call("check_dwt_status", 0))
elif act == "capture":
    permille, secs = int(sys.argv[2]), int(sys.argv[3])
    r = int(call("start_capture", permille, secs))
    if r != 1:
        out["error"] = "start_capture returned %d" % r
    else:
        time.sleep(secs + 1)
        if not wait_idle(60):
            out["error"] = "timeout waiting for capture to finish"
        else:
            summ = str(call("get_capture_summary", 0))
            out["summary"] = summ
            out["raw"] = fetch_chunks("get_raw_chunk", int(summ.split(",")[-1]))
elif act == "switch":
    n = int(sys.argv[2])
    r = int(call("start_switch", n))
    if r != 1:
        out["error"] = "start_switch returned %d" % r
    else:
        time.sleep(n * 0.035 + 1)
        if not wait_idle(120):
            out["error"] = "timeout waiting for switch test to finish"
        else:
            info = str(call("get_switch_info", 0))
            out["info"] = info
            out["rows"] = fetch_chunks("get_switch_chunk", int(info.split(",")[0]))
            summ = str(call("get_capture_summary", 0))
            out["summary"] = summ
            out["raw"] = fetch_chunks("get_raw_chunk", int(summ.split(",")[-1]))
print("RESULT " + json.dumps(out))
'''

SUMMARY_FIELDS = ["edges", "level_errors", "np", "pmin", "pmax", "psum_hi", "psum_lo", "pout",
                  "nh", "hmin", "hmax", "hsum_hi", "hsum_lo", "raw_n"]


# ---------------------------------------------------------------- board access
def run_adb(serial, args, timeout=900):
    res = subprocess.run([ADB, "-s", serial, *args], capture_output=True, text=True, timeout=timeout)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def find_container(serial):
    _, out, _ = run_adb(serial, ["shell", "docker ps --format '{{.Names}}'"])
    names = [n for n in out.splitlines() if CONTAINER_PATTERN in n]
    return names[0] if names else None


def push_helper(serial):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, newline="\n", encoding="utf-8") as f:
        f.write(HELPER.lstrip())
        local = f.name
    rc, out, err = run_adb(serial, ["push", local, REMOTE_HELPER])
    Path(local).unlink(missing_ok=True)
    if rc != 0:
        sys.exit(f"[FAIL] adb push of helper failed: {err or out}")


def helper(serial, container, *args, timeout=900):
    cmd = f"docker exec -i {container} python3 - {' '.join(str(a) for a in args)} < {REMOTE_HELPER}"
    rc, out, err = run_adb(serial, ["shell", cmd], timeout=timeout)
    for line in reversed(out.splitlines()):
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT "):])
    sys.exit(f"[FAIL] helper '{args[0]}' gave no result (rc={rc}).\nstdout tail: {out[-800:]}\nstderr: {err[-800:]}")


# ---------------------------------------------------------------- files
def write_capture_csv(path, target, seconds, summary, raw):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# target_permille: {target}\n# seconds: {seconds}\n")
        f.write(f"# summary_fields: {','.join(SUMMARY_FIELDS)}\n# summary: {summary}\n")
        f.write("edge_idx,t_cyc,level\n")
        for i, item in enumerate(raw):
            t, lvl = item.split(",")
            f.write(f"{i},{t},{lvl}\n")


def write_switch_csv(path, info, summary, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# info_fields: n_done,timeouts\n# info: {info}\n")
        f.write(f"# summary_fields: {','.join(SUMMARY_FIELDS)}\n# summary: {summary}\n")
        f.write("i,target_permille,call_cyc,cost_cyc,rise_cyc,fall_cyc,high_cyc\n")
        for i, item in enumerate(rows):
            f.write(f"{i},{item}\n")


def write_edges_csv(path, raw):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("edge_idx,t_cyc,level\n")
        for i, item in enumerate(raw):
            t, lvl = item.split(",")
            f.write(f"{i},{t},{lvl}\n")


def read_comments(path):
    meta = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                break
            k, _, v = line[1:].partition(":")
            meta[k.strip()] = v.strip()
    return meta


def read_rows(path):
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    header = lines[0].split(",")
    return [dict(zip(header, (int(x) for x in ln.split(",")))) for ln in lines[1:]]


# ---------------------------------------------------------------- analysis
def parse_summary(s):
    v = dict(zip(SUMMARY_FIELDS, (int(x) for x in s.split(","))))
    v["psum"] = (v["psum_hi"] << 32) | v["psum_lo"]
    v["hsum"] = (v["hsum_hi"] << 32) | v["hsum_lo"]
    return v


def signed_diff(a, b):
    """a - b for 32-bit DWT counts, as a signed number of cycles."""
    return ((a - b + 2**31) % 2**32) - 2**31


def eval_capture(target, seconds, summary):
    s = parse_summary(summary)
    res = {"target": target, "seconds": seconds, **s}
    if s["np"] == 0 or s["nh"] == 0:
        res.update(period_mean_us=float("nan"), duty=float("nan"), pass_=False,
                   reasons=["no edges captured (PWM not running, wrong pin or wire missing)"])
        return res
    pmean = s["psum"] / s["np"]
    hmean = s["hsum"] / s["nh"]
    duty = hmean / pmean
    expected = seconds * CLOCK_HZ / NOMINAL_PERIOD_CYC
    res.update(period_mean_us=pmean / CYC_PER_US, period_min_us=s["pmin"] / CYC_PER_US,
               period_max_us=s["pmax"] / CYC_PER_US, high_min_us=s["hmin"] / CYC_PER_US,
               high_max_us=s["hmax"] / CYC_PER_US, duty=duty, expected_periods=expected)
    reasons = []
    if abs(pmean - NOMINAL_PERIOD_CYC) > PERIOD_TOL_REL * NOMINAL_PERIOD_CYC:
        reasons.append(f"mean period {pmean / CYC_PER_US:.3f} us is not 2000 us +-0.1 %")
    if abs(duty - target / 1000) > DUTY_TOL:
        reasons.append(f"duty {duty * 100:.2f} % is not {target / 10:.1f} % +-0.5")
    if s["level_errors"]:
        reasons.append(f"{s['level_errors']} level repeats (missed edges)")
    if s["pout"]:
        reasons.append(f"{s['pout']} periods outside +-1 % (missed or extra edges)")
    if s["np"] < MIN_PERIOD_FRACTION * expected:
        reasons.append(f"only {s['np']} of ~{expected:.0f} expected periods")
    res["pass_"] = not reasons
    res["reasons"] = reasons
    return res


def eval_switch(info, rows):
    n_done, timeouts = (int(x) for x in info.split(","))
    ok = [r for r in rows if r["fall_cyc"] != 0]
    start_us = [signed_diff(r["rise_cyc"], r["call_cyc"]) / CYC_PER_US for r in ok]
    seen_us = [signed_diff(r["fall_cyc"], r["call_cyc"]) / CYC_PER_US for r in ok]
    cost_us = [r["cost_cyc"] / CYC_PER_US for r in rows]
    duty_err = [abs(r["high_cyc"] / NOMINAL_PERIOD_CYC - r["target_permille"] / 1000) for r in ok]
    transitional = sum(1 for e in duty_err if e > DUTY_TOL)
    res = {"n_done": n_done, "timeouts": timeouts, "n_ok": len(ok), "transitional": transitional}

    def stats(v):
        if not v:
            return {"min": float("nan"), "median": float("nan"), "max": float("nan")}
        return {"min": min(v), "median": statistics.median(v), "max": max(v)}

    res["start_us"], res["seen_us"], res["cost_us"] = stats(start_us), stats(seen_us), stats(cost_us)
    reasons = []
    if timeouts or len(ok) < n_done:
        reasons.append(f"{n_done - len(ok)} switches never showed the new duty within 20 ms")
    if start_us and max(start_us) > SWITCH_START_MAX_US:
        reasons.append(f"first new period started up to {max(start_us):.1f} us after the call (> 2000 us)")
    if cost_us and max(cost_us) > COST_MAX_US:
        reasons.append(f"analogWrite() took up to {max(cost_us):.1f} us (> 100 us)")
    res["pass_"] = not reasons
    res["reasons"] = reasons
    return res


def summarize(raw_dir, summary_path=SUMMARY_PATH):
    raw_dir = Path(raw_dir)
    summary_path = Path(summary_path)
    meta = read_comments(raw_dir / "meta.txt") if (raw_dir / "meta.txt").exists() else {}
    caps = []
    for d in DUTIES:
        p = raw_dir / f"capture_{d}.csv"
        c = read_comments(p)
        caps.append(eval_capture(d, int(c["seconds"]), c["summary"]))
    sw_meta = read_comments(raw_dir / "switch.csv")
    sw = eval_switch(sw_meta["info"], read_rows(raw_dir / "switch.csv"))

    rel = raw_dir.resolve().relative_to(REPO_ROOT).as_posix() if raw_dir.resolve().is_relative_to(REPO_ROOT) else str(raw_dir)
    L = ["# PWM loopback diagnostic (Phase 6b test 1)", "",
         f"- Raw data: `{rel}`",
         f"- Date: {meta.get('date', 'n/a')}; board role: {meta.get('board_role', 'n/a')}; core: arduino:zephyr {meta.get('core', 'n/a')}",
         "- Setup: one jumper D3 (PWM out, TIM3_CH3, 500 Hz) -> D8 (input, EXTI4) on the same board; DWT timestamps at 160 MHz.",
         f"- Pass criteria (fixed before the run): mean period 2000 us +-0.1 %; duty +-0.5 points; 0 missed edges; >= 99 % of expected periods; first new period starts <= {SWITCH_START_MAX_US:.0f} us after analogWrite(); analogWrite() <= {COST_MAX_US:.0f} us.",
         "", "## Steady captures", "",
         "| Target duty | Periods (expected) | Mean period (us) | Period min-max (us) | Duty (%) | High min-max (us) | Level repeats | Period outliers | Result |",
         "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"]
    for c in caps:
        if c["np"] == 0:
            L.append(f"| {c['target'] / 10:.1f} % | 0 | - | - | - | - | - | - | **FAIL** |")
            continue
        L.append(f"| {c['target'] / 10:.1f} % | {c['np']} ({c['expected_periods']:.0f}) | {c['period_mean_us']:.3f} | "
                 f"{c['period_min_us']:.3f}-{c['period_max_us']:.3f} | {c['duty'] * 100:.3f} | "
                 f"{c['high_min_us']:.3f}-{c['high_max_us']:.3f} | {c['level_errors']} | {c['pout']} | "
                 f"{'PASS' if c['pass_'] else '**FAIL**'} |")
    L += ["", "## Switch test", "",
          f"- Switches: {sw['n_done']} (alternating 80 % <-> 48 %, random phase), detected: {sw['n_ok']}, timeouts: {sw['timeouts']}",
          f"- First period with the new duty starts after the call (us): min {sw['start_us']['min']:.1f}, median {sw['start_us']['median']:.1f}, max {sw['start_us']['max']:.1f}"
          " (negative = the period that was already running changed)",
          f"- New duty visible (its falling edge) after the call (us): min {sw['seen_us']['min']:.1f}, median {sw['seen_us']['median']:.1f}, max {sw['seen_us']['max']:.1f}",
          f"- analogWrite() duration (us): min {sw['cost_us']['min']:.2f}, median {sw['cost_us']['median']:.2f}, max {sw['cost_us']['max']:.2f}",
          f"- Detected periods whose duty is off the target by > 0.5 points (transitional periods): {sw['transitional']}",
          f"- Result: {'PASS' if sw['pass_'] else '**FAIL**'}", ""]
    reasons = [f"capture {c['target'] / 10:.0f} %: {r}" for c in caps for r in c["reasons"]] + \
              [f"switch test: {r}" for r in sw["reasons"]]
    overall = all(c["pass_"] for c in caps) and sw["pass_"]
    L += ["## Overall", "", f"**{'PASS' if overall else 'FAIL'}**", ""]
    L += [f"- {r}" for r in reasons]
    text = "\n".join(L).rstrip() + "\n"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"[OK] Summary written to {summary_path}")
    return overall


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serial", help="adb serial of board 3 (not written to any file)")
    ap.add_argument("--seconds", type=int, default=100, help="seconds per steady capture (default 100)")
    ap.add_argument("--switches", type=int, default=200, help="number of duty switches (default 200, max 512)")
    ap.add_argument("--core", default="1.0.0", help="arduino:zephyr core version on board 3 (recorded in meta.txt)")
    ap.add_argument("--out", default=None, help="raw output folder (default results/raw/pwm_loopback_<date>)")
    ap.add_argument("--from-raw", default=None, help="recompute the summary from a saved raw folder (no hardware)")
    ap.add_argument("--summary", default=str(SUMMARY_PATH), help="summary output path (default results/diagnostics/pwm_loopback_summary.md)")
    args = ap.parse_args()

    if args.from_raw:
        sys.exit(0 if summarize(args.from_raw, args.summary) else 1)
    if not args.serial:
        sys.exit("--serial is required for a live run")

    date = datetime.date.today().isoformat()
    out_dir = Path(args.out) if args.out else REPO_ROOT / "results" / "raw" / f"pwm_loopback_{date}"
    if out_dir.exists() and any(out_dir.iterdir()):
        sys.exit(f"[FAIL] {out_dir} already has files; refusing to overwrite raw data. Use --out.")

    container = find_container(args.serial)
    if not container:
        sys.exit(f"[FAIL] no running container matching '{CONTAINER_PATTERN}' on the board. Start the pwm_loopback app first.")
    print(f"[..] container: {container}")
    push_helper(args.serial)

    dwt = helper(args.serial, container, "dwt", timeout=120)
    print(f"[..] DWT check: {dwt}")
    if not (7000 <= int(dwt.get("dwt_50us_cyc", -1)) <= 9000):
        sys.exit("[FAIL] DWT check outside 7000-9000 cycles per 50 us")

    results = {}
    for d in DUTIES:
        print(f"[..] steady capture {d / 10:.1f} % for {args.seconds} s ...")
        r = helper(args.serial, container, "capture", d, args.seconds)
        if "error" in r:
            sys.exit(f"[FAIL] capture {d}: {r['error']}")
        results[d] = r
        print(f"     summary: {r['summary']}  raw edges: {len(r['raw'])}")

    print(f"[..] switch test, {args.switches} switches ...")
    sw = helper(args.serial, container, "switch", args.switches)
    if "error" in sw:
        sys.exit(f"[FAIL] switch: {sw['error']}")
    print(f"     info: {sw['info']}  rows: {len(sw['rows'])}")

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "meta.txt", "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# date: {datetime.datetime.now().isoformat(timespec='seconds')}\n")
        f.write("# board_role: board3 (pwm loopback, D3 -> D8 jumper)\n")
        f.write(f"# core: {args.core}\n# container: {container}\n")
        f.write(f"# seconds: {args.seconds}\n# switches: {args.switches}\n")
    for d in DUTIES:
        write_capture_csv(out_dir / f"capture_{d}.csv", d, args.seconds, results[d]["summary"], results[d]["raw"])
    write_switch_csv(out_dir / "switch.csv", sw["info"], sw["summary"], sw["rows"])
    write_edges_csv(out_dir / "switch_edges.csv", sw["raw"])
    print(f"[OK] raw files in {out_dir}")
    sys.exit(0 if summarize(out_dir, args.summary) else 1)


if __name__ == "__main__":
    main()
