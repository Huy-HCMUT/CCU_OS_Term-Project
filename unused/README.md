# unused/

Files that are no longer used by any harness, analysis script, test or report in this project.
They were moved here on 2026-11-18 (cleanup) instead of being deleted, so their history stays easy to find.
Each file keeps its original path below `unused/`; to restore one, `git mv` it back to that path.

Nothing in `results/raw/` was moved (raw data stays where it is). Files that look old but are still used stay in place
(see "Not moved" below).

## What is here and why it is unused

| File (original path) | What it is | Why unused |
| :--- | :--- | :--- |
| `benchmarks/send_test_pulses.py` | One-off Linux-side script that sends 10 pulses on D2 through `Bridge.call("set_pin_by_name", ...)`, used once to check the referee wiring during Config C bring-up (Phase 4). | Nothing calls it. Wiring and timing checks are now done by `benchmarks/pin_test/` and the `sanity` / `act-sanity` modes of `run_config_c_hardware_test.py`. |
| `benchmarks/plot_config_c_dual_metrology.py` | Plot of the Phase 4.5 Config C baseline: DUT DWT timing next to the first referee (`config_c_dwt_*.csv`, `config_c_referee_*.csv`). | That referee timestamped with `k_cycle_get_32()` and truncated to whole µs; it was replaced by the DWT-based referee (DECISIONS.md D5), and Config C is now analysed with `benchmarks/analysis/analyze_latency.py` and `analyze_referee.py`. It finds `results/` via `Path(__file__).parent.parent`, so it only runs again from its original path. |
| `results/plots/config_c_dual_metrology_plot.png` | The figure that script produced. | Superseded with the script; only the local Week 4-6 notes embedded it (that link now points to the old path). |
| `ipc/`, `mcu_zephyr/src/`, `mpu_linux/profiler/`, `mpu_linux/stress/` (`.gitkeep` only) | Empty placeholder folders from the initial repository layout (September 2026). | Never filled: the IPC and MCU code live in the Arduino App folders under `benchmarks/` (`config_c_*`, `referee/`, `drive_emu/`), and the load generators are `stress-ng` and `benchmarks/realload/`. |

## Not moved (old but still used)

- `benchmarks/pin_test/`: used by the harness (`b2-` runs) and the clock diagnostics.
- `benchmarks/config_c_demo/`: the M3 live-demo app (not for measurements).
- `benchmarks/config_c_ipc/`, `config_c_ipc_tuned/`, `config_c_base_tuned/`, `config_c_sender_sketch.ino`: produced results that are still reported.
- `benchmarks/run_benchmark.sh`, `run_advanced_experiments.sh`, `results/parse_advanced_metrics.py`, `results/plot_advanced_results.py`: Phase 2 and Tests 1-5, still cited (e.g. Test 3 for affinity).
- `benchmarks/analysis/compare_baseline_ipc.py`: produced `results/ipc/compare_baseline_vs_ipc.md`.
- `docs/` reports and PDFs: submitted deliverables.
