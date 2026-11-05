# shellcheck shell=bash
resolve_profiles() {
    local selected=$1 item line existing
    local -a profiles components=()
    [[ "$selected" =~ ^[a-z]+(,[a-z]+)*$ ]] || fail 'lista de perfis inválida'
    IFS=',' read -r -a profiles <<<"$selected"
    for item in minimal "${profiles[@]}"; do
        [[ -f "$ROOT/profiles/$item.profile" ]] || fail "perfil desconhecido: $item"
        while IFS= read -r line || [[ -n "$line" ]]; do
            [[ -z "$line" || "$line" == \#* ]] && continue
            [[ "$line" =~ ^[a-z][a-z0-9-]*$ ]] || fail "componente inválido no perfil $item"
            existing=" ${components[*]} "
            [[ "$existing" == *" $line "* ]] || components+=("$line")
        done <"$ROOT/profiles/$item.profile"
    done
    export DEVSHELL_COMPONENTS="${components[*]}"
}
