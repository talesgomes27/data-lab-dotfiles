#!/usr/bin/env bats
# shellcheck disable=SC2016,SC2030,SC2031,SC2154 # Scripts Python entre aspas simples; run do Bats preenche status, output e stderr.
bats_require_minimum_version 1.5.0
# R-040: perfis lembrados, precedência e restauração, em HOME temporária.
load core_setup

record() { printf '%s\n' "$XDG_STATE_HOME/devshell/profiles"; }
approval_of() { python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])'; }
apply_profile() {
    "$FOUNDRY_ROOT/bin/devshell" apply --profile "$1" --approve "$("$FOUNDRY_ROOT/bin/devshell" plan --profile "$1" --json | approval_of)" --replace-existing >/dev/null
}
field() { python3 -c 'import json,sys;d=json.load(sys.stdin);print(",".join(d["profiles"]), d["profile_source"])'; }
state_digest() { (cd "$HOME" && find . -print0 | sort -z | xargs -0 -I{} sh -c 'printf "%s " "{}"; if [ -f "{}" ]; then sha256sum <"{}"; else echo dir; fi'); }

@test 'R-040 sem registro vale minimal com origem padrão e nada é gravado' {
    for command in plan doctor status; do
        run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" "$command" --json
        [ "$(printf '%s' "$output" | field)" = 'minimal padrão' ]
    done
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}

@test 'R-040 apply grava os perfis e os comandos sem --profile os usam' {
    apply_profile personal
    [ "$(cat "$(record)")" = personal ]
    for command in plan doctor status diff; do
        run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" "$command" --json
        [ "$(printf '%s' "$output" | field)" = 'personal lembrados' ]
    done
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" install --component plugins --json
    [ "$status" -eq 0 ]
    [ "$(printf '%s' "$output" | field)" = 'personal lembrados' ]
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" setup --dry-run --json
    [ "$status" -eq 0 ]
    [ "$(printf '%s' "$output" | field)" = 'personal lembrados' ]
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" diff
    [[ "$stderr" == *'Perfis: personal (lembrados)'* ]]
    run "$FOUNDRY_ROOT/bin/devshell" plan
    [[ "$output" == *'Perfis: personal (lembrados)'* ]]
}

@test 'R-040 --profile informado vale sem gravar e ignora duplicatas e o minimal implícito' {
    apply_profile personal
    before=$(state_digest)
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" plan --profile science --json
    [ "$(printf '%s' "$output" | field)" = 'science informados' ]
    for command in diff doctor status; do
        "$FOUNDRY_ROOT/bin/devshell" "$command" >/dev/null 2>&1 || true
    done
    "$FOUNDRY_ROOT/bin/devshell" setup --dry-run >/dev/null 2>&1
    "$FOUNDRY_ROOT/bin/devshell" setup --profile science --dry-run --json >/dev/null 2>&1
    [ "$(state_digest)" = "$before" ]
    a=$("$FOUNDRY_ROOT/bin/devshell" plan --profile personal --json | approval_of)
    b=$("$FOUNDRY_ROOT/bin/devshell" plan --profile minimal,personal,personal --json | approval_of)
    c=$("$FOUNDRY_ROOT/bin/devshell" plan --json | approval_of)
    [ "$a" = "$b" ] && [ "$a" = "$c" ]
}

@test 'R-040 registro desatualizado de arquivo idêntico não vira pendência do setup' {
    apply_profile personal
    python3 -c 'import json,sys;p=sys.argv[1];d=json.load(open(p));k=next(iter(d));d[k]="0"*64;open(p,"w").write(json.dumps(d))' "$XDG_STATE_HOME/devshell/current.json"
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" doctor --json
    printf '%s' "$output" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert not [i for i in d["issues"] if "arquivo gerenciado divergente" in i],d["issues"]'
}

@test 'R-042 uv, chezmoi e nu fora do PATH sempre têm algo a instalar' {
    mkdir -p "$HOME/.local/bin"
    printf 'não executável\n' >"$HOME/.local/bin/chezmoi"
    for component in uv chezmoi nu; do
        run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" install --component "$component" --profile personal --json
        printf '%s' "$output" | python3 -c 'import json,sys;assert json.load(sys.stdin)["pending"] is True'
    done
}

@test 'R-040 apply sem arquivos a alterar também grava o registro' {
    apply_profile personal
    rm "$(record)"
    run "$FOUNDRY_ROOT/bin/devshell" apply --profile personal --approve "$("$FOUNDRY_ROOT/bin/devshell" plan --profile personal --json | approval_of)"
    [ "$status" -eq 0 ]
    [ "$(cat "$(record)")" = personal ]
}

@test 'R-040 HOME já aplicada sem registro exige --profile uma vez' {
    apply_profile personal
    rm "$(record)"
    before=$(state_digest)
    run "$FOUNDRY_ROOT/bin/devshell" plan
    [ "$status" -eq 2 ]
    [[ "$output" == *'--profile'* ]]
    [ "$(state_digest)" = "$before" ]
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile personal
    [ "$status" -eq 0 ]
}

@test 'R-040 project e install devshell ignoram o registro, mesmo corrompido' {
    apply_profile personal
    mkdir -p "$HOME/projeto"
    printf 'Pessoal!\n' >"$(record)"
    run "$FOUNDRY_ROOT/bin/devshell" plan
    [ "$status" -eq 2 ]
    run "$FOUNDRY_ROOT/bin/devshell" project doctor --path "$HOME/projeto"
    [ "$status" -ne 2 ]
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --json
    [ "$status" -eq 0 ]
    run "$FOUNDRY_ROOT/bin/devshell" project doctor --path "$HOME/projeto" --profile personal
    [ "$status" -eq 2 ]
}

@test 'R-040 registro inválido sai com 2 sem --profile e só avisa com --profile' {
    apply_profile personal
    printf 'Pessoal!\n' >"$(record)"
    run "$FOUNDRY_ROOT/bin/devshell" plan
    [ "$status" -eq 2 ]
    [[ "$output" == *'--profile'* ]]
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" plan --profile personal --json
    [ "$status" -eq 0 ]
    [[ "$stderr" == *'aviso'* ]]
    printf 'inexistente\n' >"$(record)"
    run "$FOUNDRY_ROOT/bin/devshell" plan
    [ "$status" -eq 2 ]
}

@test 'R-040 rollback funciona com registro corrompido' {
    apply_profile personal
    printf 'Pessoal!\n' >"$(record)"
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    run "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash"
    [ "$status" -eq 0 ]
}

@test 'R-040 rollback restaura os perfis anteriores ou remove o registro' {
    apply_profile minimal
    [ "$(cat "$(record)")" = minimal ]
    apply_profile personal
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash" >/dev/null
    [ "$(cat "$(record)")" = minimal ]
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash" >/dev/null
    [ ! -e "$(record)" ]
}

@test 'R-040 manifesto antigo sem previous_profiles mantém o registro e avisa' {
    apply_profile personal
    latest=$(cat "$XDG_STATE_HOME/devshell/latest")
    python3 -c 'import json,sys;p=sys.argv[1];m=json.load(open(p));m.pop("previous_profiles");open(p,"w").write(json.dumps(m))' "$XDG_STATE_HOME/devshell/transactions/$latest/manifest.json"
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    run "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash"
    [ "$status" -eq 0 ]
    [[ "$output" == *'perfis anteriores desconhecidos'* ]]
    [ "$(cat "$(record)")" = personal ]
}

@test 'R-040 setup sem --profile lê o registro mesmo com permissão de grupo a reparar' {
    apply_profile personal
    chmod 775 "$HOME/.local"
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" setup --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["profiles"]==["personal"];assert any(i["path"].endswith("/.local") for i in p["permissions"]),p["permissions"]'
}

@test 'R-040 registro que é symlink não é seguido' {
    apply_profile personal
    printf 'science\n' >"$HOME/outro"
    rm "$(record)"
    ln -s "$HOME/outro" "$(record)"
    run "$FOUNDRY_ROOT/bin/devshell" plan
    [ "$status" -eq 2 ]
}

@test 'R-044 componente em ~/.local/bin fora do PATH vira passo manual, não setup' {
    apply_profile personal
    # Tira do PATH os diretórios onde a máquina já tem chezmoi.
    PATH=$(printf '%s' "$PATH" | tr ':' '\n' | while IFS= read -r dir; do [ -x "$dir/chezmoi" ] || printf '%s:' "$dir"; done)
    PATH=${PATH%:}
    mkdir -p "$HOME/.local/bin"
    printf '#!/bin/sh\n' >"$HOME/.local/bin/chezmoi"
    chmod 700 "$HOME/.local/bin/chezmoi"
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" doctor --json
    printf '%s' "$output" | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert "componente ausente: chezmoi" not in d["issues"],d["issues"]
assert any(i.startswith("componente fora do PATH: chezmoi") for i in d["issues"]),d["issues"]
assert d["next_step"]["kind"]=="manual",d["next_step"]'
}

@test 'R-040 install em texto mostra os perfis e a origem' {
    apply_profile personal
    run "$FOUNDRY_ROOT/bin/devshell" install --component plugins
    [ "$status" -eq 0 ]
    [[ "$output" == *'Perfis: personal (lembrados)'* ]]
}
