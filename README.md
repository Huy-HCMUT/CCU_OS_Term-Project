# Real-Time Operating System Benchmarking on Heterogeneous Edge Controllers
### CCU Operating System (Fall 2026) — Term Project

---

## 🎯 Key Results

**Question:** can a 10 ms control loop keep its deadline while the same board runs heavy Linux work? **Answer:** on Linux, no; on the board's real-time MCU (Config C), yes. Compared over the same number of cycles (10,000-cycle blocks), its worst-case lateness is about 30× smaller than the best Linux setup (B) and about 600× smaller than default Linux (A).

![Worst-case lateness per 10,000-cycle block under realistic load](results/phase6b/block_wcl.png)

Under the heaviest realistic load (`rboth`: bulk network traffic and a containerised CNN at the same time; 2 repeats each):

| Where the 10 ms loop runs | Worst-case lateness | Cycles later than the 1 ms deadline |
| :--- | ---: | ---: |
| A: Linux, default scheduler | 8.4–10.7 ms | 2.4–4.7 % |
| B: Linux, `SCHED_FIFO` 90 + `mlockall` | 1.45–1.54 ms | 0.014–0.036 % |
| B-iso: B on a reserved core | 1.59–1.72 ms | 0.16–0.31 % |
| **C: MCU loop, setpoints from Linux** | **0.0076–0.0105 ms** | **0** |

- **Run lengths differ:** each Linux run is 180,000 cycles (30 min), each Config C run 10,000 cycles (100 s), and a longer run tends to catch a larger worst case. Per 10,000-cycle block, the typical worst case is A 5.57 ms, B 0.30 ms, B-iso 1.45 ms, C 0.009 ms (`Block WCL median` in `realload.md`). C's 0 misses rest on 20,000 cycles (2 runs).
- **Full chain:** all 1,920 speed commands of the 8 Config C runs reached the emulated motor drive, none lost or wrong; the drive saw each new command 1.47–4.11 ms after the tick (mostly the 500 Hz PWM itself).
- **Synthetic reference (`stress-ng` on all cores):** A 18.0–27.9 ms, Config C tuned IPC 0.0078 ms.
- Lateness is measured relative to each run's best cycle. Linux runs use a fixed 2.016 GHz CPU clock (`performance` governor); Config C runs keep the board's default setting (`schedutil`). Limits: stock Linux kernel (not `PREEMPT_RT`), one board, emulated drive instead of a motor.

Full tables: `results/phase6b/realload.md`, `results/phase6b/drive.md`, `results/phase5d/compare_configs.md`.

---

## 👥 Team Information

- **Course:** Operating System (Fall 2026)
- **Department:** Department of Computer Science & Information Engineering (CSIE)
- **Institution:** National Chung Cheng University (CCU)
- **Members:**
  - **Member 1:** Quang-Huy Nguyen (Student ID: 615461004)
  - **Member 2:** An-Rui Peng (Student ID: 614461008)

---

## 📄 Project Overview (Abstract)

Modern industrial Cyber-Physical Systems (CPS) are rapidly transitioning from **Predictive Maintenance (PdM)** to **Prescriptive Maintenance (PsM)**:
- **Predictive Maintenance (PdM)** focuses on open-loop health monitoring (e.g., analyzing vibration spectra to predict equipment faults). Because results are reviewed by human operators, it is tolerant to soft timing variations.
- **Prescriptive Maintenance (PsM)** closes the loop by triggering **automated real-time corrective actions** (e.g., dynamic motor deceleration, load shedding, lubrication control) within strict, millisecond-level deadlines to prevent mechanical failure.

This shift from open-loop monitoring to closed-loop actuation exposes a fundamental **Operating System dilemma**:
1. **General-Purpose Operating Systems (GPOS, e.g., Linux):** Provide rich runtime ecosystems required for signal processing (FFT) and machine learning inference, but their non-deterministic kernel mechanisms (CFS scheduling preemption, involuntary context switching, demand paging) can introduce unbounded latency spikes under heavy system load.
2. **Real-Time Operating Systems (RTOS, e.g., Zephyr):** Guarantee microsecond-level determinism and strict deadline compliance, but lack the compute throughput and software stack required for complex analytical workloads.

This project investigates this trade-off on the **Arduino UNO Q**, an Asymmetric Multi-Processing (AMP) hardware platform featuring both an application microprocessor (Linux MPU) and a real-time microcontroller (Zephyr MCU). By using a PsM workload as our benchmarking vehicle, we evaluate task scheduling behavior, memory contention effects, and inter-processor communication (IPC) latency to study how heterogeneous operating systems can reliably bridge the gap between heavy analytics and hard real-time control.

**Research question:** can a heterogeneous dual-OS split (Linux analytics + MCU real-time loop) keep a 10 ms control loop within its deadline under heavy Linux load, where Linux CFS and Linux `SCHED_FIFO` cannot?

---

## ⚙️ What Is Measured

Every configuration runs the **same minimal 10 ms control tick**; the analytics (Hann window + FFT on replayed bearing-vibration frames → speed setpoint) run separately, so only the OS behaviour differs.

| Config | Where the 10 ms tick runs | Timestamps |
| :--- | :--- | :--- |
| **A** | Linux thread, default scheduler (`SCHED_OTHER` / CFS) | `CLOCK_MONOTONIC` |
| **B** | Linux thread, `SCHED_FIFO` priority 90 + `mlockall` (variant **B-iso**: isolated core, IRQs and load moved to the other cores, C-states off) | `CLOCK_MONOTONIC` |
| **C** | MCU loop on the STM32 (Zephyr-based Arduino core); Linux sends setpoints over the RouterBridge IPC link ("latest value wins") | MCU DWT cycle counter + a second UNO Q as external referee timing the D2 pulse |

**Metrics:** lateness `L_k = t_k − R_k` against the absolute schedule `R_k = t0 + k · 10 ms`; deadline miss = `L_k > 1.0 ms` (0.2 ms as a secondary tier); worst-case lateness (WCL), p99.9, σ_L and deadline-miss rate (DMR). Definitions: `docs/Project_Scope_Statement.md` §4.3.

**Linux load:**
- **Controlled reference:** `stress-ng` at 0 / 50 / 100 %.
- **Realistic load (Phase 6):** `rnet` (bulk TCP traffic from a PC over Wi-Fi), `rdeploy` (a sensor stream into a containerised ONNX CNN analytics node) and `rboth` (both at once).

**Full chain (Phase 6b):** in Config C the MCU also outputs the speed command as a 500 Hz PWM signal to a third UNO Q that emulates the motor drive and records when each command arrives.

---

## 🧭 Key Design Decisions

Choices a reader might question, and why we made them:

1. **Same 10 ms tick everywhere, analytics kept separate.** Every config runs the same minimal control tick; the FFT analytics run in another thread or on the other processor. So differences come from the OS, not from different work.
2. **"Latest value wins" between Linux and the MCU.** Linux sends `(sequence, setpoint)`; an MCU handler only stores it in one 32-bit word, and the loop reads that word once per tick. The loop never waits for Linux, so a late message delays the *advice*, never the tick.
3. **An external referee board.** A second UNO Q timestamps the DUT's tick pulse with its own DWT cycle counter, so Config C is not judged only by its own clock. The first referee used Zephyr's `k_cycle_get_32()`, which loses cycles while the MCU sleeps; it was replaced and the baseline re-run.
4. **Stock and tuned MCU priorities, both reported.** Stock = library defaults (RouterBridge's `bridge` thread above the loop); tuned = the loop at priority 4, above it. Tuned removes most of the IPC cost.
5. **One lateness definition for all configs.** Lateness relative to each run's best cycle (`L_rel`); for Config C the constant clock offset is removed by fitting the period. Absolute Linux values are kept in the long CSV files.
6. **B-iso is isolation by affinity only.** Control thread on core 3, everything we start and the movable interrupts on cores 0–2, C-states off, but no `isolcpus` / `nohz_full` at boot. Under combined load the kernel's own work still reaches core 3 (see "Kernel work on CPU 3" in `results/phase6b/realload.md`).
7. **Realistic load is the main result, `stress-ng` the controlled reference.** The realistic tiers model a deployed edge controller: network traffic over Wi-Fi and a containerised 1D-CNN. The CNN has random weights on purpose: it is background load, not a fault classifier.
8. **An emulated drive instead of a motor.** A third UNO Q receives the speed command as 500 Hz PWM and records when each new command arrives. Part of the measured delay (waiting for the next PWM period) is fixed by the PWM itself, not by the OS.
9. **Repeats.** `stress-ng` tiers: 3 runs per Linux condition, 3–4 per Config C condition (1–2 for all-core). Realistic tiers: 2 runs each; the two `rboth` repeats ran in one session, so they show within-session spread only.

## 🔌 Hardware Setup

- **DUT:** Arduino UNO Q (Linux MPU: Qualcomm QRB2210, quad Cortex-A53, Debian 13, stock kernel 6.16 `PREEMPT`, **not** `PREEMPT_RT`; MCU: STM32U585 Cortex-M33 @ 160 MHz).
- **Referee:** a second UNO Q timestamping the DUT's D2 pulse with its own DWT counter.
- **Drive emulator (Phase 6b):** a third UNO Q reading the DUT's PWM output (DUT D3 → D8) and the tick (D2).
- **PC (Windows):** controls the boards over `adb`, generates the realistic network load, runs the analysis.
- **Wiring:** DUT D2 → referee D2 and drive D2; DUT D3 → drive D8; all GNDs joined.

---

## 📈 Status (November 2026)

| Phase | Content | Status |
| :--- | :--- | :--- |
| 2 | Configs A and B under `stress-ng` 0/50/100 % + Tests 1–5 (I/O, endurance, affinity, mlock, FIFO vs RR) | Done |
| 4.5 | Config C baseline: MCU timing under Linux stress, no IPC | Done |
| 5 / 5b–5d | Config C with IPC, tuned variant, repeats, fair three-way comparison | Done |
| 6a | Realistic load tiers `rnet` / `rdeploy` / `rboth` for A, B, B-iso (2 repeats) | Done |
| 6b | Full chain to an emulated drive (Config C `act`, 4 load tiers, 2 repeats) | Done |

**Milestones:** M3 presentation + demo on Dec 1, 2026; M4 final report (IEEE format, ≤ 15 pages) on Jan 5, 2027.

---

## 🗺️ Where to Find the Results

**Start here (headline results):**

| Question | File |
| :--- | :--- |
| A vs B vs B-iso vs C under synthetic `stress-ng` load (one lateness definition for all) | `results/phase5d/compare_configs.md` (+ `wcl_by_tier.png`, `cdf_100.png`, `cdf_allcore.png`) |
| The same configs under realistic load (`rnet`, `rdeploy`, `rboth`) | `results/phase6b/realload.md` (+ `block_wcl.png`, `cpu3_kernel_work.png`, `core_busy.png`) |
| Does every speed command reach the emulated drive, and how fast? | `results/phase6b/drive.md` |

**Every phase, from board run to result** (all paths relative to the repository root; the board scripts run on the UNO Q, the harness and analysis on the PC):

| Phase | What it tests | Run with | Raw data in `results/raw/` | Analysis (`benchmarks/analysis/` unless noted) | Results |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2 | A and B under `stress-ng` 0 / 50 / 100 % | `benchmarks/run_benchmark.sh` | `A_*.csv`, `B_*.csv` | `analyze_latency.py` | `results/summary.md`, `results/plots/lateness_*.png` |
| 2 (Tests 1–5) | I/O contention, 10,000-cycle endurance, core affinity, `mlockall`, FIFO vs RR | `benchmarks/run_advanced_experiments.sh` | `test1_*.csv` … `test5_*.csv` | `parse_advanced_metrics.py`, `plot_advanced_results.py` | `results/plots/test*.png` |
| 4.5 | Config C baseline: MCU loop under Linux stress, no IPC (first referee) | harness modes `sanity`, `0`, `50`, `100` | `C_*.csv`, `config_c_dwt_*.csv`, `config_c_referee_*.csv` | `analyze_latency.py`, `analyze_referee.py` | `results/summary.md` (C rows), `results/referee_p45.md` |
| Clock check | Why the MCU's Zephyr clock drifts against its DWT counter | `benchmarks/diagnostics/run_clock_check.py` | `clock_diagnostics_2026-10-19.csv` | same script | `results/clock_diagnostics_summary.md` |
| 5 | Config C with IPC (Linux setpoints over RouterBridge); baseline re-run with the DWT referee | harness `b2-*`, `ipc-*` | `baseline_dwtref/`, `ipc/` | `analyze_latency.py`, `analyze_referee.py`, `analyze_ipc.py`, `pulse_pattern.py`, `compare_baseline_ipc.py` | `results/baseline_dwtref/`, `results/ipc/` (`compare_baseline_vs_ipc.md`) |
| 5b / 5c | Repeats; tuned variant (MCU loop above the bridge thread); stock baseline repeat 4 | harness `b2-*`, `ipc-*`, `b2t-*`, `ipct-*` with `--rep N` | `*_r2/`, `*_r3/`, `baseline_dwtref_r4/`, `baseline_tuned*/`, `ipc_tuned*/` | the Phase 5 scripts + `aggregate_repeats.py`, `ipc_attribution.py` | `results/phase5b/`, one `results/<folder>/` per raw folder |
| 5d | Fair comparison of A, B, B-iso and C, incl. all-core stress | `benchmarks/run_benchmark_5d.sh`; harness `*-allcore` | `linux_r1/`–`linux_r3/`, `*_allcore*/` | `compare_configs.py` (+ `aggregate_repeats.py`, `ipc_attribution.py`) | **`results/phase5d/`**, `results/linux_r*/` |
| 6a | A, B, B-iso under realistic load (`rnet`, `rdeploy`, `rboth`) | `benchmarks/run_benchmark_6r.sh` + `benchmarks/realload/pc_traffic.py` | `real_r1/`, `real_r2/`, `real_calibration/` | `compare_realload.py` | **`results/phase6b/realload.md`** (Phase 6a and 6b are analysed together) |
| 6b | Full chain: Config C under the same loads, speed command as 500 Hz PWM to board 3 | harness `act-*`; PWM check `benchmarks/diagnostics/run_pwm_loopback.py` | `act_tuned*/`, `pwm_loopback_2026-11-17/` | `compare_realload.py`, `analyze_drive.py` | **`results/phase6b/`**, `results/diagnostics/pwm_loopback_summary.md` |

More detail: `results/README.md` (every results folder) and `benchmarks/analysis/README.md` (every analysis script).

## 🔤 Folder and File Names

| Name | Meaning |
| :--- | :--- |
| `A`, `B`, `B-iso` (`_iso`) | The Linux configs (see "What Is Measured"); `_iso` = B on an isolated core 3 (affinity only, no `isolcpus`). |
| `C`, `config_c_*` | Config C (MCU loop on the STM32). |
| `baseline` | Config C without IPC: the MCU loop runs, Linux sends nothing. |
| `ipc` | Config C with IPC: Linux analytics send setpoints to the MCU ("latest value wins"). |
| `dwtref`, `b2` | Runs timed by the second, DWT-based referee (Phase 5 on); `b2` is the harness name for the baseline variant. |
| `tuned`, `b2t`, `ipct` | The MCU loop runs at thread priority 4, above RouterBridge's `bridge` thread (5); "stock" = loop at 14, below it. |
| `act` | Tuned IPC plus the PWM speed command to the drive board (Phase 6b). |
| `0`, `50`, `100` | `stress-ng` load in %, on core 0. |
| `allcore` | `stress-ng` on all four cores. |
| `rnet`, `rdeploy`, `rboth` | Realistic load: bulk network traffic from the PC / a sensor stream into a containerised CNN / both at once. |
| `_r2`, `_r3`, … | Repeat number; no suffix = repeat 1. `real_r<N>` and `linux_r<N>` are the Linux repeats. |
| `sanity` | A 20-cycle wiring and readout check before each run; not analysed. |
| `p45` | Phase 4.5. |
| `L_rel`, WCL, DMR | Lateness relative to the run's best cycle, worst-case lateness, deadline-miss rate at 1 ms (see `results/phase5d/compare_configs.md`). |

---

## 📂 Repository Structure

```
CCU_OS_Term Project/
├── README.md
├── Operating System Term Project.pdf   # The course's assignment sheet
├── docs/                          # Scope statement, progress reports, submitted documents (see docs/README.md)
├── data/                          # CWRU download/slicing script; processed frames in data/processed/
├── mpu_linux/                     # Linux benchmark for Configs A/B (dual_thread_bench.c, FFT, Makefile)
├── benchmarks/
│   ├── run_benchmark*.sh          # Board-side harnesses (Phase 2, 5d, 6a realistic load)
│   ├── run_config_c_hardware_test.py  # PC-side orchestration of the Config C runs (all boards via adb)
│   ├── config_c_*/                # Arduino Apps for Config C (MCU sketch + Linux Python side)
│   ├── referee/                   # Referee board app
│   ├── drive_emu/                 # Drive emulator board app (Phase 6b)
│   ├── realload/                  # Realistic load: board controller, PC traffic sender, ONNX analytics node
│   ├── diagnostics/               # Clock and PWM loopback diagnostics
│   ├── analysis/                  # Analysis scripts + their tests
│   └── tests/                     # Harness tests (mocked boards)
├── results/
│   ├── raw/                       # Original measurements (read-only)
│   ├── phase5b/, phase5d/, phase6b/   # Cross-run summaries per phase (headline results)
│   ├── <raw folder name>/         # Per-run-set analysis (e.g. ipc_tuned_r2/), same name as in raw/
│   └── plots/                     # Phase 2 / 4.5 figures (see results/README.md)
├── paper_ieee/                    # IEEEtran report sources and presentation slides
└── unused/                        # Files no longer used (see unused/README.md)
```

---

## ▶️ How to Run

The C benchmark and the shell harnesses run **on the UNO Q's Linux side**; the analysis runs on the PC.

```bash
# On the board
make -C mpu_linux                                   # -> mpu_linux/build/dual_thread_bench
bash benchmarks/run_benchmark.sh [CYCLES]           # Phase 2: A/B under stress-ng 0/50/100 %
bash benchmarks/run_benchmark_6r.sh <rep> <rnet|rdeploy|rboth> <pc_ip>   # Phase 6a: A, B, B-iso under realistic load

# On the PC (boards on adb)
python benchmarks/run_config_c_hardware_test.py <mode> [--rep N] [--dut-ip IP --pc-ip IP]   # -h: help, no board contact
#   mode = sanity | 0 | 50 | 100 | all (baseline), or <variant>-<sub> with variant ipc / ipct / b2 / b2t / act
#   and sub = sanity | 0 | 50 | 100 | all | allcore | rnet | rdeploy | rboth (e.g. act-rnet)
python benchmarks/realload/pc_traffic.py <bulk|ingest> --host <dut_ip> --duration <s> --out <file>

# Analysis and tests (PC)
pip install -r benchmarks/analysis/requirements.txt
python benchmarks/analysis/analyze_latency.py --clock-hz 160e6     # -> results/summary.{csv,md}, results/plots/
python -m pytest -q benchmarks/tests benchmarks/realload/tests
cd benchmarks/analysis && python -m pytest -q
```

The hardware scripts drive real boards and start load generators; run them only on the test setup.

---

## 📊 Data

- **Workload input:** CWRU Bearing Data Center, 12 kHz drive-end, 0 HP (files 97, 105, 118, 130: normal, inner race, ball, outer race), replayed as 1024-sample frames. Downloaded by `data/download_and_slice_cwru.py`; the raw `.mat` files are not in the repository.
- **Measurements:** `results/raw/` holds the original timing data from the boards and is never edited; every reported number is produced by a script from these files.
