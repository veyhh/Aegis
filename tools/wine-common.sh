#!/usr/bin/env bash
# Shared helpers. This file is sourced, not an entry point.
AEGIS_SERVICE=aegis_pushlock_test
AEGIS_WINEDEBUG=+ntoskrnl,+module,+service

aegis_preflight() {
    : "${WINEPREFIX:?Set WINEPREFIX to an initialized, dedicated absolute prefix}"
    [[ "$WINEPREFIX" == /* && "$WINEPREFIX" != / ]] || {
        echo 'AEGIS: WINEPREFIX must be an absolute prefix directory.' >&2; return 2;
    }
    [[ -f "$WINEPREFIX/system.reg" && -d "$WINEPREFIX/drive_c/windows/system32/drivers" ]] || {
        echo 'AEGIS: Initialize the dedicated prefix with wineboot first.' >&2; return 2;
    }
    WINEPREFIX=$(cd -- "$WINEPREFIX" && pwd -P)
    export WINEPREFIX
    AEGIS_WINE_BIN=${AEGIS_WINE_BIN:-wine}
    AEGIS_TIMEOUT_SECONDS=${AEGIS_TIMEOUT_SECONDS:-30}
    [[ "$AEGIS_TIMEOUT_SECONDS" =~ ^[1-9][0-9]*$ ]] || {
        echo 'AEGIS: timeout must be a positive integer.' >&2; return 2;
    }
    command -v "$AEGIS_WINE_BIN" >/dev/null || { echo 'AEGIS: Wine executable unavailable.' >&2; return 2; }
    command -v timeout >/dev/null || { echo 'AEGIS: GNU timeout is required.' >&2; return 2; }
    local resolved_drivers
    resolved_drivers=$(cd -- "$WINEPREFIX/drive_c/windows/system32/drivers" && pwd -P)
    [[ "$resolved_drivers" == "$WINEPREFIX/"* ]] || {
        echo 'AEGIS: drivers directory resolves outside the selected prefix.' >&2; return 2;
    }
    AEGIS_DRIVER_DEST="$resolved_drivers/$AEGIS_SERVICE.sys"
    export AEGIS_DRIVER_DEST WINEDEBUG="$AEGIS_WINEDEBUG"
}

aegis_wine() {
    timeout --kill-after=5s "${AEGIS_TIMEOUT_SECONDS}s" "$AEGIS_WINE_BIN" "$@"
}

# Preserve each command's exact output so localized Wine sc errors can be checked
# by their numeric Windows error, rather than by translated English sentences.
aegis_sc() {
    AEGIS_SC_LOG=$(mktemp "${AEGIS_LOG_FILE}.sc.XXXXXX")
    local rc=0
    aegis_wine sc.exe "$@" >"$AEGIS_SC_LOG" 2>&1 || rc=$?
    cat -- "$AEGIS_SC_LOG" >>"$AEGIS_LOG_FILE"
    return "$rc"
}

aegis_sc_has_error() {
    grep -Eiq "(failed|error)[^0-9]*$1([^0-9]|$)" "$AEGIS_SC_LOG"
}
