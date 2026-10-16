#!/usr/bin/env bash
#
# run_benchmark.sh - Multi-Resource Industrial Benchmark Harness
# Course: CCU Operating Systems (Fall 2026) - Term Project
# Author: Quang-Huy Nguyen (Lead) & Akash / An-Rui Peng
#
# Combines all advanced industrial stressors (CPU saturation + Flash I/O +
# Virtual Memory pressure + Core 0 Affinity Contention) across 0%, 50%, and 100%
# stress tiers for Config A (CFS) vs Config B (SCHED_FIFO 90 + mlock).
# Telemetry outputs strictly follow the project naming convention: <Config>_<Stress>.csv
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BIN_PATH="${ROOT_DIR}/mpu_linux/build/dual_thread_bench"
RAW_OUT_DIR="${ROOT_DIR}/results/raw"
DATA_BIN="${ROOT_DIR}/data/processed/cwru_test_frames.bin"
CYCLES=${1:-2000}

mkdir -p "${RAW_OUT_DIR}"

if [ ! -f "${BIN_PATH}" ]; then
    echo "[Build] Compiling dual_thread_bench binary..."
    make -C "${ROOT_DIR}/mpu_linux"
fi

kill_stress() {
    sudo pkill -9 stress-ng 2>/dev/null || true
    sleep 2
}

echo "======================================================================"
echo " CCU OS Term Project: Industrial Benchmark Harness"
echo " Platform: Arduino UNO Q (Qualcomm Cortex-A53 Linux MPU)"
echo " Stress Tiers: 0% (Idle), 50% (Medium Composite), 100% (Maximum Storm)"
echo " Stress Vectors: CPU Contention + Flash I/O + VM Memory + Core 0 Pinning"
echo " Cycles per test: ${CYCLES} ($(( CYCLES / 100 )) seconds)"
echo "======================================================================"

echo "[Governor] Hardening CPU frequency: Locking all cores to 'performance' (2.016 GHz)..."
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    echo performance | sudo tee "$g" >/dev/null || true
done
echo "[Governor] Current CPU0 Frequency: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo 'N/A') kHz"


run_test() {
    local config=$1
    local stress=$2
    local csv_file="${RAW_OUT_DIR}/${config}_${stress}.csv"
    local stress_pid=""

    echo ""
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
    echo " RUNNING: Config ${config} | Stress Level: ${stress}%"
    echo " Target Output: ${csv_file}"
    echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
    kill_stress

    if [ "${stress}" -eq 0 ]; then
        echo "[Stress] Tier 0% (Idle Baseline - Normal Machine Operation)"
    elif [ "${stress}" -eq 50 ]; then
        echo "[Stress] Tier 50% (Medium Composite): 1 CPU (Core 0) + 1 HDD + 1 VM (25% RAM)"
        stress-ng --cpu 1 --taskset 0 --hdd 1 --vm 1 --vm-bytes 25% --quiet &
        stress_pid=$!
        sleep 3
    elif [ "${stress}" -eq 100 ]; then
        echo "[Stress] Tier 100% (Maximum Storm): 2 CPU (Core 0) + 2 Cache + 1 HDD + 1 VM (50% RAM)"
        stress-ng --cpu 2 --taskset 0 --cache 2 --hdd 1 --vm 1 --vm-bytes 50% --quiet &
        stress_pid=$!
        sleep 3
    fi

    if [ "${config}" = "B" ]; then
        echo "[Runner] Executing Config B (SCHED_FIFO 90 + mlockall + Core 0 Pinning)..."
        if [ "${stress}" -eq 0 ]; then
            # At 0%, run floating to establish baseline
            sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --mlock \
                 --stress "${stress}" --cycles "${CYCLES}" \
                 --out "${csv_file}" --data "${DATA_BIN}"
        else
            # At 50% and 100%, force single-core co-location on Core 0
            sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --mlock --affinity 0 \
                 --stress "${stress}" --cycles "${CYCLES}" \
                 --out "${csv_file}" --data "${DATA_BIN}"
        fi
    else
        echo "[Runner] Executing Config A (Standard Linux CFS)..."
        if [ "${stress}" -eq 0 ]; then
            "${BIN_PATH}" --config A --stress "${stress}" --cycles "${CYCLES}" \
                 --out "${csv_file}" --data "${DATA_BIN}"
        else
            "${BIN_PATH}" --config A --affinity 0 --stress "${stress}" --cycles "${CYCLES}" \
                 --out "${csv_file}" --data "${DATA_BIN}"
        fi
    fi

    if [ -n "${stress_pid}" ]; then
        echo "[Stress] Cleaning up background stress workers..."
        kill_stress
    fi

    echo "[Cooldown] Cooling down CPU for 5 seconds..."
    sleep 5
}

# 1. Execute Config A (CFS) across 0%, 50%, 100%
run_test "A" 0
run_test "A" 50
run_test "A" 100

# 2. Execute Config B (SCHED_FIFO 90 + mlock) across 0%, 50%, 100%
run_test "B" 0
run_test "B" 50
run_test "B" 100

echo ""
echo "======================================================================"
echo " BENCHMARK SUITE COMPLETED SUCCESSFULLY!"
echo " Raw telemetry CSVs stored in: ${RAW_OUT_DIR}"
echo "======================================================================"
ls -lh "${RAW_OUT_DIR}"/[AB]_*.csv
