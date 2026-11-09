# shellcheck shell=bash
install_python() {
    local spec tools interpreter
    local -a interpreters options=(--no-config --no-progress)
    command -v uv >/dev/null || fail 'uv ausente: instale primeiro o componente uv.' 3
    # check validou manifesto, locks, destinos, versão mínima e hash aprovado.
    spec=$(devshell_python "$ROOT/lib/artifacts.py" python-spec)
    local directories directory
    directories=$(devshell_python "$ROOT/lib/artifacts.py" python-dirs)
    while IFS= read -r directory; do
        export "${directory?}"
    done <<<"$directories"
    mapfile -t interpreters < <(printf '%s' "$spec" | devshell_python -c 'import json,sys;[print(v) for v in json.load(sys.stdin)["interpreters"]]')
    tools=$(printf '%s' "$spec" | devshell_python -c 'import json,sys;print(len(json.load(sys.stdin)["tools"]))')
    if [[ "$DEVSHELL_OFFLINE" == 1 ]]; then options+=(--offline); fi
    for interpreter in "${interpreters[@]}"; do uv "${options[@]}" python install --no-bin "$interpreter" >&2; done
    # Venvs com hash obrigatório, sob o lock da CLI (ADR 004); a falha sai com 2.
    [[ "$tools" == 0 ]] || devshell_python "$ROOT/lib/artifacts.py" python-tools
    devshell_python "$ROOT/lib/artifacts.py" python-done
}
