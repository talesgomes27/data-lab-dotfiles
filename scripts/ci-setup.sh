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
# Ruff do check.sh: lock com hash obrigatório numa venv só do CI, fora de devshell/tools e de
# UV_TOOL_BIN_DIR, para não colidir com a instalação de science no smoke (R-024, R-025).
uv --no-config --no-progress venv --no-python-downloads --python "$(command -v python3)" "$HOME/.cache/ci-ruff"
uv --no-config --no-progress pip install --python "$HOME/.cache/ci-ruff/bin/python" --require-hashes --no-build \
    --link-mode copy -r manifests/python-tools/ruff.txt
mkdir -p "$HOME/.local/ci-bin"
ln -sfn "$HOME/.cache/ci-ruff/bin/ruff" "$HOME/.local/ci-bin/ruff"
export PATH="$HOME/.local/ci-bin:$PATH"
starship_archive="$HOME/starship.tar.gz"
curl --fail --location --silent --show-error --output "$starship_archive" https://github.com/starship/starship/releases/download/v1.22.1/starship-x86_64-unknown-linux-musl.tar.gz
printf '62c91b5ecc7f8c8c6ea7ffea42a98bd2e6a2d29daf61562fac04daece18a6461  %s\n' "$starship_archive" | sha256sum --check
tar -xOzf "$starship_archive" starship >"$HOME/.local/bin/starship"
chmod 755 "$HOME/.local/bin/starship"
rm -- "$starship_archive"
starship --version
for tool in bash python3 chezmoi uv nu zsh shellcheck shfmt bats ruff; do "$tool" --version | head -3; done
