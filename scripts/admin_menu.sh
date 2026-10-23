#!/usr/bin/env bash
# Menu-driven admin console for the Digital Contract Management System.

set -uo pipefail
source "$(dirname "$0")/common.sh"
cd "$PROJECT_ROOT" || exit 1
PY=$(python_cmd)

pause() { read -rp $'\nPress Enter to continue...' _; }

run_scheduler() {
    local policy
    read -rp "Policy (fcfs, sjf, srtf, rr, mlq, mlfq, edf) [srtf]: " policy
    "$PY" main.py --policy "${policy:-srtf}"
}

menu() {
    cat <<'EOF'

 ============================================
   Digital Contract Management System - Admin
 ============================================
  1) Contract due-date reminders
  2) Archive expired / completed contracts
  3) Run the request scheduler (one policy)
  4) Compare all scheduling policies + HTML report
  5) Concurrency and deadlock demos
  6) Server / system information
  7) Run the test suite
  0) Exit
EOF
}

while true; do
    menu
    read -rp "Choose an option: " choice
    case "$choice" in
        1) read -rp "Days ahead [7]: " d; scripts/due_reminder.sh -d "${d:-7}"; pause ;;
        2) scripts/archive_contracts.sh -i -n
           read -rp "Archive these now? [y/N]: " yes
           [[ "$yes" =~ ^[Yy]$ ]] && scripts/archive_contracts.sh
           pause ;;
        3) run_scheduler; pause ;;
        4) "$PY" main.py --compare --quantum-sweep 1,2,4,8 --html output/report.html; pause ;;
        5) "$PY" demo.py all; pause ;;
        6) scripts/system_info.sh; pause ;;
        7) "$PY" -m pytest -q; pause ;;
        0|q|Q) echo "Goodbye."; exit 0 ;;
        *) echo "Invalid option: $choice" ;;
    esac
done
