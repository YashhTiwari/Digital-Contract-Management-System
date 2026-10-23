#!/usr/bin/env bash
# Shared helpers for the admin scripts. Source it; do not run it.

# Project root = parent of this scripts/ directory.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACTS_FILE="${CONTRACTS_FILE:-$PROJECT_ROOT/data/contracts.csv}"
LOG_DIR="${LOG_DIR:-$PROJECT_ROOT/output/logs}"

log() {
    # log LEVEL MESSAGE... -> timestamped line on screen and in the admin log
    local level="$1"; shift
    local msg="$*"
    msg="${msg//$PROJECT_ROOT\//}"      # show paths relative to the project
    mkdir -p "$LOG_DIR"
    printf '%s [%-5s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$level" "$msg" \
        | tee -a "$LOG_DIR/admin.log"
}

die() {
    log ERROR "$*" >&2
    exit 1
}

to_epoch() {
    # to_epoch YYYY-MM-DD -> seconds since 1970 (GNU date)
    date -d "$1" +%s 2>/dev/null || die "invalid date: $1"
}

days_between() {
    # days_between FROM TO -> whole days from FROM to TO (negative if TO is earlier)
    local from to
    from=$(to_epoch "$1")
    to=$(to_epoch "$2")
    echo $(( (to - from) / 86400 ))
}

python_cmd() {
    # Prints the Python interpreter available on this machine.
    if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
        echo python3
    elif command -v python >/dev/null 2>&1; then
        echo python
    else
        die "Python 3 is required"
    fi
}

require_file() {
    [[ -f "$1" ]] || die "file not found: $1"
}
