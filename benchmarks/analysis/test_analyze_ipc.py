import pytest
import pandas as pd
from analyze_ipc import analyze_tag, run_analysis


def create_case_a_files(tmp_path):
    sender_path = tmp_path / "config_c_ipc_sender_caseA.csv"
    seq_path = tmp_path / "config_c_ipc_seq_caseA.csv"

    # Sender file: seqs 1-4, all ok, setpoints 100, 85, 70, 60, rtt_us 1000, 2000, 3000, 4000, skipped_after 0, 0, 1, 0
    sender_data = [
        [1, 0, 100, 1000000, 1000100, 1001100, 1000.0, 0, "ok"],
        [2, 1, 85, 2000000, 2000100, 2002100, 2000.0, 0, "ok"],
        [3, 2, 70, 3000000, 3000100, 3003100, 3000.0, 1, "ok"],
        [4, 3, 60, 4000000, 4000100, 4004100, 4000.0, 0, "ok"],
    ]
    sender_cols = [
        "seq",
        "frame_idx",
        "setpoint_pct",
        "release_ns",
        "t_send_ns",
        "t_return_ns",
        "rtt_us",
        "skipped_after",
        "status",
    ]
    with open(sender_path, "w", newline="") as f:
        f.write("# frames_source=synthetic period_ns=85333333\n")
    pd.DataFrame(sender_data, columns=sender_cols).to_csv(sender_path, mode="a", index=False)

    # Seq file: # rx_count=4; cycles 0-8 -> (1, 100), 9-16 -> (2, 85), 17-19 -> (4, 60)
    seq_rows = []
    for c in range(20):
        if c <= 8:
            seq_rows.append([c, 1, 100])
        elif c <= 16:
            seq_rows.append([c, 2, 85])
        else:
            seq_rows.append([c, 4, 60])

    with open(seq_path, "w", newline="") as f:
        f.write("# rx_count=4\n")
    pd.DataFrame(seq_rows, columns=["cycle", "applied_seq", "applied_setpoint_pct"]).to_csv(
        seq_path, mode="a", index=False
    )

    return seq_path, sender_path


def test_ipc_case_a(tmp_path):
    seq_path, sender_path = create_case_a_files(tmp_path)
    res = analyze_tag("caseA", seq_path, sender_path)

    assert res["cycles"] == 20
    assert res["sent"] == 4
    assert res["sent_ok"] == 4
    assert res["send_errors"] == 0
    assert res["skipped_slots"] == 1
    assert res["rx_count"] == 4
    assert res["first_cycle_with_ipc"] == 0
    assert res["distinct_applied"] == 3
    assert res["unobserved_ok"] == 1
    assert res["setpoint_mismatch"] == 0
    assert res["age_max_cyc"] == 8.0
    assert res["age_p50_cyc"] == 3.0
    assert res["rtt_p50_us"] == 2500.0


def test_ipc_case_b(tmp_path):
    seq_path, sender_path = create_case_a_files(tmp_path)

    # Case B: as A, but cycles 9-16 show setpoint 70
    seq_df = pd.read_csv(seq_path, comment="#")
    seq_df.loc[9:16, "applied_setpoint_pct"] = 70

    with open(seq_path, "w", newline="") as f:
        f.write("# rx_count=4\n")
    seq_df.to_csv(seq_path, mode="a", index=False)

    res = analyze_tag("caseB", seq_path, sender_path)
    assert res["setpoint_mismatch"] == 8


def test_run_analysis_pipeline(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    out_dir = tmp_path / "out"

    create_case_a_files(raw_dir)
    run_analysis(raw_dir, out_dir)

    assert (out_dir / "ipc_summary.csv").exists()
    assert (out_dir / "ipc_summary.md").exists()


def test_rx_count_missing(tmp_path):
    seq_path, sender_path = create_case_a_files(tmp_path)

    # Rewrite seq file's first line to "# rx_count=" (keep rest of file)
    lines = seq_path.read_text().splitlines(keepends=True)
    lines[0] = "# rx_count=\n"
    seq_path.write_text("".join(lines))

    res = analyze_tag("caseA", seq_path, sender_path)
    assert res["rx_count"] == -1
    assert res["setpoint_mismatch"] == 0

    # Rewrite seq file without any # line
    seq_df = pd.read_csv(seq_path, comment="#")
    seq_df.to_csv(seq_path, index=False)
    res2 = analyze_tag("caseA", seq_path, sender_path)
    assert res2["rx_count"] == -1

