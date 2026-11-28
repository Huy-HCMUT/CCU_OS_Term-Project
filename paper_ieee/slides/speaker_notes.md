# Heterogeneous OS Benchmarking on the Arduino UNO Q — Final Presentation: speaker notes

## 1. Can one board run heavy analytics and still hit a 10 ms deadline?

About 1 minute. Introduce the question and the team: Huy built and ran everything on the boards; An-Rui (Akash) did the analysis, statistics, report and slides.

## 2. Prescriptive maintenance puts a hard deadline in the loop

About 1.5 minutes. Walk the four layers: only the Act layer has a hard deadline. Everything else in the experiment exists to load the board the way a real digital-twin host would.

## 3. Neither kind of OS does both jobs well

About 1 minute. Point at the last table row: it names exactly the two mechanisms the results will come back to, kernel work on Linux and thread priority on the RTOS.

## 4. One board, two chips, two operating systems

About 1.5 minutes. Left to right: the PC drives the load; the DUT has both chips; the referee checks the MCU’s timing from outside; the drive emulator checks every command. Mention early that the kernel is the stock PREEMPT kernel.

## 5. Four places to run the same 10 ms loop

About 1.5 minutes. The only thing that changes between rows is where and how the loop is scheduled. The colours stay the same on every chart that follows.

## 6. One lateness measure, synthetic and realistic loads

About 1.5 minutes. Two points: the same lateness measure for every configuration, and per-block comparison because MCU runs are 18 times shorter. stress-ng only creates busy programs; the realistic loads also make the kernel work, which is what matters later.

## 7. Against busy programs, SCHED_FIFO holds the deadline

About 1.5 minutes. The controlled reference first. Default Linux fails as soon as there is load. SCHED_FIFO looks fine here, because it simply preempts busy programs. That is why the next slide uses realistic load.

## 8. Under network + CNN, only the MCU stays far below 1 ms

About 2 minutes. Compared fairly, per 10,000 ticks. Default Linux sits in the milliseconds whenever the CNN runs. SCHED_FIFO crosses the deadline once network traffic is added. The reserved core is worse than plain SCHED_FIFO. The MCU stays near 10 µs everywhere. The ratios come with ranges: the gap to SCHED_FIFO is large but its exact size is uncertain.

## 9. Every Linux setup missed the 1 ms deadline

About 1.5 minutes. Every Linux configuration missed under rboth, even SCHED_FIFO (about 1 tick in 4,000). Read the three side notes: the network is what breaks SCHED_FIFO; default Linux’s two runs disagree; and the MCU’s zero misses only bound its rate, so the real evidence is its 10 µs worst case.

## 10. Reserving a core moved the kernel’s work onto it

About 2 minutes. The surprise: giving the loop its own core made it worse. That core received about eleven times more function-call interrupts and twice the softirqs, while being only 24 % busy. A priority-90 thread can push programs aside but not the kernel’s interrupt work, so what lands on the loop’s core matters more than how busy it looks.

## 11. On the MCU, one priority setting decided the result

About 1.5 minutes. An RTOS is not real-time by itself. With library defaults the communication thread outranks the control loop, so each incoming setpoint delayed the tick by up to 0.8 ms. One call raising the loop above it brought the cost down to about 8 µs, roughly 100 times better.

## 12. Every speed command reached the drive

About 2 minutes. Follow one command from left to right. The drive board checked all 1,920: none lost, wrong or duplicated. The green bars do not move with load because the PWM sets that delay. Only the setpoint’s trip from Linux grows under load, and the loop never waits for it.

## 13. Watch the deadline hold while Linux is busy

About 4 minutes. Run the live demo; if the boards or the room’s Wi-Fi misbehave, play the replay video instead. The point to land: with the loop on the MCU, a full Linux load does not move the tick.

## 14. What our results do not show

About 1.5 minutes. Four things our results do not show. First, the CNN in the realistic load has random weights: it is realistic background load, not a fault classifier, so we make no accuracy claim, and the setpoints come from the FFT rule. Second, our plan called for a Zephyr k_timer on the MCU; every MCU result uses the Arduino sketch’s micros() schedule with a sleep and a final spin. Third, three explanations are consistent with the data but untested: idle-state wake-up making idle Linux slower than loaded Linux, an early test where mlockall looked worse, and the kernel work landing on the reserved core. Fourth, the kernel is the stock PREEMPT kernel, not PREEMPT_RT, which would likely narrow the gap for SCHED_FIFO. The scope is also limited: one board set, an emulated drive, two repeats per realistic condition, and 10,000-cycle MCU runs.

## 15. Conclusion

About 1.5 minutes. Our four findings, then the answer to the question in the title. One: SCHED_FIFO protects the loop against busy programs but not against the kernel’s interrupt and softirq work, so under network traffic plus the CNN every Linux configuration missed the 1 ms deadline. Two: reserving a core by affinity alone made it worse, because the kernel placed its own work on that core. Three: the real-time MCU kept every tick within about 10 µs at every load level and delivered all 1,920 speed commands to the emulated drive. Four: on the MCU, giving the loop priority over the communication thread cut the IPC cost about 100-fold. So: analytics on Linux, the loop that acts on the machine on the real-time core, and the loop at the top priority there. Likely questions: why not PREEMPT_RT (not tested); why MCU runs are shorter (MCU memory, so we compare per 10,000-cycle block); how MCU lateness is measured (DWT counter, period fitted, relative to the best cycle, the same definition as Linux).
