#!/usr/bin/env bash
# Archive expired and completed contracts.
#
# Usage: scripts/archive_contracts.sh [-n] [-i] [-s STORAGE_DIR] [-f contracts.csv]
#   -n        dry run: show what would be archived, change nothing
#   -i        create demo contract documents in STORAGE_DIR/active first
#   -s DIR    document storage root (default output/storage)
#   -f FILE   contract register (default data/contracts.csv)
#
# Each document STORAGE/active/<id>.txt whose contract is Expired or Completed
# is moved to STORAGE/archive/<YYYY-MM>/ and the month folder is compressed
# into STORAGE/archive/<YYYY-MM>.tar.gz.

set -euo pipefail
source "$(dirname "$0")/common.sh"

dry_run=false
init_demo=false
storage="$PROJECT_ROOT/output/storage"
file="$CONTRACTS_FILE"

while getopts "nis:f:h" opt; do
    case "$opt" in
        n) dry_run=true ;;
        i) init_demo=true ;;
        s) storage="$OPTARG" ;;
        f) file="$OPTARG" ;;
        h) sed -n '2,12p' "$0"; exit 0 ;;
        *) die "unknown option; use -h for help" ;;
    esac
done

require_file "$file"
active_dir="$storage/active"
month=$(date +%Y-%m)
archive_dir="$storage/archive/$month"

create_demo_documents() {
    mkdir -p "$active_dir"
    local count=0
    while IFS=, read -r id title party expiry status owner; do
        printf 'Contract: %s\nTitle: %s\nCounterparty: %s\nExpiry: %s\nOwner: %s\n' \
            "$id" "$title" "$party" "$expiry" "$owner" > "$active_dir/$id.txt"
        count=$((count + 1))
    done < <(tail -n +2 "$file" | tr -d '\r')
    log INFO "created $count demo documents in $active_dir"
}

archive_one() {
    # archive_one CONTRACT_ID STATUS
    local id=$1 status=$2 doc="$active_dir/$1.txt"
    if [[ ! -f "$doc" ]]; then
        log WARN "$id is $status but has no document in $active_dir"
        return 1
    fi
    if $dry_run; then
        echo "would archive $id ($status)"
    else
        mkdir -p "$archive_dir"
        mv "$doc" "$archive_dir/"
        log INFO "archived $id ($status) -> $archive_dir"
    fi
}

$init_demo && create_demo_documents
[[ -d "$active_dir" ]] || die "no active storage at $active_dir (use -i to create demo documents)"

archived=0
skipped=0
while IFS=, read -r id title party expiry status owner; do
    case "$status" in
        Expired|Completed)
            if archive_one "$id" "$status"; then
                archived=$((archived + 1))
            else
                skipped=$((skipped + 1))
            fi
            ;;
        *) ;;   # Active contracts stay where they are
    esac
done < <(tail -n +2 "$file" | tr -d '\r')

if ! $dry_run && (( archived > 0 )); then
    tar -czf "$storage/archive/$month.tar.gz" -C "$storage/archive" "$month"
    log INFO "compressed $archive_dir -> $storage/archive/$month.tar.gz"
fi

mode=$($dry_run && echo " (dry run)" || true)
echo "Archival complete$mode: $archived archived, $skipped skipped," \
     "$(find "$active_dir" -maxdepth 1 -name '*.txt' | wc -l | tr -d ' ') still active."
