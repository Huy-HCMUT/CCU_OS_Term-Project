# Demo Video Plan (optional, for extra credit)

A 3–5 minute video that shows the result instead of only reporting it. Board clips (Huy) and clips made from data we already have (An-Rui) are cut together, with captions carrying the key numbers. The same clips are the backup if the live demo fails in class.

## Storyboard

| # | Clip | Length | Who | How |
| :- | :--- | ---: | :--- | :--- |
| 1 | Title card and the question: "Can one board run heavy analytics and still hit a 10 ms deadline?" | 10 s | An-Rui | Title slide from the presentation |
| 2 | Bench tour: DUT, referee and drive emulator, the D2 / D3 / GND wires, the PC | 30 s | Huy | Phone camera, steady and close |
| 3 | The loop working: `config_c_demo` running; LED3 green at 100 %, red when the outer-race frames drop the setpoint to 60 %; console printing `frame … -> setpoint …` | 45 s | Huy | Phone on the board + screen capture of the console, side by side |
| 4 | **The key moment:** start `rboth` (network traffic + CNN container) while the demo keeps running; `htop` shows the Linux cores busy, the LED keeps switching on time | 45 s | Huy | Screen capture of `htop` + phone on the LED |
| 5 | A vs C under the same load: a short run of each (about 2,000 cycles) under `rboth`; show the printed worst case and misses | 45 s | Huy | Screen capture, large terminal font |
| 6 | Replay of the recorded runs: A, B and C under `rboth`, the 1 ms deadline line, live worst-case and miss counters | 17 s | done | `results/replay/replay_rboth_r1.mp4` |
| 7 | Why: two short animated diagrams ("latest value wins"; why `SCHED_FIFO` cannot preempt the kernel's interrupt work) | 60 s | An-Rui | Presentation slides with build animations, voice-over |
| 8 | The full chain: drive-emulator log, every command received, 0 lost | 20 s | Huy | Screen capture |
| 9 | Conclusion card (the four findings) and the team | 15 s | An-Rui | Conclusion slide |

## Best visual if a scope is available

If Huy can borrow an oscilloscope or logic analyzer: put the probe on DUT pin D2 and use persistence or trigger-on-edge mode. Config C's pulse edges stay sharp under `rboth`; the same view for a Linux GPIO pulse (if one can be added) would smear. Fifteen seconds of this is more convincing than any chart.

## Recording tips

- Record every board clip twice; the second take is the class backup.
- Terminal font 20 pt or larger; hide unrelated windows.
- Keep each clip under a minute; captions carry the numbers (from `results/phase6b/realload.md` and `headline_stats.md`).
- Say once on screen that the replay (clip 6) is recorded data, not live.

## Regenerating the replay

```bash
python benchmarks/analysis/replay_animation.py                      # rboth, run 1 -> results/replay/replay_rboth_r1.mp4
python benchmarks/analysis/replay_animation.py --series A B B-iso C # include the reserved-core variant
python benchmarks/analysis/replay_animation.py --tier rdeploy --rep 2
python benchmarks/analysis/replay_animation.py --still 499          # poster frame (PNG)
```

Every dot is one measured cycle from `results/raw/`, with the same lateness definition as the report (relative to each run's best cycle; Config C with the period fitted). The first 10,000 cycles of each run are shown, because Config C runs are 10,000 cycles long; played at 6× real time, the replay lasts about 17 s.
