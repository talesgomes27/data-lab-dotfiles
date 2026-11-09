#!/usr/bin/env bash
# Integração com downloads reais, exclusivamente numa HOME criada em /tmp.
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
sandbox=$(mktemp -d /tmp/foundry-online-XXXXXX)
trap 'rm -rf -- "$sandbox"' EXIT
export HOME="$sandbox" XDG_CONFIG_HOME="$sandbox/.config" XDG_STATE_HOME="$sandbox/.local/state"
export XDG_DATA_HOME="$sandbox/.local/share" XDG_CACHE_HOME="$sandbox/.cache"
export UV_CACHE_DIR="$sandbox/.cache/uv" UV_PYTHON_INSTALL_DIR="$sandbox/.local/share/uv/python"
export UV_TOOL_DIR="$sandbox/.local/share/uv/tools" UV_TOOL_BIN_DIR="$sandbox/.local/bin"
unset UV_PROJECT_ENVIRONMENT XDG_BIN_HOME
export PATH="$sandbox/.local/bin:$PATH"
bash scripts/ci-setup.sh
# Nenhuma confirmação automática pode alcançar um gerenciador real neste smoke.
mkdir "$sandbox/guard-bin"
for command in sudo apt-get dnf pacman zypper; do
    printf '#!/bin/sh\necho "Operação administrativa proibida neste smoke" >&2\nexit 90\n' >"$sandbox/guard-bin/$command"
    chmod 700 "$sandbox/guard-bin/$command"
done
export PATH="$sandbox/guard-bin:$PATH"
./bin/devshell setup --profile science --dry-run --json | python3 -c 'import json,sys;p=json.load(sys.stdin);assert not p["native_command"] and not p["permissions"] and not p["blockers"],p'
printf 's\ns\ns\n' | ./bin/devshell setup --profile science
"$HOME/.local/bin/pyinit" --help
approval=$(./bin/devshell install --component plugins --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
./bin/devshell install --component plugins --approve "$approval"
approval=$(./bin/devshell plan --profile personal,science --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
./bin/devshell apply --profile personal,science --approve "$approval"
./bin/devshell apply --profile personal,science --approve "$(./bin/devshell plan --profile personal,science --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')"
uv --version
uvx --version
uv --no-config python list --only-installed
# R-024: as ferramentas vêm das venvs com hash obrigatório, pelo symlink, e o doctor as aceita.
for tool in ruff pre-commit ipython; do
    [[ $(readlink "$HOME/.local/bin/$tool") == "$XDG_DATA_HOME/devshell/tools/$tool/bin/$tool" ]]
done
ruff --version
pre-commit --version
ipython --version
# doctor pode sair com 3 por outros componentes; aqui importam só as ferramentas.
doctor_report=$(./bin/devshell doctor --profile science --json || true)
printf '%s' "$doctor_report" | python3 -c 'import json,sys;i=[s for s in json.load(sys.stdin)["issues"] if any(k in s for k in ("ferramenta uv","componentes uv","interpretador uv"))];assert not i,i'
nu -c 'version | get version'
# shortcut: sem TTY valida carregamento; usar PTY para testar interação com ZLE.
zsh -fic '
    cd "$HOME"
    if [[ -n ${FOUNDRY_TEST_ZSH_PREFIX:-} ]]; then
        module_path=("$FOUNDRY_TEST_ZSH_PREFIX"/usr/lib/*/zsh/*(N) $module_path)
        fpath=("$FOUNDRY_TEST_ZSH_PREFIX"/usr/share/zsh/functions/*(/N) $fpath)
    fi
    source "$HOME/.zshenv"
    source "$ZDOTDIR/.zshrc"
    (( $+functions[_zsh_autosuggest_start] )) && (( $+functions[_zsh_highlight] )) && (( $+functions[compdef] ))
' </dev/null
# Restaurar primeiro a extensão personal e depois a configuração science inicial.
for transaction in 1 2; do
    printf 'Restaurar transação %s/2\n' "$transaction"
    approval=$(./bin/devshell rollback --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    ./bin/devshell rollback --approve "$approval"
done
[[ ! -e "$HOME/.zshenv" ]]
printf 'Smoke online concluído em HOME descartável.\n'
