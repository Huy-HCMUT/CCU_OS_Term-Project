#!/usr/bin/env bash
#
# run_benchmark_5d.sh - Phase 5d Linux Benchmark Harness (A, B, and isolated B)
#
# Runs 12 conditions (A, B, and B-iso across 0%, core0-50%, core0-100%, all-core)
# into results/raw/linux_r<REP>/, logging Linux load/frequency/temperature samples
# and restoring CPU governors and IRQ affinities on exit.
#
# Usage: bash benchmarks/run_benchmark_5d.sh <REP> [CYCLES]
#

set -euo pipefail

if [ "$#" -lt 1 ] || ! [[ "$1" =~ ^[1-9][0-9]*$ ]]; then
    echo "Usage: $0 <REP>=integer>=1 [CYCLES=10000]" >&2
    exit 1
fi

REP="$1"
CYCLES="${2:-10000}"
if ! [[ "${CYCLES}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: CYCLES must be a positive integer, got '${CYCLES}'" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BIN_PATH="${ROOT_DIR}/mpu_linux/build/dual_thread_bench"
RAW_OUT_DIR="${ROOT_DIR}/results/raw/linux_r${REP}"
DATA_BIN="${ROOT_DIR}/data/processed/cwru_test_frames.bin"

if [ -d "${RAW_OUT_DIR}" ] && compgen -G "${RAW_OUT_DIR}/[AB]_*.csv" >/dev/null; then
    echo "ERROR: refusing to overwrite existing [AB]_*.csv files in ${RAW_OUT_DIR}" >&2
    exit 1
fi

mkdir -p "${RAW_OUT_DIR}"

if [ ! -f "${BIN_PATH}" ] || \
   [ "${ROOT_DIR}/mpu_linux/workload/dual_thread_bench.c" -nt "${BIN_PATH}" ] || \
   [ "${ROOT_DIR}/mpu_linux/workload/fft_math.c" -nt "${BIN_PATH}" ] || \
   [ "${ROOT_DIR}/mpu_linux/workload/fft_math.h" -nt "${BIN_PATH}" ]; then
    echo "[Build] Compiling dual_thread_bench binary..."
    make -C "${ROOT_DIR}/mpu_linux"
fi

declare -A SAVED_GOVS
for g in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    if [ -r "${g}" ]; then
        SAVED_GOVS["${g}"]="$(cat "${g}" 2>/dev/null || true)"
    fi
done

declare -A SAVED_IRQS
for irq_file in /proc/irq/*/smp_affinity_list; do
    if [ -r "${irq_file}" ]; then
        SAVED_IRQS["${irq_file}"]="$(cat "${irq_file}" 2>/dev/null || true)"
    fi
done

IRQS_MODIFIED=0
GOVS_MODIFIED=0

kill_stress() {
    sudo pkill -9 stress-ng 2>/dev/null || true
}

restore_irqs() {
    local irq_file
    for irq_file in "${!SAVED_IRQS[@]}"; do
        if [ -e "${irq_file}" ] && [ -n "${SAVED_IRQS[${irq_file}]}" ]; then
            printf '%s\n' "${SAVED_IRQS[${irq_file}]}" | sudo tee "${irq_file}" >/dev/null 2>&1 || true
        fi
    done
    IRQS_MODIFIED=0
}

restore_governors() {
    local g
    for g in "${!SAVED_GOVS[@]}"; do
        if [ -e "${g}" ] && [ -n "${SAVED_GOVS[${g}]}" ]; then
            printf '%s\n' "${SAVED_GOVS[${g}]}" | sudo tee "${g}" >/dev/null 2>&1 || true
        fi
    done
    GOVS_MODIFIED=0
}

cleanup() {
    set +e
    kill_stress
    if [ "${IRQS_MODIFIED}" -eq 1 ]; then
        echo "[Cleanup] Restoring IRQ affinities..."
        restore_irqs
    fi
    if [ "${GOVS_MODIFIED}" -eq 1 ]; then
        echo "[Cleanup] Restoring CPU frequency governors..."
        restore_governors
    fi
}
trap cleanup EXIT
trap 'echo "[Abort] Interrupted - cleaning up and stopping."; exit 130' INT TERM

echo "======================================================================"
echo " CCU OS Term Project: Phase 5d Linux Benchmark Harness (Rep ${REP})"
echo " Cycles per run: ${CYCLES} ($(( CYCLES / 100 )) s)"
echo " Output dir:     ${RAW_OUT_DIR}"
echo "======================================================================"

echo "[Governor] Setting all cores to 'performance' (saving previous governors)..."
for g in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    if [ -e "${g}" ]; then
        echo performance | sudo tee "${g}" >/dev/null || true
    fi
done
GOVS_MODIFIED=1
echo "[Governor] Current CPU0 Frequency: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 'N/A') kHz"

sample_env() {
    local out_file="$1"
    local label="$2"
    local ts procs s1 s2 busy_str loadavg gov freq temp_max

    ts="$(date +%Y-%m-%dT%H:%M:%S)"
    procs="$(pgrep -c stress-ng 2>/dev/null || true)"
    procs="${procs:-0}"

    s1="$(grep '^cpu' /proc/stat)"
    sleep 1
    s2="$(grep '^cpu' /proc/stat)"

    busy_str="$(
        {
            printf '%s\n' "${s1}"
            echo "---"
            printf '%s\n' "${s2}"
        } | awk '
        /^---$/ { phase = 2; next }
        phase != 2 {
            for (i = 2; i <= 9; i++) a[$1, i] = $i + 0
            next
        }
        {
            tot = 0
            for (i = 2; i <= 9; i++) {
                d[i] = ($i + 0) - a[$1, i]
                tot += d[i]
            }
            idle = d[5] + d[6]
            if (tot > 0) {
                pct = 100.0 * (tot - idle) / tot
                out = out (out ? " " : "") sprintf("busy_%s=%.1f", $1, pct)
            } else {
                out = out (out ? " " : "") sprintf("busy_%s=nan", $1)
            }
        }
        END { print out }
        '
    )"

    loadavg="$(awk '{printf "%s/%s/%s", $1, $2, $3}' /proc/loadavg)"
    # cat first, then paste: "paste -s" with several files prints one line per file.
    gov="$(cat /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor 2>/dev/null | paste -sd, - || true)"
    freq="$(cat /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_cur_freq 2>/dev/null | paste -sd, - || true)"
    temp_max="$(awk 'BEGIN { max = -1 } /^[0-9]+$/ { if ($1 + 0 > max) max = $1 + 0 } END { if (max >= 0) printf "%.1f", max / 1000.0 }' /sys/class/thermal/thermal_zone*/temp 2>/dev/null || true)"

    echo "sample=${label} time=${ts} stress_ng_procs=${procs} ${busy_str} loadavg=${loadavg} governor=${gov} cur_freq_khz=${freq} temp_max_c=${temp_max}" >> "${out_file}"
}

run_one() {
    local name="$1"
    local stress_kind="$2"
    local use_sudo="$3"
    shift 3

    local csv_file="${RAW_OUT_DIR}/${name}.csv"
    local env_file="${RAW_OUT_DIR}/env_${name}.txt"
    local stress_val=0
    local stress_pid=""
    local mid_pid=""
    local mid_delay=50

    if [ "${CYCLES}" -ne 10000 ]; then
        mid_delay=$(( CYCLES / 200 ))
        if [ "${mid_delay}" -lt 1 ]; then
            mid_delay=1
        fi
    fi

    echo ""
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
    echo " RUNNING: ${name} | stress_kind=${stress_kind}"
    echo " Target Output: ${csv_file}"
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"

    kill_stress
    sleep 1

    case "${stress_kind}" in
        none)
            stress_val=0
            ;;
        core0_50)
            stress_val=50
            stress-ng --cpu 1 --taskset 0 --hdd 1 --vm 1 --vm-bytes 25% --quiet &
            stress_pid=$!
            ;;
        core0_100)
            stress_val=100
            stress-ng --cpu 2 --taskset 0 --cache 2 --hdd 1 --vm 1 --vm-bytes 50% --quiet &
            stress_pid=$!
            ;;
        allcore)
            stress_val=100
            stress-ng --cpu 4 --cache 2 --hdd 1 --vm 1 --vm-bytes 50% --quiet &
            stress_pid=$!
            ;;
        allcore_iso)
            stress_val=100
            stress-ng --cpu 3 --taskset 0-2 --cache 2 --hdd 1 --vm 1 --vm-bytes 50% --quiet &
            stress_pid=$!
            ;;
        *)
            echo "ERROR: unknown stress_kind '${stress_kind}'" >&2
            exit 1
            ;;
    esac

    sleep 3
    sample_env "${env_file}" "start"

    if [ "${stress_kind}" != "none" ]; then
        local n_procs
        n_procs="$(pgrep -c stress-ng 2>/dev/null || true)"
        n_procs="${n_procs:-0}"
        if [ "${n_procs}" -eq 0 ]; then
            echo "ERROR: stress-ng failed to start for ${name} (${stress_kind})" >&2
            exit 1
        fi
    fi

    (
        sleep "${mid_delay}"
        sample_env "${env_file}" "mid"
    ) &
    mid_pid=$!

    if [ "${use_sudo}" = "sudo" ]; then
        sudo "${BIN_PATH}" "$@" --cycles "${CYCLES}" --stress "${stress_val}" --out "${csv_file}" --data "${DATA_BIN}"
    else
        "${BIN_PATH}" "$@" --cycles "${CYCLES}" --stress "${stress_val}" --out "${csv_file}" --data "${DATA_BIN}"
    fi

    wait "${mid_pid}" || true

    if [ -n "${stress_pid}" ] || [ "${stress_kind}" != "none" ]; then
        kill_stress
    fi
    sleep 5
}

# 1-4: Config A
run_one "A_0"           "none"      "nosudo" --config A
run_one "A_50"          "core0_50"  "nosudo" --config A --affinity 0
run_one "A_100"         "core0_100" "nosudo" --config A --affinity 0
run_one "A_100_allcore" "allcore"   "nosudo" --config A

# 5-8: Config B
run_one "B_0"           "none"      "sudo" --config B --policy FIFO --priority 90 --mlock
run_one "B_50"          "core0_50"  "sudo" --config B --policy FIFO --priority 90 --mlock --affinity 0
run_one "B_100"         "core0_100" "sudo" --config B --policy FIFO --priority 90 --mlock --affinity 0
run_one "B_100_allcore" "allcore"   "sudo" --config B --policy FIFO --priority 90 --mlock

# 9-12: Config B isolated (CPU 3 for control, CPU 2 for analytics, IRQs moved to 0-2, C-states off)
echo ""
echo "[IRQ] Moving IRQ affinities to cores 0-2..."
IRQS_MODIFIED=1
irq_total=0
irq_moved=0
for irq_file in /proc/irq/*/smp_affinity_list; do
    if [ -e "${irq_file}" ]; then
        irq_total=$(( irq_total + 1 ))
        if echo "0-2" | sudo tee "${irq_file}" >/dev/null 2>&1; then
            irq_moved=$(( irq_moved + 1 ))
        fi
    fi
done
echo "[IRQ] Moved ${irq_moved} of ${irq_total} IRQ affinity entries to 0-2"
echo "# irqs_moved=${irq_moved} of ${irq_total}" > "${RAW_OUT_DIR}/env_B_0_iso.txt"

run_one "B_0_iso"           "none"        "sudo" --config B --policy FIFO --priority 90 --mlock --affinity 3 --analytics-affinity 2 --no-cstates
run_one "B_50_iso"          "core0_50"    "sudo" --config B --policy FIFO --priority 90 --mlock --affinity 3 --analytics-affinity 2 --no-cstates
run_one "B_100_iso"         "core0_100"   "sudo" --config B --policy FIFO --priority 90 --mlock --affinity 3 --analytics-affinity 2 --no-cstates
run_one "B_100_iso_allcore" "allcore_iso" "sudo" --config B --policy FIFO --priority 90 --mlock --affinity 3 --analytics-affinity 2 --no-cstates

echo "[IRQ] Restoring saved IRQ affinities..."
restore_irqs

echo ""
echo "======================================================================"
echo " PHASE 5d LINUX BENCHMARK REP ${REP} COMPLETED!"
echo "======================================================================"
ls -lh "${RAW_OUT_DIR}"/[AB]_*.csv

