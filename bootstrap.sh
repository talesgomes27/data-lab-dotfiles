#!/bin/sh
# O bootstrap não baixa nem executa instaladores remotos.
set -eu
command -v bash >/dev/null 2>&1 || {
    echo 'Requer Bash >=4.4.' >&2
    exit 3
}
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)
if [ "$#" -eq 0 ]; then set -- plan; fi
exec bash "$root/bin/devshell" "$@"
