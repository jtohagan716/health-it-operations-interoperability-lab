#!/bin/sh

DURATION="${1:-300}"
INTERVAL="${2:-1}"

START_EPOCH=$(date +%s)
SAMPLE=0
CLK_TCK=$(getconf CLK_TCK 2>/dev/null || echo 100)

echo "schema=openemr.latency.observer.v5"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "duration_seconds=$DURATION"
echo "interval_seconds=$INTERVAL"
echo "clk_tck=$CLK_TCK"

while :; do
    NOW_EPOCH=$(date +%s)
    ELAPSED=$((NOW_EPOCH - START_EPOCH))

    if [ "$ELAPSED" -ge "$DURATION" ]; then
        break
    fi

    echo
    echo "===== SAMPLE $SAMPLE ====="
    echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "elapsed_seconds=$ELAPSED"

    echo "--- CPU_STAT ---"
    cat /sys/fs/cgroup/cpu.stat

    echo "--- MEMORY_CURRENT ---"
    cat /sys/fs/cgroup/memory.current 2>/dev/null || true

    echo "--- MEMORY_EVENTS ---"
    cat /sys/fs/cgroup/memory.events

    echo "--- IO_STAT ---"
    cat /sys/fs/cgroup/io.stat

    echo "--- CPU_PRESSURE ---"
    cat /sys/fs/cgroup/cpu.pressure 2>/dev/null || true

    echo "--- IO_PRESSURE ---"
    cat /sys/fs/cgroup/io.pressure 2>/dev/null || true

    echo "--- MEMORY_PRESSURE ---"
    cat /sys/fs/cgroup/memory.pressure 2>/dev/null || true

    echo "--- LOADAVG ---"
    cat /proc/loadavg

    echo "--- BACKGROUND_PROCESSES ---"

    BG_PIDS=$(ps -o pid,args | grep "background:services" | grep -v grep | sed -n 's/^ *\([0-9][0-9]*\) .*/\1/p')

    if [ -z "$BG_PIDS" ]; then
        echo "none"
    else
        for PID in $BG_PIDS; do
            ps -o pid,ppid,user,etime,stat,rss,args -p "$PID" 2>/dev/null || true

            if [ -r "/proc/$PID/stat" ]; then
                echo "--- PROCESS_STAT pid=$PID ---"
                cat "/proc/$PID/stat"
            fi

            if [ -r "/proc/$PID/io" ]; then
                echo "--- PROCESS_IO pid=$PID ---"
                cat "/proc/$PID/io"
            fi
        done
    fi

    SAMPLE=$((SAMPLE + 1))
    sleep "$INTERVAL"
done

echo
echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "samples=$SAMPLE"
