# Real-Time Operating System Benchmarking on Heterogeneous Edge Controllers
### CCU Operating System (Fall 2026) — Term Project

---

## 👥 Team Information

- **Course:** Operating System (Fall 2026)
- **Department:** Department of Computer Science & Information Engineering (CSIE)
- **Institution:** National Chung Cheng University (CCU)
- **Members:**
  - **Member 1:** `[Quang-Huy Nguyen]` (Student ID: `[615461004]`)
  - **Member 2:** `[Your Name]` (Student ID: `[Your Student ID]`)

---

## 📄 Project Overview (Abstract)

Modern industrial Cyber-Physical Systems (CPS) are rapidly transitioning from **Predictive Maintenance (PdM)** to **Prescriptive Maintenance (PsM)**:
- **Predictive Maintenance (PdM)** focuses on open-loop health monitoring (e.g., analyzing vibration spectra to predict equipment faults). Because results are reviewed by human operators, it is tolerant to soft timing variations.
- **Prescriptive Maintenance (PsM)** closes the loop by triggering **automated real-time corrective actions** (e.g., dynamic motor deceleration, load shedding, lubrication control) within strict, millisecond-level deadlines to prevent mechanical failure.

This shift from open-loop monitoring to closed-loop actuation exposes a fundamental **Operating System dilemma**:
1. **General-Purpose Operating Systems (GPOS, e.g., Linux):** Provide rich runtime ecosystems required for signal processing (FFT) and machine learning inference, but their non-deterministic kernel mechanisms (CFS scheduling preemption, involuntary context switching, demand paging) can introduce unbounded latency spikes under heavy system load.
2. **Real-Time Operating Systems (RTOS, e.g., Zephyr):** Guarantee microsecond-level determinism and strict deadline compliance, but lack the compute throughput and software stack required for complex analytical workloads.

This project investigates this trade-off on the **Arduino UNO Q**, an Asymmetric Multi-Processing (AMP) hardware platform featuring both an application microprocessor (Linux MPU) and a real-time microcontroller (Zephyr MCU). By using a PsM workload as our benchmarking vehicle, we evaluate task scheduling behavior, memory contention effects, and inter-processor communication (IPC) latency to study how heterogeneous operating systems can reliably bridge the gap between heavy analytics and hard real-time control.

---

## 📂 Repository Structure

```
CCU_OS_Term Project/
├── README.md                      # Project overview & team information
├── .gitignore                     # Git ignore configuration
├── docs/                          # Project proposals, notes, and specifications
├── data/                          # Datasets and ingestion scripts
├── mpu_linux/                     # Linux-side software and telemetry tools
├── mcu_zephyr/                    # MCU firmware and Zephyr RTOS source
├── ipc/                           # Inter-Processor Communication (IPC) modules
├── benchmarks/                    # Test scripts and benchmarking harness
├── results/                       # Experimental results, logs, and plots
└── paper_ieee/                    # IEEEtran report sources and presentation slides
```

---

> *Note: This project is currently in the initial design and proposal phase. Specific experimental parameters, workloads, and target metrics will be finalized during upcoming team discussions.*
