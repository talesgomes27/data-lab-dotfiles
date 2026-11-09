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
# Ruff do check.sh: mesma versão fixada em manifests/python.json, com o Python do runner.
ruff_pin=$(python3 -c 'import json;print(next(t["version"] for t in json.load(open("manifests/python.json"))["tools"] if t["name"]=="ruff"))')
uv --no-config tool install --no-python-downloads --python "$(command -v python3)" "ruff==$ruff_pin"
starship_archive="$HOME/starship.tar.gz"
curl --fail --location --silent --show-error --output "$starship_archive" https://github.com/starship/starship/releases/download/v1.22.1/starship-x86_64-unknown-linux-musl.tar.gz
printf '62c91b5ecc7f8c8c6ea7ffea42a98bd2e6a2d29daf61562fac04daece18a6461  %s\n' "$starship_archive" | sha256sum --check
tar -xOzf "$starship_archive" starship >"$HOME/.local/bin/starship"
chmod 755 "$HOME/.local/bin/starship"
rm -- "$starship_archive"
starship --version
for tool in bash python3 chezmoi uv nu zsh shellcheck shfmt bats ruff; do "$tool" --version | head -3; done
