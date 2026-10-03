#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source-path=SCRIPTDIR
# shellcheck source=wine-common.sh
source "$SCRIPT_DIR/wine-common.sh"
[[ $# -ge 1 && $# -le 2 && -f "$1" ]] || {
    echo 'Usage: wine-run-test.sh driver.sys [aegis_pushlock_client.exe]' >&2; exit 2;
}
driver_source=$(cd -- "$(dirname -- "$1")" && pwd -P)/$(basename -- "$1")
client_source=''
if [[ $# == 2 ]]; then
    [[ -f "$2" ]] || { echo 'AEGIS: Client image missing.' >&2; exit 2; }
    client_source=$(cd -- "$(dirname -- "$2")" && pwd -P)/$(basename -- "$2")
fi
aegis_preflight
AEGIS_PYTHON=${AEGIS_PYTHON:-python3}
command -v "$AEGIS_PYTHON" >/dev/null || { echo 'AEGIS: Python 3.10+ is required.' >&2; exit 2; }
mkdir -p -- "${AEGIS_REPORT_DIR:-$SCRIPT_DIR/../reports}"
run_dir=$(mktemp -d "${AEGIS_REPORT_DIR:-$SCRIPT_DIR/../reports}/pushlock-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
AEGIS_LOG_FILE="$run_dir/wine.log"
export AEGIS_LOG_FILE AEGIS_WINE_BIN AEGIS_TIMEOUT_SECONDS
: >"$AEGIS_LOG_FILE"
mkdir -- "$WINEPREFIX/.aegis-pushlock.lock" 2>/dev/null || {
    echo 'AEGIS: Another run or a stale prefix lock exists.' >&2; exit 2;
}
export AEGIS_LOCK_HELD=1
installed=0
install_rc=255
start_rc=255
client_rc=255
stop_rc=255
delete_rc=255
finalize() {
    local original_rc=$?
    trap - EXIT INT TERM
    set +e
    if (( installed == 1 )); then
        aegis_sc stop "$AEGIS_SERVICE"
        stop_rc=$?
        # 1062 means already stopped, which is expected after a load failure.
        if (( stop_rc != 0 )) && aegis_sc_has_error 1062; then stop_rc=0; fi
        aegis_sc delete "$AEGIS_SERVICE"
        delete_rc=$?
        # Keep the image for recovery if unload/removal could not be confirmed.
        if (( stop_rc == 0 && delete_rc == 0 )); then rm -f -- "$AEGIS_DRIVER_DEST"; fi
    fi
    rmdir -- "$WINEPREFIX/.aegis-pushlock.lock"
    printf 'AEGIS_HARNESS: install_exit_code=%s start_exit_code=%s client_exit_code=%s stop_exit_code=%s delete_exit_code=%s\n' \
        "$install_rc" "$start_rc" "$client_rc" "$stop_rc" "$delete_rc" >>"$AEGIS_LOG_FILE"
    "$AEGIS_PYTHON" "$SCRIPT_DIR/write-run-metadata.py" \
        "$run_dir/metadata.json" "$driver_source" "$client_source" "$WINEPREFIX" \
        "$run_dir/wine-version.txt" "$install_rc" "$start_rc" "$client_rc" "$stop_rc" "$delete_rc" "$original_rc"
    local metadata_rc=$?
    local parse_args=("$AEGIS_LOG_FILE" --metadata "$run_dir/metadata.json" --output "$run_dir/report.json")
    if [[ -f "$run_dir/client.stdout" ]]; then
        parse_args+=(--client-output "$run_dir/client.stdout" --client-exit-code "$client_rc")
    fi
    "$AEGIS_PYTHON" "$SCRIPT_DIR/parse-wine-log.py" "${parse_args[@]}"
    local parse_rc=$?
    "$AEGIS_PYTHON" "$SCRIPT_DIR/aegis-report.py" "$run_dir/report.json" --output "$run_dir/report.txt"
    local report_rc=$?
    if (( metadata_rc != 0 || parse_rc == 2 || report_rc == 2 )); then
        printf 'AEGIS PushLock: FAIL (report generation error)\nLogs: %s\n' "$run_dir"
        exit 2
    fi
    local result=FAIL
    if (( original_rc == 0 && parse_rc == 0 && report_rc == 0 )); then result=PASS; fi
    printf 'AEGIS PushLock: %s\nReports and raw logs: %s\n' "$result" "$run_dir"
    [[ "$result" == PASS ]] && exit 0
    exit 1
}
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
timeout --kill-after=5s "${AEGIS_TIMEOUT_SECONDS}s" "$AEGIS_WINE_BIN" --version >"$run_dir/wine-version.txt" 2>&1 || true
install_rc=0
bash "$SCRIPT_DIR/wine-install-driver.sh" "$driver_source" >>"$AEGIS_LOG_FILE" 2>&1 || install_rc=$?
if (( install_rc != 0 )); then exit 1; fi
installed=1
start_rc=0
aegis_sc start "$AEGIS_SERVICE" || start_rc=$?
if (( start_rc != 0 )); then
    printf 'AEGIS_HARNESS: service start failed (exit=%s)\n' "$start_rc" >>"$AEGIS_LOG_FILE"
fi
if [[ -n "$client_source" && "$start_rc" == 0 ]]; then
    client_rc=0
    aegis_wine "$client_source" >"$run_dir/client.stdout" 2>>"$AEGIS_LOG_FILE" || client_rc=$?
else
    echo 'AEGIS_HARNESS: client not run; IOCTL NOT VERIFIED' >>"$AEGIS_LOG_FILE"
fi
# Cleanup and reporting are always handled by the EXIT trap.
