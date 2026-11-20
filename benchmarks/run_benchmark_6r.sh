#!/usr/bin/env bash
#
# run_benchmark_6r.sh - Phase 6a Linux Benchmark Harness (realistic loads R-net, R-deploy and R-both)
#
# Runs A, B, and isolated B for one realistic load tier into results/raw/real_r<REP>/,
# controlling board-side load via benchmarks/realload/realload.sh, logging Linux env and
# IRQ affinity metadata, and restoring governors, IRQs, and realload state on exit.
#
# Usage: bash benchmarks/run_benchmark_6r.sh <REP> <rnet|rdeploy|rboth> <PC_IP> [CYCLES=180000]
#

set -euo pipefail

if [ "$#" -lt 3 ] || ! [[ "$1" =~ ^[1-9][0-9]*$ ]]; then
    echo "Usage: $0 <REP>=integer>=1 <rnet|rdeploy|rboth> <PC_IP> [CYCLES=180000]" >&2
    exit 1
fi

REP="$1"
TIER="$2"
PC_IP="$3"
CYCLES="${4:-180000}"

if [ "${TIER}" != "rnet" ] && [ "${TIER}" != "rdeploy" ] && [ "${TIER}" != "rboth" ]; then
    echo "ERROR: tier must be 'rnet', 'rdeploy' or 'rboth', got '${TIER}'" >&2
    exit 1
fi

if ! [[ "${PC_IP}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "ERROR: PC_IP must be a dotted-quad IPv4 address, got '${PC_IP}'" >&2
    exit 1
fi
IFS='.' read -r o1 o2 o3 o4 <<< "${PC_IP}"
for oct in "${o1}" "${o2}" "${o3}" "${o4}"; do
    if [ "$((10#${oct}))" -gt 255 ]; then
        echo "ERROR: PC_IP octet out of range (0-255) in '${PC_IP}'" >&2
        exit 1
    fi
done

if ! [[ "${CYCLES}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: CYCLES must be a positive integer, got '${CYCLES}'" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BIN_PATH="${ROOT_DIR}/mpu_linux/build/dual_thread_bench"
RAW_OUT_DIR="${ROOT_DIR}/results/raw/real_r${REP}"
DATA_BIN="${ROOT_DIR}/data/processed/cwru_test_frames.bin"
REALLOAD_SH="${ROOT_DIR}/benchmarks/realload/realload.sh"

if [ -d "${RAW_OUT_DIR}" ] && compgen -G "${RAW_OUT_DIR}/[AB]_0*_${TIER}.csv" >/dev/null; then
    echo "ERROR: refusing to overwrite existing [AB]_0*_${TIER}.csv files in ${RAW_OUT_DIR}" >&2
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
    bash "${ROOT_DIR}/benchmarks/realload/realload.sh" stop || true
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
echo " CCU OS Term Project: Phase 6a Linux Benchmark Harness (Rep ${REP}, ${TIER})"
echo " Cycles per run: ${CYCLES} ($(( CYCLES / 100 )) s)"
echo " PC IP:          ${PC_IP}"
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
    gov="$(cat /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor 2>/dev/null | paste -sd, - || true)"
    freq="$(cat /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_cur_freq 2>/dev/null | paste -sd, - || true)"
    temp_max="$(awk 'BEGIN { max = -1 } /^[0-9]+$/ { if ($1 + 0 > max) max = $1 + 0 } END { if (max >= 0) printf "%.1f", max / 1000.0 }' /sys/class/thermal/thermal_zone*/temp 2>/dev/null || true)"

    echo "sample=${label} time=${ts} stress_ng_procs=${procs} ${busy_str} loadavg=${loadavg} governor=${gov} cur_freq_khz=${freq} temp_max_c=${temp_max}" >> "${out_file}"
}

run_real() {
    local name="$1"
    local iso_mode="$2"
    local use_sudo="$3"
    shift 3

    local csv_file="${RAW_OUT_DIR}/${name}.csv"
    local env_file="${RAW_OUT_DIR}/env_${name}.txt"
    local mid_delay=$(( CYCLES / 200 ))
    if [ "${mid_delay}" -lt 1 ]; then
        mid_delay=1
    fi

    echo ""
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
    echo " RUNNING: ${name} | tier=${TIER} | iso=${iso_mode}"
    echo " Target Output: ${csv_file}"
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"

    if [ "${iso_mode}" = "iso" ]; then
        bash "${REALLOAD_SH}" start "${TIER}" "${name}" "${RAW_OUT_DIR}" "${PC_IP}" "iso"
    else
        bash "${REALLOAD_SH}" start "${TIER}" "${name}" "${RAW_OUT_DIR}" "${PC_IP}"
    fi

    sleep 30

    local lc_rc=0
    local lc_line=""
    lc_line="$(bash "${REALLOAD_SH}" check "${TIER}")" || lc_rc=$?
    echo "# loadcheck start: ${lc_line}" >> "${env_file}"
    if [ "${lc_rc}" -ne 0 ]; then
        bash "${REALLOAD_SH}" stop || true
        echo "ERROR: load not present for ${name}. Are the pc_traffic.py sender(s) running on the PC?" >&2
        exit 1
    fi

    sample_env "${env_file}" "start"

    local mid_pid=""
    (
        sleep "${mid_delay}"
        sample_env "${env_file}" "mid"
        local mid_rc=0
        local mid_line=""
        mid_line="$(bash "${REALLOAD_SH}" check "${TIER}")" || mid_rc=$?
        echo "# loadcheck mid: ${mid_line}" >> "${env_file}"
        if [ "${mid_rc}" -ne 0 ]; then
            echo "WARNING: load check failed during ${name}; data kept, see env file"
        fi
    ) &
    mid_pid=$!

    if [ "${use_sudo}" = "sudo" ]; then
        sudo "${BIN_PATH}" "$@" --cycles "${CYCLES}" --stress 0 --out "${csv_file}" --data "${DATA_BIN}"
    else
        "${BIN_PATH}" "$@" --cycles "${CYCLES}" --stress 0 --out "${csv_file}" --data "${DATA_BIN}"
    fi

    wait "${mid_pid}" || true

    local end_rc=0
    local end_line=""
    end_line="$(bash "${REALLOAD_SH}" check "${TIER}")" || end_rc=$?
    echo "# loadcheck end: ${end_line}" >> "${env_file}"
    if [ "${end_rc}" -ne 0 ]; then
        echo "WARNING: load check failed during ${name}; data kept, see env file"
    fi

    bash "${REALLOAD_SH}" stop
    sleep 60
}

# 1: Config A
run_real "A_0_${TIER}" "noiso" "nosudo" --config A

# 2: Config B
run_real "B_0_${TIER}" "noiso" "sudo" --config B --policy FIFO --priority 90 --mlock

# 3: Config B isolated (CPU 3 for control, CPU 2 for analytics, IRQs moved to 0-2, C-states off)
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
echo "# irqs_moved=${irq_moved} of ${irq_total}" > "${RAW_OUT_DIR}/env_B_0_iso_${TIER}.txt"

while IFS= read -r irq_line; do
    irq_num="$(echo "${irq_line}" | awk -F: '{gsub(/^[ \t]+/, "", $1); print $1}')"
    if [[ "${irq_num}" =~ ^[0-9]+$ ]]; then
        eff=""
        if [ -r "/proc/irq/${irq_num}/effective_affinity_list" ]; then
            eff="$(cat "/proc/irq/${irq_num}/effective_affinity_list" 2>/dev/null || true)"
        elif [ -r "/proc/irq/${irq_num}/smp_affinity_list" ]; then
            eff="$(cat "/proc/irq/${irq_num}/smp_affinity_list" 2>/dev/null || true)"
        fi
        echo "# wifi_irq ${irq_num} effective=${eff}" >> "${RAW_OUT_DIR}/env_B_0_iso_${TIER}.txt"
    fi
done < <(grep -iE 'ath10k|wlan|wcn|wifi' /proc/interrupts 2>/dev/null || true)

run_real "B_0_iso_${TIER}" "iso" "sudo" --config B --policy FIFO --priority 90 --mlock --affinity 3 --analytics-affinity 2 --no-cstates

echo "[IRQ] Restoring saved IRQ affinities..."
restore_irqs

echo ""
echo "======================================================================"
echo " PHASE 6a LINUX REP ${REP} TIER ${TIER} COMPLETED!"
echo "======================================================================"
ls -lh "${RAW_OUT_DIR}"/[AB]_0*_"${TIER}".csv

