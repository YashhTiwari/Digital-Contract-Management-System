#!/usr/bin/env bash
# Due-date reminders for active contracts.
#
# Usage: scripts/due_reminder.sh [-d DAYS] [-t YYYY-MM-DD] [-f contracts.csv]
#   -d DAYS   remind about contracts expiring within DAYS days (default 7)
#   -t DATE   treat DATE as today (useful for demos and tests)
#   -f FILE   contract register (default data/contracts.csv)
#
# Exit status: 0 nothing urgent, 2 at least one contract is overdue.
# Schedule it daily with cron:  0 9 * * 1-5  /path/to/scripts/due_reminder.sh

set -euo pipefail
source "$(dirname "$0")/common.sh"

window=7
today=$(date +%F)
file="$CONTRACTS_FILE"

while getopts "d:t:f:h" opt; do
    case "$opt" in
        d) window="$OPTARG" ;;
        t) today="$OPTARG" ;;
        f) file="$OPTARG" ;;
        h) sed -n '2,11p' "$0"; exit 0 ;;
        *) die "unknown option; use -h for help" ;;
    esac
done

[[ "$window" =~ ^[0-9]+$ ]] || die "DAYS must be a whole number, got '$window'"
require_file "$file"

report_dir="$PROJECT_ROOT/output/reminders"
report="$report_dir/reminders_$today.txt"
mkdir -p "$report_dir"

classify() {
    # classify DAYS_LEFT -> urgency label
    local left=$1
    if   (( left < 0 ));  then echo "OVERDUE"
    elif (( left <= 2 )); then echo "URGENT"
    else                       echo "UPCOMING"
    fi
}

overdue=0
due_soon=0
{
    echo "Contract due-date reminders  (today: $today, window: $window days)"
    printf '%-14s %-28s %-20s %-11s %6s  %s\n' \
        "Contract" "Title" "Counterparty" "Expiry" "Days" "Level"
    printf '%.0s-' {1..92}; echo
} > "$report"

# Skip the header line, then read one contract per line.
while IFS=, read -r id title party expiry status owner; do
    [[ "$status" == "Active" ]] || continue
    left=$(days_between "$today" "$expiry")
    (( left <= window )) || continue

    level=$(classify "$left")
    [[ "$level" == "OVERDUE" ]] && overdue=$((overdue + 1))
    due_soon=$((due_soon + 1))
    printf '%-14s %-28s %-20s %-11s %6d  %s (notify %s)\n' \
        "$id" "$title" "$party" "$expiry" "$left" "$level" "$owner" >> "$report"
done < <(tail -n +2 "$file" | tr -d '\r')

echo >> "$report"
echo "Total: $due_soon contract(s) need attention, $overdue overdue." >> "$report"

cat "$report"
log INFO "reminders: $due_soon due within $window days, $overdue overdue -> $report"

if (( overdue > 0 )); then
    exit 2
fi
