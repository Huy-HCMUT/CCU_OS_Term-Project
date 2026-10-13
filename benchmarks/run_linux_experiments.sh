#!/usr/bin/env bash
#
# run_linux_experiments.sh - Automated Linux Benchmark Runner (Configs A & B)
# Course: CCU Operating Systems (Fall 2026) - Term Project
# Author: Quang-Huy Nguyen (Lead) & Akash / An-Rui Peng
#
# Executes the 6 Linux baseline experimental matrices:
#   - Config A (CFS) at 0%, 50%, and 100% synthetic stress
#   - Config B (SCHED_FIFO 90) at 0%, 50%, and 100% synthetic stress
#
# Each test executes for 10,000 cycles (100 seconds) and outputs a raw CSV.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BIN_PATH="${ROOT_DIR}/mpu_linux/build/dual_thread_bench"
RAW_OUT_DIR="${ROOT_DIR}/results/raw"
CYCLES=${1:-10000}

mkdir -p "${RAW_OUT_DIR}"

# Build benchmark binary if not present
if [ ! -f "${BIN_PATH}" ]; then
    echo "[Build] Compiling benchmark binary..."
    make -C "${ROOT_DIR}/mpu_linux"
fi

echo "======================================================================"
echo " CCU OS Term Project: Linux Baseline Benchmark Harness"
echo " Configurations: Config A (CFS) vs Config B (SCHED_FIFO 90)"
echo " Cycles per run: ${CYCLES} (~$(( CYCLES / 100 )) seconds)"
echo " Output dir:     ${RAW_OUT_DIR}"
echo "======================================================================"

run_single_experiment() {
    local config=$1
    local stress=$2
    local csv_file="${RAW_OUT_DIR}/config_${config}_stress_${stress}.csv"
    local stress_pid=""

    echo ""
    echo "----------------------------------------------------------------------"
    echo " Starting: Config ${config} | Stress Level: ${stress}%"
    echo " Target CSV: ${csv_file}"
    echo "----------------------------------------------------------------------"

    # 1. Launch synthetic background stress if required
    if [ "${stress}" -eq 50 ]; then
        echo "[Stress] Launching 50% stress: --cpu 2 --io 1 --vm 1 --vm-bytes 25%"
        stress-ng --cpu 2 --io 1 --vm 1 --vm-bytes 25% --quiet &
        stress_pid=$!
        sleep 3
    elif [ "${stress}" -eq 100 ]; then
        echo "[Stress] Launching 100% stress: --cpu 4 --io 2 --vm 1 --vm-bytes 50%"
        stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 50% --quiet &
        stress_pid=$!
        sleep 3
    else
        echo "[Stress] Tier 0% (Idle baseline - no stress-ng)"
    fi

    # 2. Run benchmark
    if [ "${config}" = "B" ]; then
        echo "[Runner] Executing Config B with sudo (SCHED_FIFO 90)..."
        sudo "${BIN_PATH}" --config B --stress "${stress}" --cycles "${CYCLES}" \
             --out "${csv_file}" --data "${ROOT_DIR}/data/processed/cwru_test_frames.bin"
    else
        echo "[Runner] Executing Config A under standard Linux CFS..."
        "${BIN_PATH}" --config A --stress "${stress}" --cycles "${CYCLES}" \
             --out "${csv_file}" --data "${ROOT_DIR}/data/processed/cwru_test_frames.bin"
    fi

    # 3. Clean up stress background tasks
    if [ -n "${stress_pid}" ]; then
        echo "[Stress] Terminating stress-ng (PID ${stress_pid})..."
        kill -9 "${stress_pid}" 2>/dev/null || true
        wait "${stress_pid}" 2>/dev/null || true
    fi

    # Cool down period to avoid thermal throttling
    echo "[Cooldown] Cooling down CPU for 5 seconds..."
    sleep 5
}

# Execute Config A across 0%, 50%, 100%
run_single_experiment "A" 0
run_single_experiment "A" 50
run_single_experiment "A" 100

# Execute Config B across 0%, 50%, 100%
run_single_experiment "B" 0
run_single_experiment "B" 50
run_single_experiment "B" 100

echo ""
echo "======================================================================"
echo " All 6 Linux Baseline Benchmark Runs Completed Successfully!"
echo " Raw CSV logs stored in: ${RAW_OUT_DIR}"
echo "======================================================================"
ls -lh "${RAW_OUT_DIR}"
