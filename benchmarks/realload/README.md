# realload/ — realistic Linux load (Phase 6a / 6b)

The load the DUT's Linux side carries in the `rnet`, `rdeploy` and `rboth` tiers. It replaces synthetic `stress-ng` with work a deployed edge controller really does.

| File | Runs on | What it does |
| :--- | :--- | :--- |
| `realload.sh` | DUT (Linux) | `start <tier> <label> <outdir> <pc_ip> [iso]`, `check <tier>`, `stop`, `status`. Starts the tier's receivers, a sampler (CPU load, temperature, frequency every ≈ 10 s) and `/proc` counter snapshots; `check` confirms the load is really there (`LOADCHECK OK` / `FAIL`). Called by `benchmarks/run_benchmark_6r.sh` and the Config C harness. |
| `pc_traffic.py` | PC | `bulk` = TCP bulk traffic to port 5557 (≈ 6.5 MB/s over Wi-Fi); `ingest` = a 12 kHz float32 sensor stream (48,000 B/s) to port 5555. Writes a JSON summary (bytes, rate, reconnects). |
| `Dockerfile`, `analytics_node.py`, `make_model.py` | DUT (Docker image `realload:1`) | The `rdeploy` analytics node: receives the sensor stream, cuts 1,024-sample windows and runs a small 1D-CNN with ONNX Runtime (3 threads), ≈ 11.7 inferences/s. The CNN has fixed-seed **random weights on purpose**: it is background load, not a fault classifier. |
| `model_width.txt` | both | The CNN width chosen by calibration (one inference ≈ 40 ms on the board); raw calibration data in `results/raw/real_calibration/`. |
| `tests/` | PC | `python -m pytest -q benchmarks/realload/tests` |

Tiers: `rnet` = `socat` sink on port 5557 + PC `bulk`; `rdeploy` = the analytics container on port 5555 + PC `ingest`; `rboth` = both at once. In the B-iso runs the receivers, the container and the sampler are limited to CPUs 0–2.
