#!/usr/bin/env bash
#
# run_advanced_experiments.sh - Advanced Linux Real-Time Benchmark Harness
# Course: CCU Operating Systems (Fall 2026) - Term Project
# Author: Quang-Huy Nguyen (Lead) & Akash / An-Rui Peng
#
# Executes the 5 advanced empirical stress tests:
#   Test 1: Kernel I/O Contention (stress-ng --hdd 2 --sync-stream 2)
#   Test 2: Extended 10,000-Cycle Endurance (100 s continuous)
#   Test 3: CPU Affinity & Core Pinning (--affinity 0 vs floating)
#   Test 4: Virtual Memory Locking (--mlock vs default)
#   Test 5: RT Policy Comparison (SCHED_FIFO vs SCHED_RR)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BIN_PATH="${ROOT_DIR}/mpu_linux/build/dual_thread_bench"
RAW_OUT_DIR="${ROOT_DIR}/results/raw"
DATA_BIN="${ROOT_DIR}/data/processed/cwru_test_frames.bin"

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
echo " CCU OS Term Project: Advanced Empirical Benchmarking Harness"
echo " Board: Arduino UNO Q (Qualcomm Cortex-A53 quad-core Linux MPU)"
echo " Tests 1 through 5: I/O, Endurance, Affinity, Memory Lock, RT Policy"
echo "======================================================================"

# ====================================================================
# TEST 1: Kernel I/O Contention (Emergency Flash Dump Simulation)
# ====================================================================
echo ""
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
echo " RUNNING TEST 1: Kernel I/O & Storage Contention"
echo " Industrial Threat: Non-preemptible spinlocks during crash forensics"
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
kill_stress
echo "[Stress] Launching I/O pressure: --cpu 4 --hdd 2 --sync-file 2 --vm 1 --vm-bytes 50%"
stress-ng --cpu 4 --hdd 2 --sync-file 2 --vm 1 --vm-bytes 50% --quiet &
sleep 3

echo "[Test 1A] Config A (Linux CFS) under I/O Contention (2000 cycles)..."
"${BIN_PATH}" --config A --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test1_io_config_A.csv" --data "${DATA_BIN}"

echo "[Test 1B] Config B (SCHED_FIFO 90) under I/O Contention (2000 cycles)..."
sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test1_io_config_B.csv" --data "${DATA_BIN}"

kill_stress
echo "[Cooldown] Resting 5 seconds..."
sleep 5

# ====================================================================
# TEST 2: Extended 10,000-Cycle Endurance (100 Seconds Continuous)
# ====================================================================
echo ""
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
echo " RUNNING TEST 2: Extended 10,000-Cycle Endurance Benchmark"
echo " Industrial Threat: Periodic 30s kernel dirty writeback jitter"
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
kill_stress
echo "[Stress] Launching 100% compute stress: --cpu 4 --io 2 --vm 1 --vm-bytes 50%"
stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 50% --quiet &
sleep 3

echo "[Test 2] Config B (SCHED_FIFO 90) for 10,000 Continuous Cycles (~100 s)..."
sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --cycles 10000 --stress 100 \
    --out "${RAW_OUT_DIR}/test2_10000_cycles_config_B.csv" --data "${DATA_BIN}"

kill_stress
echo "[Cooldown] Resting 5 seconds..."
sleep 5

# ====================================================================
# TEST 3: CPU Affinity & Core Pinning Contention
# ====================================================================
echo ""
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
echo " RUNNING TEST 3: CPU Affinity Contention"
echo " Industrial Threat: L1 cache cold-start penalty vs single-core preemption"
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
kill_stress
echo "[Stress] Launching 100% compute stress: --cpu 4 --quiet"
stress-ng --cpu 4 --quiet &
sleep 3

echo "[Test 3A] Config B Floating Dynamically across all 4 Cores (2000 cycles)..."
sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test3_affinity_floating.csv" --data "${DATA_BIN}"

echo "[Test 3B] Config B Co-located strictly on Core 0 (--affinity 0) (2000 cycles)..."
sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --affinity 0 --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test3_affinity_pinned_core0.csv" --data "${DATA_BIN}"

kill_stress
echo "[Cooldown] Resting 5 seconds..."
sleep 5

# ====================================================================
# TEST 4: Virtual Memory Locking (mlockall vs Default)
# ====================================================================
echo ""
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
echo " RUNNING TEST 4: Virtual Memory Locking"
echo " Industrial Threat: Minor page faults from kswapd reclaiming dormant pages"
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
kill_stress
echo "[Stress] Launching aggressive VM memory stress: --vm 2 --vm-bytes 50% --vm-hang 5"
stress-ng --vm 2 --vm-bytes 50% --vm-hang 5 --quiet &
sleep 3

echo "[Test 4A] Config B Default (Without mlockall) (2000 cycles)..."
sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test4_memory_no_mlock.csv" --data "${DATA_BIN}"

echo "[Test 4B] Config B Memory-Locked (--mlock) (2000 cycles)..."
sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --mlock --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test4_memory_with_mlock.csv" --data "${DATA_BIN}"

kill_stress
echo "[Cooldown] Resting 5 seconds..."
sleep 5

# ====================================================================
# TEST 5: Real-Time Scheduling Policy Comparison (SCHED_FIFO vs SCHED_RR)
# ====================================================================
echo ""
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
echo " RUNNING TEST 5: Real-Time Scheduling Policy Comparison"
echo " Industrial Threat: Monopoly run-to-completion vs time-sliced fairness"
echo ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"
kill_stress
echo "[Stress] Launching heavy CPU stress: --cpu 4"
stress-ng --cpu 4 --quiet &
sleep 3

echo "[Test 5A] Config B under SCHED_FIFO (Priority 90) (2000 cycles)..."
sudo "${BIN_PATH}" --config B --policy FIFO --priority 90 --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test5_policy_sched_fifo.csv" --data "${DATA_BIN}"

echo "[Test 5B] Config B under SCHED_RR (Priority 90) (2000 cycles)..."
sudo "${BIN_PATH}" --config B --policy RR --priority 90 --cycles 2000 --stress 100 \
    --out "${RAW_OUT_DIR}/test5_policy_sched_rr.csv" --data "${DATA_BIN}"

kill_stress

echo ""
echo "======================================================================"
echo " ALL 5 ADVANCED BENCHMARK EXPERIMENTS COMPLETED!"
echo " Raw telemetry CSVs stored in: ${RAW_OUT_DIR}"
echo "======================================================================"
ls -lh "${RAW_OUT_DIR}"/test*.csv
