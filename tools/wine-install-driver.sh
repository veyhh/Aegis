#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source-path=SCRIPTDIR
# shellcheck source=wine-common.sh
source "$SCRIPT_DIR/wine-common.sh"
[[ $# == 1 && -f "$1" ]] || { echo 'Usage: wine-install-driver.sh /path/aegis_pushlock_test.sys' >&2; exit 2; }
aegis_preflight
if [[ -z ${AEGIS_LOG_FILE:-} ]]; then
    mkdir -p -- "$SCRIPT_DIR/../reports"
    AEGIS_LOG_FILE=$(mktemp "$SCRIPT_DIR/../reports/install.XXXXXX.log")
fi
own_lock=0
copied=0
creating=0
installed=0
finish_install() {
    local rc=$?
    trap - EXIT
    local cleanup_ok=1 stop_code=0 delete_code=0
    if (( creating == 1 && installed == 0 )); then
        aegis_sc stop "$AEGIS_SERVICE" || stop_code=$?
        if (( stop_code != 0 )) && ! aegis_sc_has_error 1062 && ! aegis_sc_has_error 1060; then cleanup_ok=0; fi
        aegis_sc delete "$AEGIS_SERVICE" || delete_code=$?
        if (( delete_code != 0 )) && ! aegis_sc_has_error 1060; then cleanup_ok=0; fi
    fi
    if (( copied == 1 && installed == 0 && cleanup_ok == 1 )); then rm -f -- "$AEGIS_DRIVER_DEST"; fi
    if (( own_lock == 1 )); then rmdir -- "$WINEPREFIX/.aegis-pushlock.lock"; fi
    exit "$rc"
}
trap finish_install EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ ${AEGIS_LOCK_HELD:-0} != 1 ]]; then
    mkdir -- "$WINEPREFIX/.aegis-pushlock.lock" 2>/dev/null || {
        echo 'AEGIS: Another run or a stale prefix lock exists.' >&2; exit 2;
    }
    own_lock=1
fi
query_rc=0
aegis_sc query "$AEGIS_SERVICE" || query_rc=$?
if (( query_rc == 0 )); then
    echo 'AEGIS: Existing AEGIS service found; stop/remove it explicitly before installing.' >&2
    exit 2
fi
if ! aegis_sc_has_error 1060; then
    echo 'AEGIS: Could not prove the service is absent; inspect the install log.' >&2
    exit 2
fi
[[ ! -e "$AEGIS_DRIVER_DEST" && ! -L "$AEGIS_DRIVER_DEST" ]] || {
    echo 'AEGIS: Refusing to overwrite an existing driver image.' >&2; exit 2;
}
copied=1
cp -- "$1" "$AEGIS_DRIVER_DEST"
creating=1
aegis_sc create "$AEGIS_SERVICE" type= kernel start= demand error= normal \
    binPath= 'C:\windows\system32\drivers\aegis_pushlock_test.sys'
installed=1
printf 'AEGIS: Driver installed (Type=1). Log: %s\n' "$AEGIS_LOG_FILE"
