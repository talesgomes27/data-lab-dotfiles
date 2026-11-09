# shellcheck shell=bash
install_python() {
    local version spec
    local -a interpreters tools options=(--no-config --no-progress)
    command -v uv >/dev/null || fail 'uv ausente: instale primeiro o componente uv.' 3
    # check validou manifesto, destinos, versão mínima e hash aprovado.
    spec=$(devshell_python "$ROOT/lib/artifacts.py" python-spec)
    local directories directory
    directories=$(devshell_python "$ROOT/lib/artifacts.py" python-dirs)
    while IFS= read -r directory; do
        export "${directory?}"
    done <<<"$directories"
    mapfile -t interpreters < <(printf '%s' "$spec" | devshell_python -c 'import json,sys;[print(v) for v in json.load(sys.stdin)["interpreters"]]')
    mapfile -t tools < <(printf '%s' "$spec" | devshell_python -c 'import json,sys;d=json.load(sys.stdin);[print(t["name"]+"=="+t["version"]) for t in d["tools"]]')
    version=$(printf '%s' "$spec" | devshell_python -c 'import json,sys;print(json.load(sys.stdin)["tool_python"])')
    if [[ "$DEVSHELL_OFFLINE" == 1 ]]; then options+=(--offline); fi
    for spec in "${interpreters[@]}"; do uv "${options[@]}" python install --no-bin "$spec" >&2; done
    for spec in "${tools[@]}"; do
        uv "${options[@]}" tool install --managed-python --no-python-downloads --python "$version" "$spec" >&2
    done
    devshell_python "$ROOT/lib/artifacts.py" python-done
}
