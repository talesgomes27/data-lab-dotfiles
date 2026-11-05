#!/usr/bin/env bash
# Exclusivo de containers/runners descartáveis; nenhum uso sobre a HOME real.
set -euo pipefail
[[ ${HOME:-} == /tmp/foundry-* ]] || {
    echo 'Use HOME /tmp/foundry-* descartável.' >&2
    exit 2
}
umask 077
mkdir -p "$HOME"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export PATH="$HOME/.local/bin:$PATH"
for tool in chezmoi nu uv; do
    approval=$(./bin/devshell install --component "$tool" --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    ./bin/devshell install --component "$tool" --approve "$approval"
done
for tool in bash python3 chezmoi uv nu zsh shellcheck shfmt bats; do "$tool" --version | head -3; done
