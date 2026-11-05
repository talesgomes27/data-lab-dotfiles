# shellcheck shell=bash
# Orquestra os comandos públicos; aprovação e transações permanecem nos helpers.
setup_values() {
    python3 -c 'import json,sys;value=json.load(sys.stdin)[sys.argv[1]];[print(item) for item in value] if isinstance(value,list) else print(value)' "$1"
}

setup_confirm() {
    local answer
    printf '%s [s/N] ' "$1" >&2
    IFS= read -r answer || return 1
    [[ ${answer,,} == s || ${answer,,} == sim ]]
}

setup_cancel() {
    printf 'Setup cancelado. Etapas já concluídas foram preservadas.\n' >&2
    return 1
}

setup_inspect() {
    python3 "$ROOT/lib/setup.py" inspect
}

setup_show() {
    python3 "$ROOT/lib/setup.py" show
}

setup_path() {
    local directory
    while IFS= read -r directory; do
        case ":$PATH:" in *":$directory:"*) ;; *) export PATH="$directory:$PATH" ;; esac
    done < <(python3 "$ROOT/dotfiles/dot_config/devshell/safe-path.py" "$HOME/.local/bin")
}

setup_environment() {
    local inspection plan hash target answer count dry_run=$1
    local -a packages components options=(--profile "$DEVSHELL_PROFILES") replacement=()
    [[ "$DEVSHELL_OFFLINE" == 0 ]] || options+=(--offline)
    setup_path
    inspection=$(setup_inspect)
    if ((dry_run)); then
        if [[ "$DEVSHELL_JSON" == 1 ]]; then printf '%s\n' "$inspection"; else printf '%s\n' "$inspection" | setup_show; fi
        return
    fi
    printf '%s\n' "$inspection" | setup_show
    [[ -z $(printf '%s' "$inspection" | setup_values blockers) ]] || fail 'resolva os bloqueios apresentados e execute setup novamente' 3
    mapfile -t packages < <(printf '%s' "$inspection" | setup_values native_command)
    if ((DEVSHELL_OFFLINE && ${#packages[@]})); then fail 'offline: pacotes nativos ausentes; instale-os manualmente antes de continuar' 3; fi
    count=$(printf '%s' "$inspection" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)["permissions"]))')
    if ((count)); then
        printf '%s' "$inspection" | python3 -c 'import json,sys;sys.exit(any(not item["repairable"] for item in json.load(sys.stdin)["permissions"]))' || fail 'há caminhos que exigem correção manual; nenhum modo foi alterado' 3
        setup_confirm 'Retirar escrita de grupo/outros somente dos caminhos apresentados?' || {
            setup_cancel
            return 1
        }
        printf '%s' "$inspection" | python3 "$ROOT/lib/setup.py" repair
        setup_path
        inspection=$(setup_inspect)
        printf '%s\n' "$inspection" | setup_show
        [[ -z $(printf '%s' "$inspection" | setup_values blockers) ]] || fail 'resolva os bloqueios apresentados antes de continuar' 3
        mapfile -t packages < <(printf '%s' "$inspection" | setup_values native_command)
    fi
    if ((${#packages[@]})); then
        local -a administrator=()
        if ((EUID != 0)); then
            command -v sudo >/dev/null || fail 'sudo ausente: execute o comando administrativo apresentado manualmente' 3
            administrator=(sudo --)
        fi
        printf 'Comando administrativo: ' >&2
        printf '%q ' "${administrator[@]}" "${packages[@]}" >&2
        printf '\n' >&2
        setup_confirm 'Executar este comando com privilégios administrativos?' || {
            setup_cancel
            return 1
        }
        "${administrator[@]}" "${packages[@]}"
        inspection=$(setup_inspect)
        [[ -z $(printf '%s' "$inspection" | setup_values blockers) ]] || fail 'ferramenta incompatível após instalação; veja setup --dry-run' 3
        [[ -z $(printf '%s' "$inspection" | setup_values native_command) ]] || fail 'ainda há pacotes ausentes; veja setup --dry-run' 3
    fi
    setup_path
    mapfile -t components < <(printf '%s' "$inspection" | setup_values user_components)
    for target in "${components[@]}"; do
        plan=$("$ROOT/bin/devshell" install --component "$target" "${options[@]}" --json)
        printf '%s\n' "$plan" | setup_show
        setup_confirm "Instalar/verificar o componente $target conforme este plano?" || {
            setup_cancel
            return 1
        }
        hash=$(printf '%s' "$plan" | setup_values approval)
        "$ROOT/bin/devshell" install --component "$target" "${options[@]}" --approve "$hash"
        setup_path
    done
    plan=$("$ROOT/bin/devshell" plan "${options[@]}" --json)
    count=$(printf '%s' "$plan" | python3 -c 'import json,sys;print(sum(item["action"]=="write" for item in json.load(sys.stdin)["files"]))')
    if ((count)); then
        printf '%s\n' "$plan" | setup_show
        "$ROOT/bin/devshell" diff "${options[@]}"
        setup_confirm 'Aplicar os dotfiles apresentados, com backup?' || {
            setup_cancel
            return 1
        }
        count=$(printf '%s' "$plan" | python3 -c 'import json,sys;print(sum(item["conflict"] for item in json.load(sys.stdin)["files"]))')
        if ((count)); then
            printf 'Há %s conflito(s). Para substituir os arquivos existentes com backup, digite substituir: ' "$count" >&2
            IFS= read -r answer || {
                setup_cancel
                return 1
            }
            [[ "$answer" == substituir ]] || {
                setup_cancel
                return 1
            }
            replacement=(--replace-existing)
        fi
        hash=$(printf '%s' "$plan" | setup_values approval)
        "$ROOT/bin/devshell" apply "${options[@]}" --approve "$hash" "${replacement[@]}"
    else
        printf 'Dotfiles já correspondem ao perfil; nenhuma aplicação necessária.\n'
    fi
    "$ROOT/bin/devshell" doctor "${options[@]}"
    printf 'Setup concluído. Inicie zsh quando desejar; a shell de login foi preservada.\n'
}
