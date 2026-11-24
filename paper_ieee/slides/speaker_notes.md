# Heterogeneous OS Benchmarking on the Arduino UNO Q — Final Presentation: speaker notes

## 1. Can one board run heavy analytics and still hit a 10 ms deadline?

About 1 minute. The question: a maintenance controller has to run heavy analytics (network traffic, a CNN in a container) and also act on a strict 10 ms control tick. We compare four ways to do that on one Arduino UNO Q, which has a Linux processor and a separate Zephyr microcontroller. Huy ran everything on the boards; An-Rui (Akash) built the analysis pipeline, reviewed the code and drafted the reports and slides.

## 2. From predicting a fault to acting on it within milliseconds

About 1.5 minutes. Predictive maintenance only predicts and reports, so timing is soft. Prescriptive maintenance closes the loop: the controller changes the machine itself, so the control tick has a hard deadline. Our motivating example is a CNC cell with a sensory tool holder (products like SCHUNK iTENDO² exist): vibration goes to an AI model on a Linux “digital twin” host, and a 10 ms loop applies the speed or feed override. The AI’s advice may be late by many milliseconds without harm; the 10 ms loop may not.

## 3. Neither kind of OS does both jobs well

About 1 minute. Linux gives us the software ecosystem for analytics, but its scheduler and the kernel’s own interrupt and softirq work can delay a time-critical thread. An RTOS like Zephyr bounds timing but cannot run the analytics stack. So the research question has two parts: how far can Linux go with real-time scheduling, and does putting the loop on a separate microcontroller remove the problem?

## 4. One board, two chips, two operating systems

About 1.5 minutes. The Arduino UNO Q is an asymmetric multiprocessing board: a Qualcomm Linux processor and a separate STM32 microcontroller running Zephyr, connected by Arduino’s RouterBridge, an RPC layer over an internal serial link. Say early that the kernel is the stock PREEMPT kernel, not PREEMPT_RT; it matters for the Linux real-time results. Two more UNO Q boards complete the setup: one is an independent timing referee on pin D2, the other emulates the motor drive and checks every speed command it receives.

## 5. Four places to run the same 10 ms loop

About 2 minutes. The timed loop does the same tiny amount of work in every configuration, so differences come from the OS, not the workload. A uses Linux’s default scheduler: SCHED_OTHER, which since kernel 6.6 is EEVDF rather than CFS. B raises the loop to SCHED_FIFO priority 90 and locks memory. B-iso adds a reserved core: the loop runs alone on core 3, and our other programs and the movable interrupts are moved to cores 0 to 2, using affinity only, no boot-time isolation. C moves the loop to the microcontroller; Linux sends each new setpoint over RouterBridge.

## 6. One lateness measure for every configuration

About 1.5 minutes. Every cycle has a fixed release time on an absolute schedule, so a late cycle cannot hide behind a short one. Since Phase 5d, lateness is measured relative to each run’s best cycle for every configuration, so Linux and MCU numbers are directly comparable. Run lengths differ: Linux runs are 180,000 cycles (30 minutes); MCU runs are 10,000 cycles (100 seconds), limited by MCU memory. A longer run catches a larger worst case, so we compare per 10,000-cycle block. Each realistic condition was repeated twice.

## 7. Realistic load makes the kernel work, not just the CPU

About 1.5 minutes. Our first loads were stress-ng, which only creates busy programs, and a SCHED_FIFO thread simply preempts them. A deployed edge controller also makes the kernel work: network interrupts and network processing, container networking, driver code. So Phase 6 uses three realistic loads: rnet is bulk network traffic from the PC; rdeploy streams real CWRU bearing vibration over Wi-Fi into an ONNX CNN in a Docker container; rboth runs both. Every run logged load checks to prove the load was really there.

## 8. Only the MCU stays far from the 1 ms deadline

About 1.5 minutes. The headline, compared fairly: the typical worst case in a block of 10,000 cycles under the heaviest load, network traffic plus the CNN. Default Linux 5.6 ms, SCHED_FIFO 0.31 ms, the reserved-core variant 1.46 ms, the MCU 9 µs. So the MCU is about 30 times below the best Linux setup and about 600 times below default Linux. The full-run worst cases on the next slide are larger for Linux because its runs are 18 times longer.

## 9. Every Linux setup missed the 1 ms deadline under rboth

About 2 minutes. Whole-run numbers under rboth. Default Linux misses 3.5 % of deadlines overall, but its two runs differ a lot (4.7 versus 2.4 %), more than counting noise explains, so the honest statement is the per-run range. SCHED_FIFO misses rarely, about 1 cycle in 4,000, but it does miss: its worst case is 1.5 ms. The reserved-core variant misses about ten times more often than plain SCHED_FIFO. The MCU had no misses in 20,000 cycles, which bounds its miss rate at 0.015 % with 95 % confidence.

## 10. The MCU stays near 10 µs at every load level

About 1.5 minutes. Each point is the worst case of one block of 10,000 cycles, on a log scale. Default Linux sits at 4 to 15 ms whenever the CNN runs. SCHED_FIFO stays below 1 ms under the CNN alone but crosses it when network traffic is added. The reserved-core variant is above 1 ms in every one of its 36 rboth blocks. The MCU sits between 6 and 11 µs in every load level, including idle.

## 11. The gap is large; its exact size is not

About 2 minutes. We added error bars to the headline. First, the ratio: the MCU is about 34 times below SCHED_FIFO under rboth, but the plausible range is 18 to 103 times, because SCHED_FIFO’s block worst cases are spread out; under the CNN alone it is only 16 to 24 times. Second, zero misses in 20,000 cycles only proves the miss rate is below 0.015 % with 95 % confidence; that is weaker than it sounds, because the MCU runs are short. The real argument is that the MCU’s worst case, about 10 µs, is 100 times below the 1 ms deadline. Third, default Linux’s two runs disagree far more than chance allows, so more repeats would be needed for a precise miss rate.

## 12. Reserving a core made SCHED_FIFO worse

About 2 minutes. The most surprising Linux result: moving everything off core 3 and giving it to the control thread made things worse under the combined load. Core 3 ended up receiving about ten times more function-call interrupts than in plain SCHED_FIFO, and it was 24 % busy although none of our programs ran there. Our interpretation: a priority-90 thread takes the CPU from normal programs at once, but it cannot preempt interrupt handlers or the softirq work that runs when an interrupt ends. So for this kind of setup, the kernel work landing on the loop’s core matters more than how busy the core looks. These counters are run averages, so they are consistent with the result but do not prove the cause of each late cycle; a kernel trace would.

## 13. On the MCU, thread priority decided the result

About 1.5 minutes. An RTOS is not automatically real-time. With the Arduino library defaults, RouterBridge’s bridge thread runs above the sketch’s loop, so each incoming setpoint delayed the tick by up to about 0.8 ms. Raising the loop to priority 4, above the bridge thread at 5, removed most of that cost: about 8 µs with IPC. All Config C results from Phase 5d on use this tuned version, and both are reported. The lesson applies to both sides: priorities are part of the design, on Linux and on the MCU.

## 14. From vibration to drive: four steps, one hard deadline

About 1.5 minutes. Config C closes the loop. The Linux analytics compute a new setpoint about every 85 ms and send it over RouterBridge. The protocol is latest value wins: the MCU keeps only the newest setpoint, packed with a sequence number into one aligned 32-bit word, so the loop reads both in one load without a lock. The loop applies the setpoint on its next tick and sends the speed command to the third board as a 500 Hz PWM signal, which emulates the motor drive. The loop never waits for Linux: if a setpoint is late, the tick still happens on time with the previous one.

## 15. Every speed command reached the drive

About 1.5 minutes. The drive board checked every command: all 1,920 speed commands of the 8 runs arrived, none lost, wrong or duplicated. The drive saw each new command 1.5 to 4.1 ms after the tick, and that delay is the same at idle and under every load, because it is set by the 500 Hz PWM itself, not by Linux. Linux load only stretches how long a setpoint takes to reach the MCU: the 99th-percentile round trip grows from 12.8 ms at idle to 15.7 ms under rboth, which is harmless for wear that develops over minutes, and the loop never waits for it.

## 16. Watch the deadline hold while Linux is busy

About 5 minutes. Draft demo plan built around the config_c_demo app; Huy to confirm which steps the board setup can show live. Keep a recorded backup in case the boards or the classroom Wi-Fi misbehave. The point to land: with the loop on the MCU, a full Linux load does not move the tick, while the same load visibly hurts the default-scheduler loop.

## 17. What our results do not show

About 1.5 minutes. Four things our results do not show. First, the CNN in the realistic load has random weights: it is realistic background load, not a fault classifier, so we make no accuracy claim, and the setpoints come from the FFT rule. Second, our plan called for a Zephyr k_timer on the MCU; every MCU result uses the Arduino sketch’s micros() schedule with a sleep and a final spin. Third, three explanations are consistent with the data but untested: idle-state wake-up making idle Linux slower than loaded Linux, an early test where mlockall looked worse, and the kernel work landing on the reserved core. Fourth, the kernel is the stock PREEMPT kernel, not PREEMPT_RT, which would likely narrow the gap for SCHED_FIFO. The scope is also limited: one board set, an emulated drive, two repeats per realistic condition, and 10,000-cycle MCU runs.

## 18. Conclusion

About 1.5 minutes. Our four findings, then the answer to the question in the title. One: SCHED_FIFO protects the loop against busy programs but not against the kernel’s interrupt and softirq work, so under network traffic plus the CNN every Linux configuration missed the 1 ms deadline. Two: reserving a core by affinity alone made it worse, because the kernel placed its own work on that core. Three: the real-time MCU kept every tick within about 10 µs at every load level and delivered all 1,920 speed commands to the emulated drive. Four: on the MCU, giving the loop priority over the communication thread cut the IPC cost about 100-fold. So: analytics on Linux, the loop that acts on the machine on the real-time core, and the loop at the top priority there. Likely questions: why not PREEMPT_RT (not tested); why MCU runs are shorter (MCU memory, so we compare per 10,000-cycle block); how MCU lateness is measured (DWT counter, period fitted, relative to the best cycle, the same definition as Linux).
