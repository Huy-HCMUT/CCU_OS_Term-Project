# Week 7–10 Lab Progress Report
### Heterogeneous OS Benchmarking for Real-Time Edge Control on Asymmetric Hardware
**Course:** Operating Systems (Fall 2026) — National Chung Cheng University (CCU)  
**Author / Lab Lead:** Quang-Huy Nguyen  
**Sprint Window:** Weeks 7–10 (Oct 21 – Nov 17, 2026)  
**Execution Dates:** PC-side Phase 5 work Nov 10; board runs Nov 13–17, 2026  
**Target Milestone:** Milestone 3: 25-minute presentation and demo (**Dec 1, 2026**; moved from Nov 17. Results due Nov 28, slides Nov 29–30)

> **Status (Nov 17, 2026).** Phase 5 (full Config C with IPC) and the fair three-way comparison (Phase 5d) are finished, with 3 repeats per condition. The realistic-load experiments (Phase 6a/6b) are set up and the first run is in progress; their results are **not** in this report. Every number below comes from a script output on `results/raw/`, named next to each table. Open team items are marked **[TBD]**.

---

## 1. Executive Summary

**Question:** can a heterogeneous split (Linux analytics + MCU real-time loop) keep a 10 ms control loop within its deadline under heavy Linux load, where Linux `SCHED_OTHER` (Config A) and `SCHED_FIFO` (Config B) cannot?

**Answer so far (synthetic `stress-ng` load, 3 repeats each, worst-case lateness WCL):**

| Config | Where the 10 ms loop runs | Idle | All-core stress | Deadline misses (> 1 ms) |
| :--- | :--- | ---: | ---: | :--- |
| **A** | Linux, default scheduling (`SCHED_OTHER`) | 0.54 ms | **18.0–27.9 ms** | up to 39 % (core-0 heavy), 10 % (all-core) |
| **B** | Linux, `SCHED_FIFO` 90 + `mlockall` | 0.47 ms | 0.55–0.77 ms | 0 % |
| **B-iso** | B on its own core (3), interrupts and load on cores 0–2 | 0.10 ms | 0.28–0.39 ms | 0 % |
| **C, default settings** | STM32 MCU, setpoints from Linux over RouterBridge | 0.76 ms | 0.76 ms | 0 % |
| **C, tuned** | same, loop thread above the message thread | **8.1 µs** | **7.8 µs** | 0 % |

Source: `results/phase5d/compare_configs.md` (Linux lateness relative to each run's own floor; Config C wake-only, period fitted).

**Main findings:**
1. **A fails under load** (deadline misses, WCL up to 28 ms). **B and B-iso hold the deadline** under synthetic CPU load, with B-iso about 2× tighter.
2. **Config C is isolated from Linux load**: its timing is the same at idle and under all-core stress.
3. **But Config C with default settings is not better than B.** The RouterBridge message thread has a higher priority than the loop and delays it by up to ≈ 0.8 ms whenever a setpoint arrives. One priority change (loop above the message thread) brings the worst case to ≈ 8 µs: about **40× better than B-iso under all-core stress** (12× at idle).
4. The referee board is now trustworthy (DWT timestamps). The old ≈ −390 ppm "oscillator offset" from M2 was mostly the old referee losing its own clock cycles.

**In progress:** realistic loads (network burst and an edge-analytics "production" scenario), and an end-to-end test where a third board plays the motor drive (§7).

---

## 2. Work Breakdown & Milestone Checklist

| WBS Task | Description (scope statement) | What was done | Deliverables / Artifacts | Status |
| :---: | :--- | :--- | :--- | :---: |
| **M2** | Written progress report (due Oct 27) | Submitted, with review corrections | `docs/Operating System_Progress Report.pdf`, `docs/Week_04_06_Progress_Report.md` | ✅ Done |
| **P4.5** | Sub-ms RTOS baseline before IPC | Re-run 4× with the DWT referee | `results/raw/baseline_dwtref*/` | ✅ Done |
| **P5.1** | Zephyr-side IPC: receive setpoint, apply in loop | `set_setpoint` handler, atomic latest-value-wins word, per-cycle log | `benchmarks/config_c_ipc/` | ✅ Done |
| **P5.2** | Linux-side IPC: analytics → setpoint → MCU | Python sender (FFT + setpoint rule), every 85.33 ms | `benchmarks/config_c_ipc/python/` | ✅ Done |
| **P5.3** | End-to-end integration test | `ipc-sanity`: all messages delivered, 0 mismatches | `results/raw/ipc/` | ✅ Done |
| **P5.4** | Inject stress, verify MCU timing | `ipc-all` at 0/50/100 % and all-core, 3 repeats, stock + tuned | `results/raw/ipc*`, `results/phase5b/`, `results/phase5d/` | ✅ Done |
| **Phase 5d** | (added) Fair A/B/B-iso/C comparison | All-core tier, isolated B, 3 repeats of A/B, one lateness definition | `results/phase5d/` | ✅ Done |
| **Phase 6a** | (added) Realistic loads | Tools, Docker image, calibration and smoke tests done; runs started Nov 17 | `benchmarks/realload/` | ⏳ In progress |
| **Phase 6b** | (added) Command delivery to an emulated drive | Feasibility test done; build and runs planned | `benchmarks/diagnostics/pwm_loopback/` | ⏳ Planned |
| **P5.5** | 25-minute slide deck | Not started | — | ⏳ Nov 29–30 |
| **P5.6** | Present and demo (M3) | Demo: **[TBD]** | — | ⏳ Dec 1 |

**Note on P5.2:** the analytics workload is the in-tree FFT plus a rule-based setpoint table. The 1D-CNN / TFLite model is not part of the measured control path. (A CNN runs in Phase 6a only as realistic *background* load.)

---

## 3. Changes Since M2

- **M3 moved to Dec 1** (results by Nov 28).
- **Scheduler wording (recommendation).** Config A uses Linux's default policy `SCHED_OTHER`. Since kernel 6.6 its fair scheduler is **EEVDF**, which replaced CFS ([kernel documentation](https://docs.kernel.org/scheduler/sched-eevdf.html)); our board runs 6.16. Proposed wording: "`SCHED_OTHER`, Linux's default fair scheduler (EEVDF since 6.6, previously CFS)". This changes no result: both are fair schedulers without real-time guarantees. **[TBD: team agreement]**
- **Lateness definition unified (Phase 5d).** Linux runs: lateness relative to each run's own minimum (wake-up floor removed). Config C: wake-only DWT timestamps relative to the best cycle, with a fitted period. Absolute Linux values are kept in `results/phase5d/compare_long.csv`.
- **Stress tiers renamed for clarity.** The old "50 %/100 %" tiers load **only core 0** (measured: cpu0 100 %, cores 1–3 ≈ 1–2 %). They are now called *core-0 medium / heavy*. A new **all-core** tier loads all four cores (100 % each).
- **Paper scope (decided Nov 17).** The final report has ≤ 8 pages for experiments and results. Realistic load becomes the main result; the `stress-ng` data becomes the controlled synthetic reference.

---

## 4. Phase 5 Design and Implementation

### 4.1 Data Path

```
Linux (QRB2210, under load)                            MCU (STM32U585, Zephyr-based core)
-----------------------------------                    -----------------------------------------
replayed CWRU frame (1024 samples @ 12 kHz)
  -> Hann window + FFT (numpy)
  -> setpoint rule (100/85/70/60 %)
  -> Bridge.call("set_setpoint", seq, sp)  ==RPC==>    bridge thread: g_sp_word = (seq << 8) | sp
     every 85.33 ms, absolute schedule                      (one aligned 32-bit store, atomic)
                                                       10 ms loop: DWT timestamp
                                                                   -> read g_sp_word once (32-bit load)
                                                                   -> log it, apply sp
                                                                   -> 500 µs pulse on D2 -> referee board
```

### 4.2 Design Choices

| Choice | Decision | Why |
| :--- | :--- | :--- |
| Timing loop | Copied unchanged from the baseline sketch (`micros()` schedule, `delay(6)` + spin, 500 µs D2 pulse); only one 32-bit read plus two stores added per cycle | Any timing difference can be attributed to IPC, not to a new loop design |
| Receive path | RouterBridge RPC handler `set_setpoint(seq, sp)` packs `(seq << 8) \| sp` into one `volatile uint32_t` | A single aligned 32-bit access is atomic on the Cortex-M33: no lock, the loop never waits for IPC |
| Semantics | Latest value wins; the sequence number shows which message was applied in each cycle | A control loop must never wait for analytics |
| Sender | Python Arduino App, one setpoint per 85.33 ms (≈ 11.7 messages/s) | Same cadence as the analytics thread in Configs A/B |
| Measurement | DWT timestamps on the MCU (main metric) + DWT-based referee board on D2 | Two independent clocks (§5) |

**Thread priorities (measured on the board).** In Zephyr a lower number means a higher priority. With the library defaults ("stock"), the loop thread runs at **14** and RouterBridge's `bridge` thread at **5**, so message handling can preempt the loop. The **tuned** variant raises the loop to **4** (one `k_thread_priority_set` call at the end of `setup()`); everything else is identical.

### 4.3 Setpoint Rule on the Real CWRU Frames

Peak magnitude > 0.15, then: peak bin ≥ 150 → 60 %; ≥ 115 → 70 %; ≥ 75 → 85 %; otherwise 100 % (bin width 11.72 Hz). On the 100 test frames only the outer-race block changes the setpoint (60 % × 15, 100 % × 10); Normal, Inner and Ball give 100 %. The message rate is constant whatever the value, so this does not affect the timing study. In a 10,000-cycle run the applied setpoint changes ≈ 240 times.

### 4.4 Referee Fix (DWT Timestamps)

At M2 the referee timestamped D2 edges with Zephyr's `k_cycle_get_32()` and stored whole microseconds. That counter loses ≈ 508 ppm while the chip sleeps, and the referee sleeps most of the time. The referee now reads `DWT->CYCCNT` in the D2 interrupt and stores raw cycle deltas. **Prediction (stated before the re-run):** if the ≈ 390 ppm was the referee's own lost cycles, the offset shrinks; if it was an oscillator difference, it stays. Result in §5.

### 4.5 Harness Modes

| Mode | What it runs | Output folder |
| :--- | :--- | :--- |
| `sanity`, `0`, `50`, `100`, `all` | Original P4.5 baseline modes (unchanged) | `results/raw/` |
| `b2-*` / `b2t-*` | Baseline sketch, stock / tuned priorities | `results/raw/baseline_dwtref*/`, `baseline_tuned*/` |
| `ipc-*` / `ipct-*` | IPC app + sender, stock / tuned | `results/raw/ipc*/`, `ipc_tuned*/` |
| `<variant>-allcore` | All-core stress tier | `<folder>_allcore/` |
| `--rep N` | Repeat N into `<folder>_rN/` (never overwrites) | — |

Variant modes now also record the Linux load during each run (stress-ng process count, per-core busy %, governor, frequency, temperature at start and mid-run) and stop with an error if data are incomplete.

---

## 5. Referee vs DUT Clock

Source: `results/baseline_dwtref/referee_vs_dut.md` (new DWT referee) and `results/referee_p45.md` (old referee, P4.5 data).

| Stress | Referee | Referee vs DUT (ppm) | Referee σ (µs) | Max \|period − 10 ms\| (µs) | Referee misses |
| :---: | :---: | ---: | ---: | ---: | ---: |
| 0 % | old (`k_cycle`, µs) | −389.78 | 3.51 | 11 | 0 |
| 50 % | old | −386.75 | 29.20 | 996 | 0 |
| 100 % | old | −393.50 | 25.44 | 897 | 0 |
| sanity | **new (DWT)** | −0.16 | 9.01 | 33.2 | 0 |
| 0 % | **new** | −0.28 | 22.29 | 59.4 | 0 |
| 50 % | **new** | +2.60 | 22.29 | 59.5 | 0 |
| 100 % | **new** | +2.95 | 20.69 | 55.9 | 0 |

- **The −390 ppm offset disappears** (now −0.3 to +3 ppm). It was mostly the old referee's own clock loss, not a difference between the boards' oscillators. The M2 wording "crystal drift" must be withdrawn.
- **The ≈ 1 ms deviations the old referee saw under stress were timestamp errors.** The new referee's largest deviation (≈ 56–60 µs) matches the DUT's own worst case in the same runs (≈ 55 µs).
- What remains: the DUT's loop runs at ≈ 10.0055 ms per cycle (+545 ppm) because Zephyr's timekeeping loses cycles while the MCU sleeps. The period fit removes this constant offset, so jitter and WCL are unaffected; the paper states it.

---

## 6. Board Results

### 6.1 IPC Link Health

Source: `results/ipc/ipc_summary.md`, `results/ipc_tuned/ipc_summary.md` (first repeat shown; repeats 2–3 agree).

| Run | Sent = received | Send errors | Setpoint mismatch | Setpoint age p50 / p99 (cycles) | Round trip p50 / p99 (ms) |
| :--- | :---: | ---: | ---: | :---: | :---: |
| stock, 0 / 50 / 100 % | 1241 / 1267 / 1273 ✓ | 0 | 0 | 4 / 8 | 7.9–8.2 / 9.2–10.0 |
| tuned, 0 / 50 / 100 % | 1238 / 1291 / 1263 ✓ | 0 | 0 | 4 / 8 | 8.4–8.7 / 12.7–13.0 |

Every setpoint arrived and was applied with the right value. "Age" = how many 10 ms cycles the current setpoint has been held (≈ 85 ms / 10 ms). Tuning the MCU makes the Linux-side round trip ≈ 0.5 ms slower at the median (plausibly because the MCU now finishes its loop work before answering; not tested), which does not matter for an 85 ms update rate. *Known gap:* in stock repeat 2 at 100 % the per-cycle setpoint log was read back for only 1,750 of 10,000 cycles (readout failure); its timing data are complete.

### 6.2 Config C: Baseline vs IPC, Stock vs Tuned

Source: `results/phase5b/repeats_summary.md` (3 repeats; 4 for the stock baseline; mean [min–max] across runs).

| Variant | WCL (µs) idle | WCL (µs) core-0 heavy | σ_L (µs) core-0 heavy | DMR @ 1 ms |
| :--- | ---: | ---: | ---: | :---: |
| Baseline (no IPC), stock | 20.3 [3.4–55.0] | 41.2 [9.2–52.6] | 11.4 | 0 % |
| **IPC, stock** | **759.2 [755.6–762.5]** | **809.1 [802.3–820.2]** | 49.4 | 0 % |
| Baseline, tuned | 1.7 [1.5–2.1] | 1.5 [1.5–1.5] | 0.4 | 0 % |
| **IPC, tuned** | **8.1 [6.7–9.3]** | **7.7 [7.3–8.1]** | 0.6 | 0 % |

- **Stock IPC costs ≈ 0.75 ms of worst-case lateness, already at idle.** Source `results/phase5d/ipc_attribution.md`: 72–83 % of the late cycles (> 100 µs) contain a setpoint arrival (base rate 11.7 %), and with tuned priorities the number of late cycles drops from 84–121 per run to **0**. So the cause is the message thread preempting the loop, not Linux load.
- **Tuned IPC**: ≈ 6–8 µs above the tuned baseline, plausibly interrupt handling of the serial traffic (not tested).
- **Scope hypothesis for Config C** (DMR 0 % at heavy stress, σ_L < 100 µs, WCL < 500 µs): **met with tuned priorities; not met with default settings** (WCL ≈ 0.8 ms).
- **"Every 11th pulse late" pattern** (found Nov 13 in the stock baseline: one pulse in 11 is late by 30–53 µs, constant within a run): it sets the stock baseline's WCL and is absent in all 18 tuned runs checked (`results/phase5b/pulse_pattern.md`, idle and core-0 tiers). The arithmetic of the bridge thread's 1 ms poll against the 10 ms loop predicts exactly an 11-cycle period; it is plausible but not directly tested.

### 6.3 Three-Way Comparison (Phase 5d)

Source: `results/phase5d/compare_configs.md`. WCL in µs, mean [min–max] of 3 runs; DMR @ 1 ms, highest run.

| Config | Idle | Core-0 medium | Core-0 heavy | All-core | DMR max (any tier) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| A | 545 [521–563] | 5,304 [4,616–5,844] | 6,321 [5,992–6,975] | 21,580 [18,000–27,852] | 39.2 % |
| B | 471 [433–516] | 755 [353–973] | 489 [378–653] | 661 [552–770] | 0 % |
| B-iso | 96 [90–108] | 324 [303–357] | 329 [316–354] | 324 [275–388] | 0 % |
| C, IPC stock | 759 | 795 | 809 | 759 (n = 1) | 0 % |
| C, IPC tuned | 8.1 | 7.9 | 7.7 | 7.8 (n = 1) | 0 % |

- **Measured load:** core-0 tiers 100 % on core 0 only; all-core 100 % on all four cores (B-iso: cores 0–2 at 100 %, its own core 3 at 4.5 %).
- **A:** misses deadlines in every loaded tier. Interestingly its miss rate is *lower* under all-core (10 %) than under core-0 heavy (39 %), although its WCL is higher: a plausible reading (not tested) is that with all four cores loaded A competes on every core but against more evenly shared work, so it waits less often but sometimes much longer.
- **B:** 0 misses, but one run came within 27 µs of the 1 ms deadline (core-0 medium, 973 µs).
- **B-iso:** 0 misses, ≈ 0.3 ms worst case under any stress.
- **Scope hypotheses:** A (DMR > 0 and WCL > 10 ms under heavy load): **met in the all-core tier** (core-0 tiers: DMR > 0 but WCL ≤ 7 ms). B ("substantially reduces, may keep tail latency"): **met**. C: see §6.2.
- **Caveat:** Config C all-core has 1 run per variant (2 for the stock baseline); the other cells have 3.

---

## 7. In Progress: Realistic Load and End-to-End Command Delivery

**Why.** `stress-ng` creates busy *programs*, which `SCHED_FIFO` can always preempt. A deployed edge device also does work inside the kernel that a real-time thread cannot simply preempt: network interrupts, network processing (softirqs, up to 8 ms per round on this board) and driver code. Phase 6a tests A/B/B-iso/C under two realistic loads:
- **Network burst (`rnet`):** the PC sends as fast as the Wi-Fi allows (measured 6.3–6.7 MB/s); the board receives and discards it.
- **Production (`rdeploy`):** the PC streams the CWRU vibration signal at its real rate (48 kB/s); a Docker container on the board runs a 1D-CNN (ONNX Runtime) on every 85.33 ms window, logs results and sends a one-second summary upstream (UDP), like an IIoT edge node. The CNN has random weights on purpose: it is background load, not a classifier.

**Done (Nov 16–17):** tools written, reviewed and committed; Docker image built; CNN size calibrated (40.5 ms per inference); 60 s smoke tests of both loads passed. Under production, onnxruntime keeps two cores ≈ 100 % busy (its worker threads spin while waiting, library default). **First run (A/B/B-iso under the network burst, repeat 1) started Nov 17.** Results follow in the next report.

**Predictions written before any run** (e.g.): B under the network burst will be *worse* than under all-core `stress-ng` (WCL > 0.78 ms); B-iso stays ≤ 0.5 ms only if the Wi-Fi interrupt can be kept off its core; tuned C stays < 20 µs with 0 misses.

**Phase 6b — the command reaches the "motor drive".** A third UNO Q plays the drive: the DUT's MCU sends the speed setpoint as a hardware-PWM signal (duty = 0.8 × setpoint, 500 Hz), and the third board timestamps when each new speed arrives. A loopback test on the third board (Nov 17) confirmed the design: period 2000.000 µs, duty within 0.01 points, 0 missed edges in 100,040 periods, and one `analogWrite()` costs 7.3 µs (max 69 µs). A new duty always takes effect at the next 2 ms PWM boundary. (Source: `results/diagnostics/pwm_loopback_summary.md`; its pre-set limit "≤ 2,000 µs after the call" was missed by 1.7 µs in 1 of 200 switches, explained by the call's own duration.)

---

## 8. Risks and Open Questions

| Risk | Status / mitigation |
| :--- | :--- |
| Stock RouterBridge priorities | Resolved by measurement: cause of the 0.8 ms; tuned variant reported next to stock |
| One run per condition | Resolved for the main matrix (3 repeats); Config C all-core still n = 1–2 |
| ≈ 250 ppm of the DUT's +545 ppm loop-period offset unexplained | Open; does not affect jitter or WCL (period fitted) |
| "Every 11th pulse" mechanism | Plausible explanation, not tested; absent in tuned runs |
| Realistic load depends on our Wi-Fi and PC | Stated as a limit; load checks (bytes received, inference count) recorded before, during and after each run |
| Stock (non-real-time) kernel | B and B-iso are not best-case real-time Linux (no `PREEMPT_RT`); stated as a limit |
| Third board runs a newer Arduino core (1.0.0 vs 0.90.0) | Relevant code compared and identical; the DUT's own PWM write cost is measured in every run |

---

## 9. Team Status and Next Steps

| When | Who | What |
| :--- | :--- | :--- |
| Nov 17–18 | Huy | Linux realistic runs, repeat 1 (network burst, then production) |
| Nov 18–19 | Huy (with AI tools) | Build the drive chain (MCU speed output, drive emulator, harness, analysis) |
| ≈ Nov 19–21 | Huy | Wire the third board; Config C end-to-end runs (idle, production, burst) |
| ≈ Nov 22–24 | Huy | Repeat 2 of all realistic runs |
| Nov 25–28 | Huy | Analysis, figures, results freeze |
| **[TBD]** | Akash (remote) | **[TBD: tasks]** |
| Nov 29–30 | **[TBD]** | P5.5 slide deck |
| Dec 1 | **[TBD]** | P5.6 presentation and demo (**[TBD: demo]**) |
