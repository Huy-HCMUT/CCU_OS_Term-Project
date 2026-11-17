#!/usr/bin/env python3
"""Phase 6a analysis across realistic load tiers (R-net and R-deploy) for A, B, B-iso, and C IPC tuned."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_latency import load_run  # noqa: E402
from compare_configs import SERIES_COLORS, _fmt_range, _summarize_run  # noqa: E402

SERIES_ORDER = ["A", "B", "B-iso", "C IPC tuned"]
TIERS = ["rnet", "rdeploy"]
BLOCK_SIZE = 10000

REAL_LINUX_DIR_RE = re.compile(r"^real_r(?P<rep>\d+)$")
REAL_LINUX_FILE_RE = re.compile(r"^(?P<config>[AB])_0(?P<iso>_iso)?_(?P<tier>rnet|rdeploy)\.csv$")
REAL_C_DIR_RE = re.compile(r"^ipc_tuned_(?P<tier>rnet|rdeploy)(?:_r(?P<rep>\d+))?$")

SOFTIRQ_KEYS = ("NET_RX", "NET_TX", "BLOCK", "TIMER")


def _block_wcls(l_rel: np.ndarray, block_size: int = BLOCK_SIZE) -> np.ndarray:
    n_blocks = int(l_rel.size // block_size)
    if n_blocks <= 0:
        return np.array([], dtype=np.float64)
    return l_rel[: n_blocks * block_size].reshape(n_blocks, block_size).max(axis=1)


def _parse_sections(path: Path) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    cur: str | None = None
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip("\r\n")
        if line.startswith("#"):
            cur = line[1:].strip()
            sections.setdefault(cur, [])
        elif cur is not None and line.strip():
            sections[cur].append(line)
    return sections


def _parse_per_cpu_table(lines: list[str]) -> tuple[int, dict[str, tuple[list[int], str]]]:
    if not lines:
        return 0, {}
    header_tokens = lines[0].split()
    n_cpus = sum(1 for tok in header_tokens if tok.startswith("CPU"))
    if n_cpus <= 0:
        return 0, {}

    rows: dict[str, tuple[list[int], str]] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        key = key.strip()
        tokens = rest.split()
        if len(tokens) < n_cpus:
            continue
        try:
            vals = [int(t) for t in tokens[:n_cpus]]
        except ValueError:
            continue
        desc = " ".join(tokens[n_cpus:])
        rows[key] = (vals, desc)
    return n_cpus, rows


def _parse_netdev(lines: list[str]) -> dict[str, tuple[int, int, int, int]]:
    out: dict[str, tuple[int, int, int, int]] = {}
    for line in lines:
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        toks = rest.split()
        if len(toks) < 10:
            continue
        try:
            out[iface] = (int(toks[0]), int(toks[1]), int(toks[8]), int(toks[9]))
        except ValueError:
            continue
    return out


def _parse_vmstat(lines: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in lines:
        toks = line.split()
        if len(toks) == 2:
            try:
                out[toks[0]] = int(toks[1])
            except ValueError:
                pass
    return out


def _parse_counters(before_path: Path, after_path: Path) -> dict:
    info = {
        "irq_total_per_cpu": "",
        "irq_total_delta": np.nan,
        "top5_irqs": "",
        "softirq_net_rx_delta": np.nan,
        "softirq_net_rx_per_cpu": "",
        "softirq_net_tx_delta": np.nan,
        "softirq_net_tx_per_cpu": "",
        "softirq_block_delta": np.nan,
        "softirq_block_per_cpu": "",
        "softirq_timer_delta": np.nan,
        "softirq_timer_per_cpu": "",
        "wlan0_rx_bytes_delta": np.nan,
        "wlan0_rx_packets_delta": np.nan,
        "wlan0_tx_bytes_delta": np.nan,
        "wlan0_tx_packets_delta": np.nan,
        "pswpin_delta": np.nan,
        "pswpout_delta": np.nan,
        "pgmajfault_delta": np.nan,
    }
    if not before_path.exists() or not after_path.exists():
        return info

    sb = _parse_sections(before_path)
    sa = _parse_sections(after_path)

    # Interrupts
    nb, irqs_b = _parse_per_cpu_table(sb.get("INTERRUPTS", []))
    na, irqs_a = _parse_per_cpu_table(sa.get("INTERRUPTS", []))
    n_cpus = min(nb, na)
    if n_cpus > 0:
        cpu_totals = [0] * n_cpus
        per_line_deltas: list[tuple[int, str, str, list[int]]] = []
        for key, (va, desc) in irqs_a.items():
            vb = irqs_b.get(key, ([0] * n_cpus, ""))[0]
            deltas = [va[i] - vb[i] for i in range(n_cpus)]
            for i in range(n_cpus):
                cpu_totals[i] += deltas[i]
            per_line_deltas.append((sum(deltas), key, desc, deltas))
        per_line_deltas.sort(key=lambda item: item[0], reverse=True)
        info["irq_total_per_cpu"] = ",".join(str(x) for x in cpu_totals)
        info["irq_total_delta"] = int(sum(cpu_totals))
        top5_parts = []
        for tot, key, desc, deltas in per_line_deltas[:5]:
            label = f"{key}({desc})" if desc else key
            top5_parts.append(f"{label}={tot}[" + ",".join(str(d) for d in deltas) + "]")
        info["top5_irqs"] = "; ".join(top5_parts)

    # Softirqs
    sb_soft_n, soft_b = _parse_per_cpu_table(sb.get("SOFTIRQS", []))
    sa_soft_n, soft_a = _parse_per_cpu_table(sa.get("SOFTIRQS", []))
    soft_cpus = min(sb_soft_n, sa_soft_n)
    if soft_cpus > 0:
        for skey in SOFTIRQ_KEYS:
            if skey in soft_a and skey in soft_b:
                va = soft_a[skey][0]
                vb = soft_b[skey][0]
                deltas = [va[i] - vb[i] for i in range(soft_cpus)]
                low = skey.lower()
                info[f"softirq_{low}_delta"] = int(sum(deltas))
                info[f"softirq_{low}_per_cpu"] = ",".join(str(d) for d in deltas)

    # Netdev (wlan0)
    nd_b = _parse_netdev(sb.get("NETDEV", []))
    nd_a = _parse_netdev(sa.get("NETDEV", []))
    if "wlan0" in nd_b and "wlan0" in nd_a:
        rxb, rxp, txb, txp = nd_b["wlan0"]
        rxa, rxpa, txa, txpa = nd_a["wlan0"]
        info["wlan0_rx_bytes_delta"] = int(rxa - rxb)
        info["wlan0_rx_packets_delta"] = int(rxpa - rxp)
        info["wlan0_tx_bytes_delta"] = int(txa - txb)
        info["wlan0_tx_packets_delta"] = int(txpa - txp)

    # VMstat
    vm_b = _parse_vmstat(sb.get("VMSTAT", []))
    vm_a = _parse_vmstat(sa.get("VMSTAT", []))
    for k in ("pswpin", "pswpout", "pgmajfault"):
        if k in vm_b and k in vm_a:
            info[f"{k}_delta"] = int(vm_a[k] - vm_b[k])

    return info


def _parse_thermal(thermal_path: Path) -> dict:
    info = {
        "temp_max_c": np.nan,
        "freq_min_khz": np.nan,
        "throttled": None,
    }
    if not thermal_path.exists():
        return info
    df = pd.read_csv(thermal_path)
    if df.empty:
        return info

    if "temp_max_c" in df.columns:
        temps = pd.to_numeric(df["temp_max_c"], errors="coerce").dropna()
        if not temps.empty:
            info["temp_max_c"] = float(temps.max())

    freq_vals: list[float] = []
    for col in ("freq_cpu0_khz", "freq_cpu1_khz", "freq_cpu2_khz", "freq_cpu3_khz"):
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if not s.empty:
                freq_vals.append(float(s.min()))
    if freq_vals:
        info["freq_min_khz"] = float(min(freq_vals))

    throttled = False
    if "cooling_states" in df.columns:
        for cell in df["cooling_states"].dropna():
            for tok in str(cell).split(";"):
                tok = tok.strip()
                if tok.isdigit() and int(tok) > 0:
                    throttled = True
                    break
            if throttled:
                break
    info["throttled"] = throttled
    return info


def _parse_analytics(analytics_path: Path) -> dict:
    info = {
        "infer_count": np.nan,
        "infer_rate_hz": np.nan,
        "infer_p50_us": np.nan,
        "infer_p99_us": np.nan,
    }
    if not analytics_path.exists():
        return info
    df = pd.read_csv(analytics_path)
    if df.empty or "infer_us" not in df.columns:
        return info
    vals = pd.to_numeric(df["infer_us"], errors="coerce").dropna().to_numpy(dtype=np.float64)
    if vals.size == 0:
        return info
    info["infer_count"] = int(vals.size)
    info["infer_p50_us"] = float(np.percentile(vals, 50))
    info["infer_p99_us"] = float(np.percentile(vals, 99))
    if "t_mono_ns" in df.columns and len(df) >= 2:
        ts = pd.to_numeric(df["t_mono_ns"], errors="coerce").dropna().to_numpy(dtype=np.float64)
        if ts.size >= 2 and ts[-1] > ts[0]:
            info["infer_rate_hz"] = float((ts.size - 1) / ((ts[-1] - ts[0]) * 1e-9))
    return info


def _find_pc_traffic(folder: Path, label: str, tier: str) -> dict:
    info = {"pc_avg_rate_Bps": np.nan, "pc_reconnects": np.nan}
    candidates = [
        folder / f"pc_traffic_{label}.json",
        folder / f"pc_traffic_{tier}.json",
    ]
    chosen = next((p for p in candidates if p.exists()), None)
    if chosen is None:
        return info
    try:
        data = json.loads(chosen.read_text(encoding="utf-8"))
        if "avg_rate_Bps" in data:
            info["pc_avg_rate_Bps"] = float(data["avg_rate_Bps"])
        if "reconnects" in data:
            info["pc_reconnects"] = int(data["reconnects"])
    except (OSError, ValueError, TypeError):
        pass
    return info


def _parse_env_notes(env_path: Path) -> dict:
    info = {"loadcheck": "", "irqs_moved": "", "wifi_irq": ""}
    if not env_path.exists():
        return info
    lc: list[str] = []
    wifi: list[str] = []
    irqs_moved = ""
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("# loadcheck"):
            lc.append(s[2:].strip())
        elif s.startswith("# irqs_moved="):
            irqs_moved = s[2:].strip()
        elif s.startswith("# wifi_irq"):
            wifi.append(s[2:].strip())
    info["loadcheck"] = " | ".join(lc)
    info["irqs_moved"] = irqs_moved
    info["wifi_irq"] = " | ".join(wifi)
    return info


def _collect_evidence(folder: Path, label: str, tier: str, env_path: Path) -> dict:
    ev: dict = {}
    ev.update(_parse_counters(folder / f"counters_{label}_before.txt", folder / f"counters_{label}_after.txt"))
    ev.update(_parse_thermal(folder / f"thermal_{label}.csv"))
    if tier == "rdeploy":
        ev.update(_parse_analytics(folder / f"analytics_{label}.csv"))
    else:
        ev.update({"infer_count": np.nan, "infer_rate_hz": np.nan, "infer_p50_us": np.nan, "infer_p99_us": np.nan})
    ev.update(_find_pc_traffic(folder, label, tier))
    ev.update(_parse_env_notes(env_path))
    return ev


def _collect_realload_runs(raw_dir: Path) -> list[dict]:
    records: list[dict] = []
    if not raw_dir.exists():
        return records

    linux_dirs: list[tuple[int, Path]] = []
    c_dirs: list[tuple[str, int, Path]] = []
    for entry in raw_dir.iterdir():
        if not entry.is_dir():
            continue
        m_l = REAL_LINUX_DIR_RE.fullmatch(entry.name)
        if m_l:
            linux_dirs.append((int(m_l.group("rep")), entry))
            continue
        m_c = REAL_C_DIR_RE.fullmatch(entry.name)
        if m_c:
            tier = m_c.group("tier")
            rep = int(m_c.group("rep")) if m_c.group("rep") else 1
            c_dirs.append((tier, rep, entry))

    for rep, folder in sorted(linux_dirs, key=lambda x: x[0]):
        for csv_path in sorted(folder.glob("*.csv")):
            m = REAL_LINUX_FILE_RE.fullmatch(csv_path.name)
            if not m:
                continue
            cfg = m.group("config")
            series = "B-iso" if (cfg == "B" and m.group("iso")) else cfg
            tier = m.group("tier")
            label = csv_path.stem
            df = pd.read_csv(csv_path, comment="#", skipinitialspace=True)
            if df.empty or "lateness_ms" not in df.columns:
                continue
            l_abs = df["lateness_ms"].to_numpy(dtype=np.float64) * 1000.0
            l_rel = l_abs - float(np.min(l_abs))
            row = _summarize_run(
                series=series,
                tier=tier,
                rep=rep,
                rel_path=f"{folder.name}/{csv_path.name}",
                l_rel=l_rel,
                l_abs=l_abs,
            )
            bw = _block_wcls(l_rel)
            row["n_blocks"] = int(bw.size)
            row["block_wcl_median_us"] = float(np.median(bw)) if bw.size else np.nan
            row["block_wcl_max_us"] = float(np.max(bw)) if bw.size else np.nan
            row["_block_wcls"] = bw
            row.update(_collect_evidence(folder, label, tier, folder / f"env_{label}.txt"))
            records.append(row)

    tier_rank = {t: i for i, t in enumerate(TIERS)}
    for tier, rep, folder in sorted(c_dirs, key=lambda x: (tier_rank[x[0]], x[1])):
        csv_path = folder / f"C_0_ipc_tuned_{tier}.csv"
        if not csv_path.exists():
            continue
        label = f"0_ipc_tuned_{tier}"
        run = load_run(csv_path, clock_hz=160e6, period_mode="fit")
        l_rel = run.lateness_us
        row = _summarize_run(
            series="C IPC tuned",
            tier=tier,
            rep=rep,
            rel_path=f"{folder.name}/{csv_path.name}",
            l_rel=l_rel,
            l_abs=None,
        )
        bw = _block_wcls(l_rel)
        row["n_blocks"] = int(bw.size)
        row["block_wcl_median_us"] = float(np.median(bw)) if bw.size else np.nan
        row["block_wcl_max_us"] = float(np.max(bw)) if bw.size else np.nan
        row["_block_wcls"] = bw
        row.update(_collect_evidence(folder, label, tier, folder / f"config_c_env_{label}.txt"))
        records.append(row)

    return records


def _load_reference_wcl(ref_csv: Path) -> dict[tuple[str, str], tuple[str, float]]:
    """Return {(series, tier): (formatted mean [min-max], mean_us)} for tier 0 and allcore."""
    out: dict[tuple[str, str], tuple[str, float]] = {}
    if not ref_csv.exists():
        return out
    df = pd.read_csv(ref_csv)
    for series in SERIES_ORDER:
        for tier in ("0", "allcore"):
            sub = df[(df["series"] == series) & (df["tier"] == tier)]
            if sub.empty:
                continue
            vals = sub["wcl_us"].to_numpy(dtype=np.float64)
            out[(series, tier)] = (_fmt_range(vals, 1), float(np.mean(vals)))
    return out


def _build_markdown(long_df: pd.DataFrame, ref_map: dict[tuple[str, str], tuple[str, float]]) -> str:
    lines = [
        "# Phase 6a Realistic-Load Comparison (R-net & R-deploy)",
        "",
        "## Timing Summary",
        "",
        "| Series | Tier | n runs | Cycles | WCL µs mean [min–max] | Block WCL median µs | σ_L µs mean | DMR@1 ms max % | Ref 0% WCL µs mean [min–max] | Ref all-core WCL µs mean [min–max] |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for series in SERIES_ORDER:
        ref0 = ref_map.get((series, "0"), ("—", np.nan))[0]
        ref_ac = ref_map.get((series, "allcore"), ("—", np.nan))[0]
        for tier in TIERS:
            sub = long_df[(long_df["series"] == series) & (long_df["tier"] == tier)]
            if sub.empty:
                lines.append(f"| {series} | {tier} | 0 | — | — | — | — | — | {ref0} | {ref_ac} |")
                continue
            n_runs = len(sub)
            cycles = int(np.median(sub["n"].to_numpy(dtype=float)))
            wcl_str = _fmt_range(sub["wcl_us"].to_numpy(dtype=np.float64), 1)
            bw_med = sub["block_wcl_median_us"].dropna().to_numpy(dtype=np.float64)
            bw_str = f"{float(np.median(bw_med)):.1f}" if bw_med.size else "—"
            sigma_str = f"{float(np.mean(sub['sigma_us'].to_numpy(dtype=np.float64))):.1f}"
            dmr_str = f"{float(np.max(sub['dmr_1000_pct'].to_numpy(dtype=np.float64))):.2f}"
            lines.append(
                f"| {series} | {tier} | {n_runs} | {cycles} | {wcl_str} | {bw_str} | {sigma_str} | {dmr_str} | {ref0} | {ref_ac} |"
            )

    lines.extend(
        [
            "",
            "## Load Evidence Per Run",
            "",
            "| File | Series | Tier | Rep | wlan0 rx Δ (B) | NET_RX Δ | IRQ total Δ | Top IRQ | Temp max °C | Freq min kHz | Throttled | Inferences / rate Hz / p50–p99 µs | PC traffic B/s / reconn | Loadcheck | IRQ / Wi-Fi affinity |",
            "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: | :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for _, r in long_df.iterrows():
        rx_b = f"{int(r['wlan0_rx_bytes_delta'])}" if pd.notna(r["wlan0_rx_bytes_delta"]) else "—"
        net_rx = f"{int(r['softirq_net_rx_delta'])}" if pd.notna(r["softirq_net_rx_delta"]) else "—"
        irq_tot = f"{int(r['irq_total_delta'])}" if pd.notna(r["irq_total_delta"]) else "—"
        top1 = str(r["top5_irqs"]).split("; ")[0] if str(r["top5_irqs"]) else "—"
        tmax = f"{float(r['temp_max_c']):.1f}" if pd.notna(r["temp_max_c"]) else "—"
        fmin = f"{float(r['freq_min_khz']):.0f}" if pd.notna(r["freq_min_khz"]) else "—"
        throt = str(r["throttled"]) if r["throttled"] is not None and pd.notna(r["throttled"]) else "—"
        if pd.notna(r["infer_count"]):
            rate_s = f"{float(r['infer_rate_hz']):.2f}" if pd.notna(r["infer_rate_hz"]) else "—"
            inf_s = f"{int(r['infer_count'])} / {rate_s} / {float(r['infer_p50_us']):.0f}–{float(r['infer_p99_us']):.0f}"
        else:
            inf_s = "—"
        if pd.notna(r["pc_avg_rate_Bps"]):
            pc_s = f"{float(r['pc_avg_rate_Bps']):.0f} / {int(r['pc_reconnects'])}"
        else:
            pc_s = "—"
        lc_s = str(r["loadcheck"]) if str(r["loadcheck"]) else "—"
        aff_parts = [p for p in (str(r["irqs_moved"]), str(r["wifi_irq"])) if p]
        aff_s = "; ".join(aff_parts) if aff_parts else "—"
        lines.append(
            f"| {r['file']} | {r['series']} | {r['tier']} | {int(r['rep'])} | {rx_b} | {net_rx} | {irq_tot} | {top1} | {tmax} | {fmin} | {throt} | {inf_s} | {pc_s} | {lc_s} | {aff_s} |"
        )

    lines.extend(
        [
            "",
            "**Relative lateness definition:** For Linux runs (`A`, `B`, `B-iso`), relative lateness is "
            "`L_rel = L_abs - min(L_abs)` within each run (wake-up floor `floor_us = min(L_abs)` subtracted). "
            "For Config C runs, lateness is wake-only (`wake_cyc` @ 160 MHz) relative to each run's best-case cycle "
            "using a least-squares fitted period (`analyze_latency.load_run(..., period_mode='fit')`).",
            "",
            "**Run length & block comparability:** Linux Phase 6a runs span 180,000 cycles (30 min), while Config C runs "
            "span 10,000 cycles. Splitting every run into consecutive 10,000-cycle blocks (`block_wcl_median_us`, "
            "`block_wcl_max_us`) places Linux and Config C maxima on the same 10,000-cycle horizon.",
            "",
            "**Background CNN workload:** The ONNX 1D-CNN model uses fixed-seed random weights on purpose as realistic "
            "background compute/memory/disk load only, not as a bearing-fault classifier.",
            "",
            "**CPU governor:** Linux runs lock all cores to `performance` during measurement (`run_benchmark_6r.sh`), "
            "whereas Config C runs retain the board default `schedutil` governor.",
            "",
        ]
    )
    return "\n".join(lines)


def _plot_block_wcl(records: list[dict], ref_map: dict[tuple[str, str], tuple[str, float]], out_dir: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update(
        {
            "figure.facecolor": "#ffffff",
            "axes.facecolor": "#ffffff",
            "savefig.facecolor": "#ffffff",
            "font.size": 9,
            "axes.grid": True,
            "grid.color": "#e4e3df",
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )

    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    tier_offsets = {"rnet": -0.14, "rdeploy": 0.14}
    tier_markers = {"rnet": "o", "rdeploy": "s"}

    seen_labels: set[str] = set()
    has_points = False

    for idx, series in enumerate(SERIES_ORDER):
        color = SERIES_COLORS.get(series, "#333333")
        for tier in TIERS:
            pts: list[float] = []
            for r in records:
                if r["series"] == series and r["tier"] == tier:
                    bw = r.get("_block_wcls")
                    if bw is not None and bw.size > 0:
                        pts.extend(float(v) for v in bw)
            if pts:
                has_points = True
                xs = [idx + tier_offsets[tier]] * len(pts)
                ys = [max(v, 0.1) for v in pts]
                lbl = f"{tier} blocks" if f"{tier} blocks" not in seen_labels else "_nolegend_"
                seen_labels.add(f"{tier} blocks")
                ax.scatter(
                    xs,
                    ys,
                    color=color,
                    marker=tier_markers[tier],
                    s=34,
                    alpha=0.8,
                    edgecolors="#ffffff",
                    linewidths=0.4,
                    label=lbl,
                    zorder=4,
                )

        # Reference horizontal markers for tier 0 and allcore from Phase 5d
        for ref_tier, ls_style, ref_lbl in (("0", ":", "Ref 0% mean WCL"), ("allcore", "-.", "Ref all-core mean WCL")):
            ref_entry = ref_map.get((series, ref_tier))
            if ref_entry is not None and np.isfinite(ref_entry[1]):
                has_points = True
                lbl = ref_lbl if ref_lbl not in seen_labels else "_nolegend_"
                seen_labels.add(ref_lbl)
                ax.hlines(
                    max(ref_entry[1], 0.1),
                    idx - 0.30,
                    idx + 0.30,
                    colors=color,
                    linestyles=ls_style,
                    linewidth=1.5,
                    label=lbl,
                    zorder=3,
                )

    ax.axhline(1000.0, color="#52514e", lw=1.0, ls="--", zorder=2)
    ax.text(len(SERIES_ORDER) - 0.55, 1000.0, "1 ms deadline", fontsize=8, color="#52514e", va="bottom", ha="right")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_xticks(range(len(SERIES_ORDER)), SERIES_ORDER)
    ax.set_xlim(-0.5, len(SERIES_ORDER) - 0.5)
    ax.set_xlabel("Configuration series")
    ax.set_ylabel("10,000-cycle block WCL (µs)")
    ax.set_title("Phase 6a realistic-load block WCL vs Phase 5d references", fontsize=10)
    if has_points:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), fontsize=8, ncol=4)
    fig.tight_layout()
    out_path = out_dir / "block_wcl.png"
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out_path


def compare_realload(raw_dir: Path, ref_csv: Path, out_dir: Path) -> tuple[pd.DataFrame, str, Path]:
    records = _collect_realload_runs(raw_dir)
    ref_map = _load_reference_wcl(ref_csv)

    columns = [
        "series",
        "tier",
        "rep",
        "file",
        "n",
        "sigma_us",
        "p999_us",
        "wcl_us",
        "dmr_1000_pct",
        "dmr_200_pct",
        "wcl_abs_us",
        "dmr_1000_abs_pct",
        "floor_us",
        "n_blocks",
        "block_wcl_median_us",
        "block_wcl_max_us",
        "irq_total_per_cpu",
        "irq_total_delta",
        "top5_irqs",
        "softirq_net_rx_delta",
        "softirq_net_rx_per_cpu",
        "softirq_net_tx_delta",
        "softirq_net_tx_per_cpu",
        "softirq_block_delta",
        "softirq_block_per_cpu",
        "softirq_timer_delta",
        "softirq_timer_per_cpu",
        "wlan0_rx_bytes_delta",
        "wlan0_rx_packets_delta",
        "wlan0_tx_bytes_delta",
        "wlan0_tx_packets_delta",
        "pswpin_delta",
        "pswpout_delta",
        "pgmajfault_delta",
        "temp_max_c",
        "freq_min_khz",
        "throttled",
        "infer_count",
        "infer_rate_hz",
        "infer_p50_us",
        "infer_p99_us",
        "pc_avg_rate_Bps",
        "pc_reconnects",
        "loadcheck",
        "irqs_moved",
        "wifi_irq",
    ]
    long_rows = [{k: r.get(k) for k in columns} for r in records]
    long_df = pd.DataFrame(long_rows, columns=columns)

    out_dir.mkdir(parents=True, exist_ok=True)
    long_csv = out_dir / "realload_long.csv"
    long_df.to_csv(long_csv, index=False, float_format="%.4f")

    md_text = _build_markdown(long_df, ref_map)
    md_path = out_dir / "realload.md"
    md_path.write_text(md_text, encoding="utf-8")

    chart_path = _plot_block_wcl(records, ref_map, out_dir)
    print(f"Wrote {long_csv}")
    print(f"Wrote {md_path}")
    print(f"Wrote {chart_path}")
    return long_df, md_text, chart_path


def main(argv: list[str] | None = None) -> int:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=repo / "results" / "raw")
    parser.add_argument("--ref", type=Path, default=repo / "results" / "phase5d" / "compare_long.csv")
    parser.add_argument("--out", type=Path, default=repo / "results" / "phase6a")
    args = parser.parse_args(argv)
    compare_realload(args.raw, args.ref, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

