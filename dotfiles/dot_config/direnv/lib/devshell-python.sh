# shellcheck shell=bash
# Chamado apenas pelo .envrc revisado: use devshell_python.
use_devshell_python() {
    # Conda mantém estado próprio de shell; não simular conda deactivate.
    if [[ -n ${CONDA_PREFIX-} ]]; then
        log_error 'Conda ativo; desative-o explicitamente para usar a troca de .venv pelo uv.'
        return 0
    fi
    local config data entry safe_bin=''
    local -a entries kept=()
    case "${XDG_CONFIG_HOME-}" in /*) config=$XDG_CONFIG_HOME ;; *) config="$HOME/.config" ;; esac
    case "${XDG_DATA_HOME-}" in /*) data=$XDG_DATA_HOME ;; *) data="$HOME/.local/share" ;; esac
    IFS=: read -r -a entries <<<"$PATH"
    for entry in "${entries[@]}"; do
        # Comparação literal: nomes com metacaracteres não são padrões de glob.
        [[ $entry == "$data/devshell/venvs/geral/bin" || (-n ${VIRTUAL_ENV-} && $entry == "$VIRTUAL_ENV/bin") ]] || kept+=("$entry")
    done
    local IFS=:
    export PATH="${kept[*]}"
    unset VIRTUAL_ENV PYTHONHOME
    watch_file "$PWD/.venv/pyvenv.cfg" "$PWD/.venv/bin/python" "$PWD/.venv/bin/python3"
    if [[ -x /usr/bin/python3 && -r $config/devshell/safe-path.py ]]; then
        safe_bin=$(/usr/bin/python3 -I "$config/devshell/safe-path.py" --venv --explain "$PWD/.venv/bin")
    fi
    if [[ -n $safe_bin ]]; then
        export VIRTUAL_ENV="$PWD/.venv"
        PATH_add "$safe_bin"
    else
        log_error '.venv não ativada; corrija os motivos acima e execute direnv reload. A CLI Data Lab oferece project doctor e project fix-permissions.'
    fi
    # Retornar erro descartaria também a retirada do ambiente pessoal pelo direnv.
    return 0
}
