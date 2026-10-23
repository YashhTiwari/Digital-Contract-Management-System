#!/usr/bin/env bash
# Snapshot of the server the contract system runs on: OS, kernel, CPUs,
# memory, load, processes and disk space. Each value comes from a system
# utility that in turn asks the kernel through system calls.

set -uo pipefail
source "$(dirname "$0")/common.sh"

section() { printf '\n%s\n' "== $1 =="; }

section "Operating system"
echo "Kernel       : $(uname -s) $(uname -r)"
echo "Machine      : $(uname -m)"
echo "Hostname     : $(hostname)"
if [[ -r /etc/os-release ]]; then
    echo "Distribution : $(. /etc/os-release && echo "$PRETTY_NAME")"
fi

section "CPU"
cpus=$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo "?")
echo "Logical CPUs : $cpus (includes hyper-threads)"
if [[ -r /proc/loadavg ]]; then
    read -r one five fifteen _ < /proc/loadavg
    echo "Load average : $one (1 min)  $five (5 min)  $fifteen (15 min)"
fi

section "Memory"
if command -v free >/dev/null 2>&1; then
    free -h | head -2
else
    echo "free(1) not available on this system"
fi

section "Processes"
total=$(ps -e 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
echo "Running processes: $total"
echo "Top 5 by CPU:"
ps -eo pid,ppid,stat,pcpu,comm --sort=-pcpu 2>/dev/null | head -6 \
    || ps | head -6

section "Disk (project folder)"
df -h "$PROJECT_ROOT" | tail -1 | awk '{print "Used " $3 " of " $2 " (" $5 ") on " $6}'
