# Project Scope Statement
## Heterogeneous OS Benchmarking for Real-Time Edge Control on Asymmetric Hardware

- **Course:** Operating Systems (Fall 2026)
- **Institution:** National Chung Cheng University (CCU)
- **Document Version:** 2.4.0 (Pre-M2 Hardware-Verified Edition)
- **Document Status:** Active Execution (Milestone 1 Completed, M2 In-Progress)

---

## Table of Contents

- [1. Project Overview & Objectives](#1-project-overview--objectives)
  - [1.1 Background & Motivation](#11-background--motivation)
  - [1.2 The Operating System Problem](#12-the-operating-system-problem)
  - [1.3 Project Objectives](#13-project-objectives)
- [2. High-Level System Components](#2-high-level-system-components)
- [3. Technical Environment & Tools](#3-technical-environment--tools)
- [4. Scope Boundaries & Measurement Methodology](#4-scope-boundaries--measurement-methodology)
  - [4.1 In-Scope (What We Will Do)](#41-in-scope-what-we-will-do)
  - [4.2 Out-of-Scope (What We Will NOT Do)](#42-out-of-scope-what-we-will-not-do)
  - [4.3 Measurement Methodology: Workload-Normalized Benchmark Design](#43-measurement-methodology-workload-normalized-benchmark-design)
    - [4.3.1 Dual-Threaded Execution Architecture](#431-dual-threaded-execution-architecture)
    - [4.3.2 Benchmark Timing Metrics & Definitions](#432-benchmark-timing-metrics--definitions)
- [5. Key Project Deliverables](#5-key-project-deliverables)
- [6. High-Level Work Breakdown Structure (High-Level WBS)](#6-high-level-work-breakdown-structure-high-level-wbs)
  - [Team Roles & Lab Constraints](#team-roles)
  - [WBS Task Table (Phase 1 to Phase 7)](#wbs-table)
- [7. Project Schedule & Milestones](#7-project-schedule--milestones)
- [8. Acceptance Criteria (Definition of Success)](#8-acceptance-criteria-definition-of-success)
- [9. Assumptions, Constraints & Contingency Plans](#9-assumptions-constraints--contingency-plans)
  - [9.1 Assumptions](#91-assumptions)
  - [9.2 Constraints & Risk Mitigations](#92-constraints--risk-mitigations)

---

### 1. Project Overview & Objectives

#### 1.1 Background & Motivation
In smart manufacturing and industrial automation (such as CNC machining spindles and robotic joints), machinery relies on fast, repetitive control loops. For example, a motor controller must calculate and send corrective speed adjustments every 10 milliseconds ($10\text{ ms}$). If a control command arrives late by even a few milliseconds, the motor can vibrate violently, damaging the machine tool or ruining the manufactured workpiece.

Modern industrial systems are moving from **Predictive Maintenance (PdM)** to **Prescriptive Maintenance (PsM)**:
- **Predictive Maintenance (PdM):** An algorithm analyzes vibration data to warn an operator that a machine part is wearing down. Because when a technician reviews the alert, a few seconds of delay does not cause immediate damage (soft timing).
- **Prescriptive Maintenance (PsM):** The embedded controller autonomously takes corrective action within milliseconds (e.g., automatically slowing down or stopping a motor) before catastrophic failure occurs (hard real-time deadline).

#### 1.2 The Operating System Problem
Executing closed-loop Prescriptive Maintenance reveals an operating system dilemma:
1. **Why Linux alone struggles:** General-Purpose Operating Systems (GPOS) like Linux provide rich software libraries for heavy math (like Fast Fourier Transform vibration analytics and neural network inference). However, Linux is designed to be fair to all running programs. When background tasks run, Linux may pause the control program to give CPU time to other apps or to manage memory. These unpredictable pauses can exceed 10 to 50 milliseconds, causing missed deadlines.
2. **Why a Microcontroller RTOS alone is not enough:** A Real-Time Operating System (RTOS) like Zephyr guarantees that time-critical tasks run on time without random pauses. However, microcontrollers have limited CPU power and small memory, making them incapable of running heavy vibration analytics.
3. **The Proposed Dual-OS Solution:** We investigate a **Heterogeneous Dual-OS Architecture** on a single dual-chip board (the **Arduino UNO Q**) leveraging a **Multi-Rate Asymmetric Execution Model**:
   - **Cognitive Plane on Linux Processor (The Analytical Brain):** Processes 1024-sample vibration frames (~85.3 ms of physical signal at 12 kHz) using FFT and a 1D-CNN classifier at an analytical cadence of ~80–100 ms. When an updated bearing health assessment is produced, Linux sends the new speed derating setpoint to the MCU over the inter-processor serial link.
   - **Reflex Plane on Zephyr Microcontroller (The Fast Muscle):** Executes the time-critical motor actuation loop at a strict, deterministic **10 ms interval (100 Hz)** with zero jitter. Zephyr holds the latest received setpoint and applies it each cycle without blocking or waiting for the next Linux update.
   - **Inter-Processor Communication (IPC):** Serial channel (UART/SPI via Arduino Bridge/RPC layer — exact mechanism to be confirmed on the physical board) carrying lightweight setpoint messages. The protocol uses a **"latest-value-wins"** non-blocking design: Zephyr always keeps the most recently received setpoint, even if Linux is delayed.

#### 1.3 Project Objectives
- **Objective 1 (Architecture Setup):** Establish a functional dual-OS communication pipeline between Linux and Zephyr RTOS on the Arduino UNO Q.
- **Objective 2 (Benchmarking Execution):** Run a periodic 10 ms control loop for **10,000 continuous cycles** across three configurations:
  - Configuration A: Monolithic Linux under standard Completely Fair Scheduling (CFS).
  - Configuration B: Monolithic Linux under POSIX Real-Time Priority Scheduling (`SCHED_FIFO`, priority 90) on the standard Linux kernel.
  - Configuration C: Heterogeneous Dual-OS (Linux Cognitive Plane + Zephyr RTOS Reflex Plane).
- **Objective 3 (Stress & Latency Evaluation):** Measure how each configuration behaves under escalating background workload stress (0%, 50%, 100% CPU/memory/IO stress using `stress-ng`) and quantify the **Deadline Miss Ratio (DMR)**, **Cycle Period Jitter ($\sigma_J$)**, and **Worst-Case Cycle Latency ($\max T_k$)**.
- **Objective 4 (Deliverables):** Produce clear comparison charts, presentation slides, and an academic project report explaining the OS trade-offs.

---

### 2. High-Level System Components

Rather than focusing on low-level code implementation details at this proposal stage, the project is structured into four conceptual components:

```
+-----------------------------------------------------------------------------------+
|                              ARDUINO UNO Q HARDWARE                               |
|                                                                                   |
|  [ COMPONENT 1: Linux Analytics Subsystem ]                                       |
|  - Runs on the quad-core application processor (Qualcomm Cortex-A53)              |
|  - Simulates vibration signal processing and health evaluations                   |
|  - Tracks operating system interruptions (context switches and memory stalls)     |
|                                         |                                         |
|  [ COMPONENT 3: Inter-Processor Communication (IPC) Bridge ]                      |
|  - Serial message channel (UART/SPI) between both processors                      |
|                                         |                                         |
|  [ COMPONENT 2: Zephyr Real-Time Control Subsystem ]                              |
|  - Runs on the dedicated microcontroller (STM32 Cortex-M33)                       |
|  - Executes the 10 ms motor control loop with guaranteed real-time priority       |
|  - Accurately measures cycle time using hardware timers                           |
|                                                                                   |
|  [ COMPONENT 4: Benchmarking & Measurement Harness ]                              |
|  - Injects synthetic background stress to test system limits                      |
|  - Records latency data across 10,000 cycles and outputs CSV files for graphing   |
+-----------------------------------------------------------------------------------+
```

1. **Component 1 (Linux Analytics Subsystem):** Executes the heavy analytical workload (1024-point vibration FFT + 1D-CNN condition inference). Based on the detected bearing condition (Normal, Ball Fault, Inner Race Fault, Outer Race Fault), a **deterministic rule-based Look-Up Table (LUT / `if-else` policy)** calculates the prescribed motor speed derating setpoint (100%, 85%, 70%, or 60%) to relieve mechanical stress.
2. **Component 2 (Zephyr Real-Time Control Subsystem):** Runs the time-sensitive motor control task at a fixed 10 ms interval. Because it runs on a dedicated real-time microcontroller, it is isolated from Linux background activity.
3. **Component 3 (Inter-Processor Communication Bridge):** A serial message channel (UART/SPI via Arduino Bridge/RPC) where Linux sends speed recommendations, and the Zephyr microcontroller receives them non-blocking using a "latest-value-wins" protocol.
4. **Component 4 (Benchmarking & Measurement Harness):** Automated test scripts that run the 10,000-cycle experiment under different stress levels and record timing logs for analysis.

---

### 3. Technical Environment & Tools

- **Target Hardware:** Arduino UNO Q
  - Processor 1: Qualcomm QRB2210 Quad-Core ARM Cortex-A53 (runs Linux).
  - Processor 2: STM32U585 ARM Cortex-M33 (runs Zephyr RTOS).
- **Operating Systems:**
  - Embedded Linux (Debian-based) for the application processor.
  - Zephyr RTOS (v3.x) for the real-time microcontroller.
- **Development Tools & Utilities:**
  - Programming Language: C / Shell scripting / Python.
  - Build System & Toolchain: CMake, `west` (Zephyr meta-tool), and **Ninja** (a high-speed, parallel build execution backend required by Zephyr RTOS to compile C/C++ firmware rapidly), GCC ARM Embedded toolchain (`arm-none-eabi-gcc`).
  - Local RTOS Emulation & Testing: Zephyr native POSIX simulator (`native_sim`) or QEMU ARM Cortex-M emulator (`qemu_cortex_m3`), enabling the remote teammate (Akash) to write, compile, and functionally verify Zephyr periodic timer apps locally without requiring the physical board.
  - System Stress Generator: `stress-ng` (a standard Linux tool used to simulate high CPU and memory workload).
  - Operating System Metrics: Standard OS timing functions (`clock_nanosleep`, `clock_gettime`) and resource usage statistics (`getrusage`) to record task interruptions.
  - Data Analysis & Plotting: Python (matplotlib / numpy / pandas) to generate latency distribution graphs, CDF curves, and comparison box plots.
- **Benchmark Dataset Specification:**
  - **Name:** Case Western Reserve University (CWRU) Bearing Data Center Seeded Fault Dataset.
  - **Source / Download URL:** Official portal at [https://engineering.case.edu/bearingdatacenter](https://engineering.case.edu/bearingdatacenter) (Mirror/clean packages on Kaggle: `brnithish/cwru-bearing-dataset` or GitHub: `hasan-kamal/Bearing-Fault-Detection-CWRU`).
  - **Selected Subset:** 12k Drive End Bearing Fault Data sampled at 12,000 Hz under 1–3 HP motor loads.
  - **Target Classes:** 4 operational conditions — Normal Baseline (`97.mat`), Ball Fault (`118.mat`), Inner Race Fault (`105.mat`), Outer Race Fault (`130.mat`).
  - **Repository Location:** Downloaded into `data/raw/cwru/` and preprocessed into fixed 1024-sample windows in `data/processed/` for FFT analysis and model inference.

---

### 4. Scope Boundaries & Measurement Methodology

Defining clear boundaries and measurement protocols is critical to keeping the project focused and scientifically rigorous:

#### 4.1 In-Scope (What We Will Do)
- Configure the Arduino UNO Q board to run both Linux (Debian) and Zephyr RTOS.
- Implement realistic vibration analytical workload using CWRU bearing dataset playback (1024-point frames, FFT, TFLite 1D-CNN inference) coupled with a periodic 10 ms control loop.
- Implement an inter-processor message exchange between Linux and Zephyr over the board's serial link (UART/SPI via Arduino Bridge/RPC layer).
- Benchmark 10,000 continuous cycles for:
  - Standard Linux (CFS).
  - Real-Time Linux (`SCHED_FIFO`, priority 90) on the standard Linux kernel.
  - Dual-OS (Linux Cognitive Plane + Zephyr RTOS Reflex Plane).
- Compare the three configurations under no load vs. heavy background stress (`stress-ng`).
- Measure quantitative timing metrics: mean cycle period, worst-case cycle latency ($\max T_k$), period jitter standard deviation ($\sigma_J$), and Deadline Miss Ratio (DMR).
- Produce academic reports and presentations matching course requirements.

#### 4.2 Out-of-Scope (What We Will NOT Do)
- **No Physical Motor Rig:** No real motors or wiring are built. We replay recorded CWRU vibration data and use timers to focus purely on OS behavior.
- **No Novel Machine Learning / AI Research:** We do not invent new AI architectures. A standard lightweight 1D-CNN is used strictly to represent a realistic edge analytical workload.
- **No Complex Numerical Optimization for Prescriptions:** The Prescriptive Maintenance (PsM) decision is implemented as a fast, deterministic rule-based Look-Up Table (LUT / `if-else` derating policy) that maps detected fault classes to speed setpoints (100%, 85%, 70%, 60%). Complex multi-objective quadratic optimization or enterprise factory scheduling solvers are intentionally excluded to keep the focus squarely on Operating System scheduling latency, page faults, and inter-processor communication determinism.
- **No Graphical User Interface (GUI):** Tests will run from the command line (CLI) and generate log files; no complex desktop or web UI will be created.
- **No Cloud or Internet Connectivity:** All experiments run locally on the board. Wi-Fi and Cloud networking are excluded to prevent network lag from distorting OS measurement data.

#### 4.3 Measurement Methodology: Workload-Normalized Benchmark Design

##### 4.3.1 Dual-Threaded Execution Architecture

To guarantee a scientifically rigorous, peer-review-proof comparison, the benchmark enforces **Option 2 (Dual-Threaded Asymmetric Decoupling)** across all configurations. The timed 10 ms control loop executes the **exact same minimal workload** in every configuration:

| Configuration | 10 ms Control Loop (Timed Reflex) | Background Analytics (Cognitive Plane) | Background Contention | What the Benchmark Measures |
| :--- | :--- | :--- | :--- | :--- |
| **A (Linux CFS)** | **Linux Thread 1:** Periodic 10 ms loop (`clock_nanosleep`), reads latest setpoint from shared variable, logs timestamp | **Linux Thread 2:** Periodic ~85 ms loop, runs FFT + 1D-CNN inference, updates shared variable | CFS CPU time-slice sharing, kernel page faults, synthetic `stress-ng` | Wakeup-to-wakeup period jitter of Thread 1 |
| **B (Linux `SCHED_FIFO`)** | **Linux Thread 1:** Same 10 ms loop, but elevated to real-time priority (`chrt -f 90`) | **Linux Thread 2:** Same ~85 ms analytics loop running at standard CFS priority | Linux kernel locks, interrupt handling, CPU cache thrashing from `stress-ng` | Wakeup-to-wakeup period jitter of Thread 1 |
| **C (Dual-OS)** | **Zephyr `k_timer` on STM32 MCU:** Periodic 10 ms loop, reads latest setpoint from local SRAM, logs timestamp | **Linux Process:** Runs on Cortex-A53 at ~85 ms cadence, sends setpoint over serial IPC (`arduino-router`) | Linux 100% compute/memory stress (`stress-ng`) running concurrently on the MPU | Wakeup-to-wakeup period jitter of Zephyr MCU tick |

**Why This Eliminates All Bias:**
1. **Identical Timed Workload:** In all three configurations, the 10 ms tick does not compute FFTs or neural networks inside its loop. It only wakes up on a timer, samples the latest prescription setpoint, records its timestamp, and sleeps.
2. **Identical Computational Burden:** In all three configurations, the full FFT + 1D-CNN pipeline and `stress-ng` run concurrently on the system.
3. **Pure OS Architecture Evaluation:** Any deadline misses observed in Config A and B are proven to stem purely from **operating system scheduling limitations and kernel contention**, while Config C demonstrates whether **hardware-enforced heterogeneous OS isolation** achieves true zero-jitter determinism.

##### 4.3.2 Benchmark Timing Metrics & Definitions

To ensure clear communication and avoid confusion between different types of "latency", all benchmark metrics are defined simply:

| Metric | What It Means | Target / Ideal | Concrete Example |
| :--- | :--- | :---: | :--- |
| **Cycle Period ($T$)** | The actual time between two loop wakeups. | **10.0 ms** | If cycle 1 starts at 0 ms and cycle 2 starts at 10.1 ms, the period is **10.1 ms**. |
| **Jitter ($J$)** | How far the cycle drifted from the 10.0 ms target. | **0.0 ms** | If a cycle took 10.4 ms, the jitter is **+0.4 ms**. We report standard deviation ($\sigma$). |
| **Worst-Case Latency (WCL)** | The longest, slowest cycle observed out of all 10,000 cycles. | **< 10.5 ms** | If 9,999 cycles were on time, but 1 cycle paused for 24 ms, WCL is **24.0 ms**. |
| **Deadline Miss (Strict)** | Any cycle that took longer than the **10.0 ms** deadline ($T > 10.0\text{ ms}$). | **0 misses** | A cycle taking 10.2 ms is counted as a missed deadline. (>50 ms = Severe Freeze). |
| **Deadline Miss Ratio (DMR)** | Percentage of the 10,000 cycles that arrived late. | **0.00%** | 5 misses out of 10,000 cycles = **0.05% DMR** ($\frac{5}{10,000} \times 100\%$). |

**Important Distinction: Two Different Timers in This Project**
1. **Reflex Actuation Tick (10 ms):** The time-critical loop that actuates the motor. Every single cycle must run strictly within the 10.0 ms deadline. This is what we benchmark for DMR and Jitter.
2. **Cognitive AI Update (~90 ms):** The background health evaluation on Linux (FFT + AI inference + sending serial setpoint $\approx 85\text{ ms} + 5\text{ ms} \approx 90\text{ ms}$). This runs asynchronously at its own natural pace and **never blocks or delays** the 10 ms motor tick.

---

### 5. Key Project Deliverables

1. **Source Code & Scripts:**
   - Linux analytics program and telemetry collector.
   - Zephyr RTOS microcontroller firmware.
   - Inter-processor communication interface.
   - Automated benchmark test scripts.
2. **Experimental Data & Visualizations:**
   - Raw CSV log files recording 10,000 cycles for each test setup.
   - Latency distribution graphs (box plots and Cumulative Distribution Function curves) comparing the three configurations.
3. **Course Deliverables & Academic Reports:**
   - **Milestone 1 (Sep 29):** 2-Page Project Proposal & Abstract + 5-10 min in-class presentation. ✅ **COMPLETED**
   - **Milestone 2 (Oct 20):** Formal Written Progress Report describing environment setup and preliminary tests. ⏳ **3 Weeks Remaining**
   - **Milestone 3 (Nov 10):** 25-Minute In-Class Presentation and live/recorded demo. ⏳ **6 Weeks Remaining**
   - **Milestone 4 (Dec 29):** Final Written Report (up to 15 pages in IEEE format), codebase, and role breakdown. ⏳ **13 Weeks Remaining**

### 6. High-Level Work Breakdown Structure (High-Level WBS)

#### Team Roles

The board (Arduino UNO Q) is located in Huy's lab. Akash works remotely from a separate lab and has no physical board access. Work is divided accordingly:

- **Huy (Board & Linux Lead):** All tasks requiring physical board access - SSH, flashing, running benchmarks, IPC integration testing.
- **Akash (Model, Analysis & Documentation Lead):** All laptop-only tasks - model training, Zephyr firmware development (compile only), data analysis, plotting, and report drafting.

#### WBS Table

| WBS | Phase / Task | Owner | Board? | Status |
| :--- | :--- | :---: | :---: | :---: |
| **P1** | **Phase 1: Project Initiation & Proposal (Wk 1-3, Sep 14 - Sep 29) — [Milestone 1]** | | | **✅ Done** |
| P1.1 | Identify core problem: GPOS vs RTOS trade-off for PsM | Both | - | ✅ |
| P1.2 | Select hardware platform (Arduino UNO Q: A53 + M33) | Both | - | ✅ |
| P1.3 | Define 3 benchmark configs (A: CFS, B: RT-FIFO, C: Dual-OS) | Both | - | ✅ |
| P1.4 | Submit 2-page proposal and deliver in-class presentation | Both | - | ✅ |
| | | | | |
| **P2** | **Phase 2: Linux Baseline Benchmarking & Bring-up (Wk 4-6, Sep 30 - Oct 20) — [Supports M2]** | | | **🚀 Active** |
| | *Goal: Collect Config A & B results for M2 Progress Report* | | | |
| P2.1 | Connect to Linux processor (Cortex-A53) via SSH / serial | Huy 🔧 | Yes | |
| P2.1b | **Investigate IPC link:** Confirm how QRB2210 talks to STM32U585 (UART? SPI? Arduino Bridge/RPC?) and document the serial interface | Huy 🔧 | Yes | |
| P2.2 | Install `stress-ng`, `build-essential` on board | Huy 🔧 | Yes | |
| P2.3 | Ingest CWRU bearing vibration dataset (`data/raw/cwru/`) onto board filesystem | Huy 🔧 | Yes | |
| P2.4 | Write dual-threaded C benchmark for Linux: Thread 1 = 10 ms control tick (`clock_nanosleep`, logs CSV); Thread 2 = ~85 ms analytics loop (FFT, updates setpoint) | Huy 🔧 | Yes | |
| P2.5 | Run Config A: standard Linux CFS scheduling | Huy 🔧 | Yes | |
| P2.6 | Run Config B: RT-FIFO scheduling (`sudo chrt -f 90`) | Huy 🔧 | Yes | |
| P2.7 | Evaluate both under idle and stress (`stress-ng --cpu 4 --vm 1`) | Huy 🔧 | Yes | |
| P2.8 | Write shell scripts for automated stress test scenarios | Akash 💻 | No | |
| P2.9 | Draft and submit **M2 Progress Report (Due Oct 20)** | Both | - | |
| | | | | |
| **P3** | **Phase 3: Offline Model Training & Edge Deployment (Wk 4-6, Oct 1 - Oct 20, Parallel Track)** | | | |
| | *Goal: Train 1D-CNN on CWRU dataset and export TFLite INT8 model* | | | |
| P3.1 | Download CWRU raw data into `data/raw/cwru/`, segment into 1024-sample windows | Akash 💻 | No | |
| P3.2 | Train 1D-CNN fault classifier (normal / inner / ball / outer race) | Akash 💻 | No | |
| P3.3 | Quantize model to TFLite INT8 (`.tflite`) | Akash 💻 | No | |
| P3.4 | Receive `.tflite` from Akash, deploy to board via `scp`/`sftp` | Huy 🔧 | Yes | |
| P3.5 | Integrate TFLite C/C++ runtime into Thread 2 (analytics thread: FFT -> inference -> prescription) | Huy 🔧 | Yes | |
| | | | | |
| **P4** | **Phase 4: Zephyr RTOS Bring-up & Real-Time Timer Setup (Wk 5-7, Oct 7 - Oct 27)** | | | |
| | *Goal: Set up Zephyr toolchain (west + CMake + Ninja) and establish zero-jitter baseline* | | | |
| P4.1 | Install Zephyr SDK, CMake, Ninja, `west` on laptop; test with `native_sim` | Akash 💻 | No | |
| P4.2 | Configure BSP, device tree, pin mux for STM32U585 Cortex-M33 | Akash 💻 | No | |
| P4.3 | Develop Zephyr 10 ms timer app (`k_timer`); verify logic locally in `native_sim` | Akash 💻 | No | |
| P4.4 | Receive binary from Akash, flash to MCU, verify jitter over UART | Huy 🔧 | Yes | |
| P4.5 | Confirm zero-jitter RTOS baseline before IPC connection | Huy 🔧 | Yes | |
| P4.6 | Remote debugging via screen-share (Akash adjusts code, Huy re-flashes) | Both | Yes | |
| | | | | |
| **P5** | **Phase 5: Dual-OS Communication & Live Demo (Wk 7-9, Oct 26 - Nov 10) — [Supports M3]** | | | |
| | *Goal: Complete Config C and deliver M3 Presentation & Demo* | | | |
| P5.1 | Write Zephyr-side IPC: receive prescription over serial (UART/SPI), apply in actuation loop | Akash 💻 | No | |
| P5.2 | Write Linux-side IPC: serialize FFT + TFLite output, send setpoint over serial to MCU | Huy 🔧 | Yes | |
| P5.3 | Deploy both sides on board, run end-to-end integration tests | Huy 🔧 | Yes | |
| P5.4 | Inject `stress-ng` on Linux, verify Zephyr actuation is immune | Huy 🔧 | Yes | |
| P5.5 | Prepare 25-minute presentation slides (joint slide deck) | Both | - | |
| P5.6 | Co-present and demo for **M3 (Due Nov 10)** | Both | Yes | |
| | | | | |
| **P6** | **Phase 6: Full-Scale Benchmarking & Statistical Evaluation (Wk 10-12, Nov 11 - Dec 6)** | | | |
| | *Goal: Collect 10,000-cycle datasets across 9 test matrices for M4* | | | |
| P6.1 | Execute 10,000-cycle runs across 9 matrices (3 configs x 3 stress levels), export CSVs | Huy 🔧 | Yes | |
| P6.2 | Generate visualizations: CDF curves, latency box plots, jitter distribution | Akash 💻 | No | |
| P6.3 | Calculate KPIs: DMR, 99.9th percentile worst-case latency, jitter std dev | Akash 💻 | No | |
| | | | | |
| **P7** | **Phase 7: IEEE Final Report & Codebase Packaging (Wk 13-16, Dec 7 - Dec 29) — [Supports M4]** | | | |
| | *Goal: Submit 15-page IEEE report and complete code repository* | | | |
| P7.1 | Write sections: hardware setup, Linux experiments (A & B), IPC implementation | Huy 🔧 | No | |
| P7.2 | Write sections: model design, Zephyr RTOS theory, statistical analysis, conclusions | Akash 💻 | No | |
| P7.3 | Cross-review each other's sections and unify writing style | Both | - | |
| P7.4 | Clean and document code repository with test scripts and reproduction steps | Both | - | |
| P7.5 | Document individual contributions, submit final package **M4 (Due Dec 29)** | Both | - | |

> *Risk Mitigation Note: Because Phase 2 (Config A vs Config B) produces valid comparative OS data by Oct 20 (M2), the project already has tangible academic deliverables even while Zephyr/IPC integration is underway for M3.*

---

### 7. Project Schedule & Milestones

The project milestones are aligned with the official deadlines established in the CCU Operating System course syllabus:

| Milestone | Target Date | Status | Time Window | Contributing WBS Phases | Description & Major Deliverables | Primary Focus |
| :---: | :---: | :---: | :---: | :---: | :--- | :--- |
| **M1** | **Sep 29** | ✅ **COMPLETED** | Weeks 1 - 3 | **Phase 1 (P1)** | **Project Proposal & Abstract:** Submitted 2-page proposal and presented in class. | Problem definition, scope, and dual-OS concept |
| **M2** | **Oct 20** | ⏳ **UPCOMING** | Weeks 4 - 6 (3 wks left) | **Phase 2 (P2) & Phase 3 (P3)** | **Progress Report:** Submit formal written report detailing setup and preliminary results. | Platform bring-up, baseline benchmarks (Config A & B), and offline model |
| **M3** | **Nov 10** | ⏳ **UPCOMING** | Weeks 7 - 9 (6 wks left) | **Phase 4 (P4) & Phase 5 (P5)** | **Class Presentation & Demo:** Deliver 25-minute presentation and live/recorded demo. | Dual-OS integration (Config C), model inference, and stress evaluation |
| **M4** | **Dec 29** | ⏳ **FINAL** | Weeks 10 - 16 (13 wks left) | **Phase 6 (P6) & Phase 7 (P7)** | **Final Report Due:** Submit complete 15-page report in IEEE format, code repository, and roles. | In-depth OS analysis, complete 10k-cycle data, and documentation |

---

### 8. Acceptance Criteria (Definition of Success)

The project will be considered successful when the following quantitative engineering benchmarks and academic standards are fulfilled:

1. **Benchmark Execution Stability:** All 10,000 continuous control cycles execute reliably to completion without application crash, kernel panic, or buffer overflow across all 9 experimental test runs (3 Configurations $\times$ 3 Stress Levels).
2. **Quantitative Real-Time Metrics & Thresholds (Formally Defined in §4.3.1):**
   - **Nominal Cycle Period ($T_{\text{nom}}$):** Exactly $10.00\text{ ms}$ ($100\text{ Hz}$).
   - **Deadline Miss Criterion (Strict):** Any observed cycle period exceeding the nominal time budget, **$T_k > 10.00\text{ ms}$**, is officially classified as a **Deadline Miss**. Delays $T_k > 50.00\text{ ms}$ are flagged as **Severe System Starvation**.
   - **Empirical Target KPIs:**
     - **Configuration C (Dual-OS):** Must achieve a Deadline Miss Ratio of **$\text{DMR} = 0.00\%$** under 100% Linux stress (`stress-ng --cpu 4 --vm 1`), with cycle period jitter standard deviation **$\sigma_J < 0.10\text{ ms}$** and Worst-Case Cycle Latency **$\text{WCL} < 10.50\text{ ms}$**, proving absolute temporal isolation.
     - **Configurations A & B (Linux CFS & `SCHED_FIFO`):** Must capture statistically significant latency degradation under heavy load ($\text{DMR} > 0\%$ and worst-case spikes $\text{WCL} > 20.00\text{ ms}$), providing empirical validation of GPOS scheduling preemption and memory page-fault stalls.
3. **Academic Deliverable Standards:**
   - All four course milestones (M1, M2, M3, M4) submitted strictly by the official deadlines.
   - Individual teammate contributions (Huy vs. Akash) clearly documented to satisfy the syllabus peer-evaluation criteria.
   - Publication-grade final IEEE report (up to 15 pages) accompanied by fully documented, reproducible scripts in the repository.

---

### 9. Assumptions, Constraints & Contingency Plans

#### 9.1 Assumptions
- The Arduino UNO Q hardware board remains functional and accessible in Huy's laboratory.
- Synthetic stress generated by `stress-ng` provides an industry-standard, reproducible simulation of high edge computing workloads.
- The CWRU bearing dataset provides a recognized, verifiable baseline for vibration frequency spectra.

#### 9.2 Constraints & Risk Mitigations
- **Single Hardware Board Constraint:** Only Huy has physical access to the board.
  - *Mitigation:* Akash utilizes Zephyr's host emulator (`native_sim`) and QEMU to write, build, and test Zephyr application logic locally before passing compiled binaries to Huy for hardware deployment.
- **Hardware Corruption / Kernel Crash Risk:** Intensive stress testing (`stress-ng`) and direct hardware register access can cause OS crashes or filesystem corruption.
  - *Mitigation:* A golden backup image of the Debian filesystem is maintained on cloud storage, allowing full board re-flashing within 15 minutes.
- **Contingency Schedule Buffer:** If dual-OS inter-processor communication setup takes longer than anticipated, Phase 2 (Config A vs Config B on Linux) provides complete, valid comparative operating systems data for Milestone 2 (Oct 20), guaranteeing that the team never misses an academic deadline.
- **IPC Mechanism Uncertainty:** The exact inter-processor link between the QRB2210 (MPU) and STM32U585 (MCU) has not yet been verified on the physical board. It is expected to be a serial channel (UART or SPI) exposed through Arduino's Bridge/RPC layer, not shared RAM (since the two chips are separate packages). Task P2.1b is specifically allocated to investigate and document this during Phase 2.
  - *Mitigation:* The IPC protocol is designed as a lightweight "latest-value-wins" single-value serial message, which works identically over UART, SPI, or shared memory. Only the transport driver changes; the application logic and benchmark methodology remain the same regardless of the underlying channel.
