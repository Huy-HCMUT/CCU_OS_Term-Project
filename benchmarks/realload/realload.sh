#!/usr/bin/env bash
#
# realload.sh - Phase 6a board-side realistic load controller (R-net, R-deploy and R-both)
#
# Subcommands:
#   start <rnet|rdeploy|rboth> <label> <outdir> <pc_ip> [iso]
#   check <rnet|rdeploy|rboth>
#   stop
#   status
#

set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/home/arduino/CCU_OS_Term-Project}"
STATE_FILE="/tmp/realload.state"
CONTAINER_NAME="realload_analytics"
IMAGE_NAME="realload:1"

write_counters() {
    local out_file="$1"
    {
        echo "#TIME"
        date +%s.%N
        echo "#INTERRUPTS"
        cat /proc/interrupts 2>/dev/null || true
        echo "#SOFTIRQS"
        cat /proc/softirqs 2>/dev/null || true
        echo "#NETDEV"
        cat /proc/net/dev 2>/dev/null || true
        echo "#VMSTAT"
        cat /proc/vmstat 2>/dev/null || true
        echo "#END"
    } > "${out_file}"
}

run_sampler() {
    local thermal_csv="$1"
    if [ ! -f "${thermal_csv}" ] || [ ! -s "${thermal_csv}" ]; then
        echo "time_s,busy_cpu0,busy_cpu1,busy_cpu2,busy_cpu3,temp_max_c,freq_cpu0_khz,freq_cpu1_khz,freq_cpu2_khz,freq_cpu3_khz,cooling_states" > "${thermal_csv}"
    fi

    while true; do
        local s1 s2 ts busy_csv temp_max freqs cstates c_val
        s1="$(grep '^cpu[0-3] ' /proc/stat 2>/dev/null || true)"
        sleep 10
        s2="$(grep '^cpu[0-3] ' /proc/stat 2>/dev/null || true)"
        ts="$(date +%s.%N)"

        busy_csv="$(
            {
                printf '%s\n' "${s1}"
                echo "---"
                printf '%s\n' "${s2}"
            } | awk '
            /^---$/ { phase = 2; next }
            phase != 2 {
                for (i = 2; i <= 9; i++) a[$1, i] = $i + 0
                next
            }
            {
                tot = 0
                for (i = 2; i <= 9; i++) {
                    d[i] = ($i + 0) - a[$1, i]
                    tot += d[i]
                }
                idle = d[5] + d[6]
                if (tot > 0) {
                    pct[$1] = sprintf("%.1f", 100.0 * (tot - idle) / tot)
                } else {
                    pct[$1] = ""
                }
            }
            END {
                printf "%s,%s,%s,%s", pct["cpu0"], pct["cpu1"], pct["cpu2"], pct["cpu3"]
            }
            '
        )"

        temp_max="$(awk 'BEGIN { max = -1 } /^[0-9]+$/ { if ($1 + 0 > max) max = $1 + 0 } END { if (max >= 0) printf "%.1f", max / 1000.0 }' /sys/class/thermal/thermal_zone*/temp 2>/dev/null || true)"

        freqs=""
        for idx in 0 1 2 3; do
            local fpath="/sys/devices/system/cpu/cpu${idx}/cpufreq/scaling_cur_freq"
            local fval=""
            if [ -r "${fpath}" ]; then
                fval="$(cat "${fpath}" 2>/dev/null || true)"
            fi
            if [ "${idx}" -eq 0 ]; then
                freqs="${fval}"
            else
                freqs="${freqs},${fval}"
            fi
        done

        cstates=""
        for cpath in /sys/class/thermal/cooling_device*/cur_state; do
            if [ -r "${cpath}" ]; then
                c_val="$(cat "${cpath}" 2>/dev/null || true)"
                if [ -z "${cstates}" ]; then
                    cstates="${c_val}"
                else
                    cstates="${cstates};${c_val}"
                fi
            fi
        done

        echo "${ts},${busy_csv},${temp_max},${freqs},${cstates}" >> "${thermal_csv}"
    done
}

cmd_start() {
    if [ "$#" -lt 4 ] || [ "$#" -gt 5 ]; then
        echo "Usage: $0 start <rnet|rdeploy|rboth> <label> <outdir> <pc_ip> [iso]" >&2
        exit 1
    fi
    local tier="$1"
    local label="$2"
    local outdir="$3"
    local pc_ip="$4"
    local iso="${5:-}"

    if [ "${tier}" != "rnet" ] && [ "${tier}" != "rdeploy" ] && [ "${tier}" != "rboth" ]; then
        echo "ERROR: unknown tier '${tier}', expected rnet, rdeploy or rboth" >&2
        exit 1
    fi
    if [ -n "${iso}" ] && [ "${iso}" != "iso" ]; then
        echo "ERROR: optional 5th argument must be 'iso', got '${iso}'" >&2
        exit 1
    fi
    if [ -e "${STATE_FILE}" ]; then
        echo "ERROR: realload is already running (${STATE_FILE} exists)" >&2
        exit 1
    fi

    local width=""
    if [ "${tier}" = "rdeploy" ] || [ "${tier}" = "rboth" ]; then
        local width_file="${ROOT_DIR}/benchmarks/realload/model_width.txt"
        if [ ! -r "${width_file}" ]; then
            echo "ERROR: missing ${width_file}; run calibration first" >&2
            exit 1
        fi
        width="$(tr -d ' \t\r\n' < "${width_file}")"
        if ! [[ "${width}" =~ ^[0-9]+$ ]]; then
            echo "ERROR: invalid width '${width}' in ${width_file}" >&2
            exit 1
        fi
    fi

    mkdir -p "${outdir}"
    write_counters "${outdir}/counters_${label}_before.txt"

    local sink_pid=""
    if [ "${tier}" = "rnet" ] || [ "${tier}" = "rboth" ]; then
        if [ "${iso}" = "iso" ]; then
            nohup taskset -c 0-2 socat -u TCP-LISTEN:5557,reuseaddr,fork OPEN:/dev/null >/dev/null 2>&1 &
        else
            nohup socat -u TCP-LISTEN:5557,reuseaddr,fork OPEN:/dev/null >/dev/null 2>&1 &
        fi
        sink_pid="$!"
    fi
    if [ "${tier}" = "rdeploy" ] || [ "${tier}" = "rboth" ]; then
        local -a docker_args=(
            -d --rm --name "${CONTAINER_NAME}"
            --user "$(id -u):$(id -g)"
            -p 5555:5555
            -v "${outdir}:/out"
        )
        if [ "${iso}" = "iso" ]; then
            docker_args+=(--cpuset-cpus 0-2)
        fi
        if ! docker run "${docker_args[@]}" "${IMAGE_NAME}" \
            --label "${label}" --pc-ip "${pc_ip}" --threads 3 --width "${width}" --out /out >/dev/null; then
            if [ -n "${sink_pid}" ]; then
                pkill -P "${sink_pid}" 2>/dev/null || true
                kill "${sink_pid}" 2>/dev/null || true
            fi
            echo "ERROR: docker run failed for ${tier}" >&2
            exit 1
        fi
    fi

    local sampler_pid=""
    if [ "${iso}" = "iso" ]; then
        nohup setsid taskset -c 0-2 bash -c "$(declare -f run_sampler); run_sampler \"\$1\"" _ "${outdir}/thermal_${label}.csv" >/dev/null 2>&1 &
    else
        nohup setsid bash -c "$(declare -f run_sampler); run_sampler \"\$1\"" _ "${outdir}/thermal_${label}.csv" >/dev/null 2>&1 &
    fi
    sampler_pid="$!"

    cat > "${STATE_FILE}" <<EOF
tier=${tier}
label=${label}
outdir=${outdir}
sink_pid=${sink_pid}
sampler_pid=${sampler_pid}
EOF

    echo "[realload] started ${tier} ${label}"
}

read_rx_bytes() {
    local rx=""
    rx="$(cat /sys/class/net/wlan0/statistics/rx_bytes 2>/dev/null || true)"
    if [[ "${rx}" =~ ^[0-9]+$ ]]; then
        echo "${rx}"
    else
        echo 0
    fi
}

read_status_count() {
    local status_file="$1"
    if [ -r "${status_file}" ]; then
        awk -F= '/^count=/{val=$2; found=1; exit} END{print (found && val ~ /^[0-9]+$/ ? val : 0)}' "${status_file}" 2>/dev/null || echo 0
    else
        echo 0
    fi
}

cmd_check() {
    if [ "$#" -ne 1 ]; then
        echo "Usage: $0 check <rnet|rdeploy|rboth>" >&2
        exit 1
    fi
    local want_tier="$1"
    if [ "${want_tier}" != "rnet" ] && [ "${want_tier}" != "rdeploy" ] && [ "${want_tier}" != "rboth" ]; then
        echo "ERROR: unknown tier '${want_tier}', expected rnet, rdeploy or rboth" >&2
        exit 1
    fi
    if [ ! -r "${STATE_FILE}" ]; then
        echo "LOADCHECK FAIL tier=${want_tier} rx_Bps=0 inferences=-"
        exit 1
    fi

    local tier="" label="" outdir="" sink_pid="" sampler_pid=""
    # shellcheck disable=SC1090
    source "${STATE_FILE}"
    if [ "${tier:-}" != "${want_tier}" ]; then
        echo "LOADCHECK FAIL tier=${want_tier} rx_Bps=0 inferences=- (running load is '${tier:-none}')"
        exit 1
    fi

    local rx1 rx2 inf1=0 inf2=0 rx_bps inf_delta inf_str ok=0
    rx1="$(read_rx_bytes)"
    if [ "${tier}" = "rdeploy" ] || [ "${tier}" = "rboth" ]; then
        inf1="$(read_status_count "${outdir}/analytics_${label}_status.txt")"
    fi
    sleep 5
    rx2="$(read_rx_bytes)"
    if [ "${tier}" = "rdeploy" ] || [ "${tier}" = "rboth" ]; then
        inf2="$(read_status_count "${outdir}/analytics_${label}_status.txt")"
    fi

    rx_bps=$(( (rx2 - rx1) / 5 ))
    if [ "${tier}" = "rdeploy" ]; then
        inf_delta=$(( inf2 - inf1 ))
        inf_str="${inf_delta}"
        if [ "${rx_bps}" -ge 30000 ] && [ "${inf_delta}" -ge 30 ]; then
            ok=1
        fi
    elif [ "${tier}" = "rboth" ]; then
        inf_delta=$(( inf2 - inf1 ))
        inf_str="${inf_delta}"
        if [ "${rx_bps}" -ge 1000000 ] && [ "${inf_delta}" -ge 30 ]; then
            ok=1
        fi
    else
        inf_str="-"
        if [ "${rx_bps}" -ge 1000000 ]; then
            ok=1
        fi
    fi

    if [ "${ok}" -eq 1 ]; then
        echo "LOADCHECK OK tier=${tier} rx_Bps=${rx_bps} inferences=${inf_str}"
        exit 0
    fi
    echo "LOADCHECK FAIL tier=${tier} rx_Bps=${rx_bps} inferences=${inf_str}"
    exit 1
}

cmd_stop() {
    if [ ! -r "${STATE_FILE}" ]; then
        echo "[realload] nothing running"
        exit 0
    fi

    local tier="" label="" outdir="" sink_pid="" sampler_pid=""
    # shellcheck disable=SC1090
    source "${STATE_FILE}"

    if { [ "${tier}" = "rnet" ] || [ "${tier}" = "rboth" ]; } && [ -n "${sink_pid}" ]; then
        pkill -P "${sink_pid}" 2>/dev/null || true
        kill "${sink_pid}" 2>/dev/null || true
        wait "${sink_pid}" 2>/dev/null || true
    fi
    if [ "${tier}" = "rdeploy" ] || [ "${tier}" = "rboth" ]; then
        docker stop -t 10 "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi

    if [ -n "${sampler_pid}" ]; then
        pkill -P "${sampler_pid}" 2>/dev/null || true
        kill "${sampler_pid}" 2>/dev/null || true
        wait "${sampler_pid}" 2>/dev/null || true
    fi

    write_counters "${outdir}/counters_${label}_after.txt"
    rm -f "${STATE_FILE}"
}

cmd_status() {
    if [ -r "${STATE_FILE}" ]; then
        cat "${STATE_FILE}"
        exit 0
    fi
    echo "not running"
    exit 3
}

SUBCMD="${1:-}"
if [ -z "${SUBCMD}" ]; then
    echo "Usage: $0 <start|check|stop|status> ..." >&2
    exit 1
fi
shift

case "${SUBCMD}" in
    start)
        cmd_start "$@"
        ;;
    check)
        cmd_check "$@"
        ;;
    stop)
        cmd_stop
        ;;
    status)
        cmd_status
        ;;
    *)
        echo "ERROR: unknown subcommand '${SUBCMD}'" >&2
        exit 1
        ;;
esac
