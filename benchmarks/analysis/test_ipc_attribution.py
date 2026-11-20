from pathlib import Path
import pandas as pd

from ipc_attribution import analyze_pair, run


def _write_synth_pair(
    folder: Path,
    tag: str,
    late_indices: set[int],
    n_rows: int = 1001,
) -> tuple[Path, Path]:
    dwt_path = folder / f"config_c_dwt_{tag}.csv"
    seq_path = folder / f"config_c_ipc_seq_{tag}.csv"

    dwt_rows = []
    seq_rows = []
    prev_cyc = 0
    seq_val = 0
    for k in range(n_rows):
        displace = 48_000 if k in late_indices else 0
        cyc = k * 1_600_000 + displace
        delta = 1_600_000 if k == 0 else (cyc - prev_cyc)
        dwt_rows.append(
            {
                "cycle": k,
                "dwt_cyccnt": cyc,
                "dwt_delta_cyc": delta,
                "dwt_period_us": f"{delta / 160.0:.3f}",
                "dwt_lateness_ms": "0.00000",
            }
        )
        prev_cyc = cyc

        if k > 0 and k % 10 == 0:
            seq_val += 1
        seq_rows.append({"cycle": k, "applied_seq": seq_val, "applied_setpoint_pct": 100})

    pd.DataFrame(dwt_rows).to_csv(dwt_path, index=False)
    with open(seq_path, "w", encoding="utf-8", newline="") as f:
        f.write("# rx_count=100\n")
        pd.DataFrame(seq_rows).to_csv(f, index=False)
    return dwt_path, seq_path


def test_ipc_attribution_late_and_clean(tmp_path):
    dwt_late, seq_late = _write_synth_pair(tmp_path, "0_ipc", {10, 30, 50})
    res_late = analyze_pair(tmp_path.name, "0_ipc", dwt_late, seq_late)
    assert res_late["n_intervals"] == 1000
    assert res_late["n_msg"] == 100
    assert res_late["n_late"] == 3
    assert res_late["late_with_msg_share"] == "1.000"
    assert res_late["msg_late_share"] == "0.030"
    assert res_late["late_dev_p50_us"] == "300.0"

    dwt_clean, seq_clean = _write_synth_pair(tmp_path, "50_ipc", set())
    res_clean = analyze_pair(tmp_path.name, "50_ipc", dwt_clean, seq_clean)
    assert res_clean["n_late"] == 0
    assert res_clean["late_with_msg_share"] == ""
    assert res_clean["late_dev_p50_us"] == ""
    assert res_clean["late_dev_p90_us"] == ""
    assert res_clean["late_dev_max_us"] == ""

    out_md = tmp_path / "attr.md"
    run([tmp_path], out_md)
    assert out_md.exists()
    assert out_md.with_suffix(".csv").exists()

