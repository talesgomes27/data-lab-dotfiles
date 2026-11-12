# shellcheck shell=bash
# Saída completa (Bloco G): orquestra uninstall e rollback --all com uma confirmação por etapa (D-036).
leave_value() {
    devshell_python -c 'import json,sys;print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

leave_failed() {
    printf 'A etapa "%s" falhou. Etapas já concluídas foram preservadas. Para continuar: ./bin/devshell leave\n' "$1" >&2
    return 1
}

leave_show_plan() {
    devshell_python "$ROOT/lib/leave.py" show-plan
}

leave_cancel() {
    printf 'Saída cancelada. Etapas já concluídas foram preservadas. Para continuar: ./bin/devshell leave\n' >&2
    return 1
}

# Antes de cada etapa: o plano da cadeia continua aceito? Ele é só leitura.
leave_guard() {
    local error
    if ! error=$("$ROOT/bin/devshell" rollback --all --json 2>&1 >/dev/null); then
        printf 'O plano do rollback --all passou a recusar: %s\n' "${error##*$'\n'}" >&2
        printf 'Etapas já concluídas foram preservadas. Resolva e rode ./bin/devshell leave de novo.\n' >&2
        return 1
    fi
}

leave_environment() {
    local dry_run=$1 purge=$2 summary plan hash count component answer
    summary=$(DEVSHELL_PURGE=$purge devshell_python "$ROOT/lib/leave.py" summary)
    if ((dry_run)); then
        if [[ "$DEVSHELL_JSON" == 1 ]]; then printf '%s\n' "$summary"; else printf '%s\n' "$summary" | devshell_python "$ROOT/lib/leave.py" show; fi
        return
    fi
    printf '%s\n' "$summary" | devshell_python "$ROOT/lib/leave.py" show
    # R-071: qualquer plano com erro para tudo antes da primeira pergunta.
    count=$(printf '%s' "$summary" | devshell_python -c 'import json,sys;print(len(json.load(sys.stdin)["blockers"]))')
    ((count == 0)) || fail 'resolva os bloqueios apresentados; nada foi alterado' 2
    for component in python plugins firacode pyinit devshell; do
        leave_guard || return 1
        plan=$("$ROOT/bin/devshell" uninstall --component "$component" --json) || {
            leave_failed "uninstall $component"
            return 1
        }
        count=$(printf '%s' "$plan" | devshell_python -c 'import json,sys;print(sum(i["action"]=="remove" for i in json.load(sys.stdin)["items"]))')
        ((count)) || continue
        # O plano mostrado é o mesmo que vai ser aprovado.
        printf '%s' "$plan" | leave_show_plan
        setup_confirm "Desinstalar o componente $component conforme este plano?" || {
            leave_cancel
            return 1
        }
        hash=$(printf '%s' "$plan" | leave_value approval)
        "$ROOT/bin/devshell" uninstall --component "$component" --approve "$hash" || {
            leave_failed "uninstall $component"
            return 1
        }
    done
    leave_guard || return 1
    plan=$("$ROOT/bin/devshell" rollback --all --json) || {
        leave_failed 'rollback --all'
        return 1
    }
    count=$(printf '%s' "$plan" | devshell_python -c 'import json,sys;print(len(json.load(sys.stdin)["transactions"]))')
    if ((count)); then
        printf '%s' "$plan" | leave_show_plan
        setup_confirm "Desfazer as $count transação(ões) da cadeia, voltando os dotfiles a antes do primeiro apply?" || {
            leave_cancel
            return 1
        }
        hash=$(printf '%s' "$plan" | leave_value approval)
        "$ROOT/bin/devshell" rollback --all --approve "$hash" || {
            leave_failed 'rollback --all'
            return 1
        }
    fi
    if ((purge)); then
        leave_guard || return 1
        plan=$(devshell_python "$ROOT/lib/leave.py" purge-plan) || {
            leave_failed 'apagar o estado'
            return 1
        }
        if [[ $(printf '%s' "$plan" | leave_value offered) == True ]]; then
            printf '%s\n' "$plan" | devshell_python -c 'import json,sys;d=json.load(sys.stdin);print("Apagar",d["path"],"("+str(d["bytes"])+" bytes):",", ".join(d["contents"]));print(d["message"]);[print("Aviso:",w) for w in d["warnings"]]'
            # R-074: irreversível; a própria palavra, como substituir e retirar.
            printf 'Para apagar o estado da CLI por completo, digite apagar: ' >&2
            if IFS= read -r answer && [[ "$answer" == apagar ]]; then
                printf '%s' "$plan" | DEVSHELL_APPROVAL=$(printf '%s' "$plan" | leave_value approval) devshell_python "$ROOT/lib/leave.py" purge || {
                    leave_failed 'apagar o estado'
                    return 1
                }
            else
                printf 'Estado mantido.\n'
            fi
        else
            printf 'O estado não será apagado: %s\n' "$(printf '%s' "$plan" | leave_value reason)"
        fi
    fi
    devshell_python "$ROOT/lib/leave.py" remains
}
