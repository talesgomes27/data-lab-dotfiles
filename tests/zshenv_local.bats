#!/usr/bin/env bats
# shellcheck disable=SC2016 # Programas Zsh literais executados em HOME temporária.
# shellcheck disable=SC2030,SC2031 # Cada teste Bats tem subshell e setup próprios.
load core_setup

configure_zshenv() {
    local hash
    hash=$("$FOUNDRY_ROOT/bin/devshell" plan --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$FOUNDRY_ROOT/bin/devshell" apply --approve "$hash"
    export TEST_LOCAL_ENV="$XDG_CONFIG_HOME/zsh/.zshenv.local"
}

write_local_env() {
    printf 'typeset TEST_LOCAL_VALUE="personal fixture"\nexport TEST_LOCAL_EXPORTED="kept"\n' >"$TEST_LOCAL_ENV"
}

@test 'Zsh carrega extensão local segura no escopo global sem comandos externos' {
    export XDG_CONFIG_HOME="$HOME/configuração com espaços"
    configure_zshenv
    write_local_env
    shell=$(command -v zsh)
    run env PATH=/no-external-commands "$shell" -dc '[[ $TEST_LOCAL_VALUE == "personal fixture" && $TEST_LOCAL_EXPORTED == kept && $ZDOTDIR == "$XDG_CONFIG_HOME/zsh" ]]'
    [ "$status" -eq 0 ]
    [ -z "$output" ]
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 0 ]
}

@test 'extensão local ausente não cria arquivo ou emite aviso' {
    configure_zshenv
    run zsh -dc '[[ $ZDOTDIR == "$XDG_CONFIG_HOME/zsh" ]]'
    [ "$status" -eq 0 ]
    [ -z "$output" ]
    [ ! -e "$TEST_LOCAL_ENV" ]
}

@test 'Zsh e doctor recusam extensão gravável por grupo ou outros' {
    configure_zshenv
    printf ': >"$HOME/extensao-executada"\n' >"$TEST_LOCAL_ENV"
    for mode in 660 606; do
        chmod "$mode" "$TEST_LOCAL_ENV"
        run zsh -dc '[[ ! -e "$HOME/extensao-executada" ]]'
        [ "$status" -eq 0 ]
        [[ "$output" == *'extensão Zsh recusada'* ]]
        run "$FOUNDRY_ROOT/bin/devshell" doctor --json
        [ "$status" -eq 3 ]
        printf '%s' "$output" | python3 -c 'import json,sys;assert any("permissões inseguras" in s and ".zshenv.local" in s for s in json.load(sys.stdin)["issues"])'
    done
}

@test 'Zsh recusa extensão quando um ancestral permite escrita por grupo' {
    configure_zshenv
    printf ': >"$HOME/extensao-executada"\n' >"$TEST_LOCAL_ENV"
    chmod 770 "$XDG_CONFIG_HOME/zsh"
    run zsh -dc '[[ ! -e "$HOME/extensao-executada" ]]'
    [ "$status" -eq 0 ]
    [[ "$output" == *'extensão Zsh recusada'* ]]
}

@test 'Zsh e doctor recusam symlink e hardlink no arquivo local' {
    configure_zshenv
    printf ': >"$HOME/extensao-executada"\n' >"$HOME/payload"
    for kind in symlink hardlink; do
        if [[ $kind == symlink ]]; then ln -s "$HOME/payload" "$TEST_LOCAL_ENV"; else ln "$HOME/payload" "$TEST_LOCAL_ENV"; fi
        run zsh -dc '[[ ! -e "$HOME/extensao-executada" ]]'
        [ "$status" -eq 0 ]
        [[ "$output" == *'extensão Zsh recusada'* ]]
        run "$FOUNDRY_ROOT/bin/devshell" doctor --json
        [ "$status" -eq 3 ]
        rm "$TEST_LOCAL_ENV"
    done
}

@test 'Zsh recusa symlink em ancestral e tipo não regular no arquivo local' {
    configure_zshenv
    printf ': >"$HOME/extensao-executada"\n' >"$TEST_LOCAL_ENV"
    mv "$XDG_CONFIG_HOME/zsh" "$XDG_CONFIG_HOME/zsh-real"
    ln -s "$XDG_CONFIG_HOME/zsh-real" "$XDG_CONFIG_HOME/zsh"
    run zsh -dc '[[ ! -e "$HOME/extensao-executada" ]]'
    [ "$status" -eq 0 ]
    [[ "$output" == *'extensão Zsh recusada'* ]]
    rm "$XDG_CONFIG_HOME/zsh"
    mv "$XDG_CONFIG_HOME/zsh-real" "$XDG_CONFIG_HOME/zsh"
    rm "$TEST_LOCAL_ENV"
    for kind in directory fifo; do
        if [[ $kind == directory ]]; then mkdir "$TEST_LOCAL_ENV"; else mkfifo "$TEST_LOCAL_ENV"; fi
        run zsh -dc '[[ ! -e "$HOME/extensao-executada" ]]'
        [ "$status" -eq 0 ]
        [[ "$output" == *'extensão Zsh recusada'* ]]
        if [[ $kind == directory ]]; then rmdir "$TEST_LOCAL_ENV"; else rm "$TEST_LOCAL_ENV"; fi
    done
}

@test 'Zsh recusa caminho XDG com componente ponto-ponto' {
    configure_zshenv
    printf ': >"$HOME/extensao-executada"\n' >"$TEST_LOCAL_ENV"
    mkdir "$HOME/intermediario"
    export XDG_CONFIG_HOME="$HOME/intermediario/../.config"
    run zsh -dc '[[ ! -e "$HOME/extensao-executada" ]]'
    [ "$status" -eq 0 ]
    [[ "$output" == *'extensão Zsh recusada'* ]]
}

@test 'Zsh não carrega extensão quando o módulo de stat está indisponível' {
    configure_zshenv
    printf ': >"$HOME/extensao-executada"\n' >"$TEST_LOCAL_ENV"
    run zsh -dfc 'module_path=("$HOME/modulos-ausentes"); source "$HOME/.zshenv"; [[ ! -e "$HOME/extensao-executada" ]]'
    [ "$status" -eq 0 ]
    [[ "$output" == *'extensão Zsh recusada'* ]]
}

@test 'bytecode local mais novo não contorna validação do texto' {
    configure_zshenv
    printf ': >"$HOME/bytecode-executado"\n' >"$HOME/payload"
    zsh -dfc 'zcompile "$TEST_LOCAL_ENV.zwc" "$HOME/payload"'
    write_local_env
    python3 - <<'PY'
import os
os.utime(os.environ['TEST_LOCAL_ENV'],(1,1))
PY
    chmod 666 "$TEST_LOCAL_ENV.zwc"
    for kind in regular symlink; do
        if [[ $kind == symlink ]]; then
            mv "$TEST_LOCAL_ENV.zwc" "$HOME/payload.zwc"
            ln -s "$HOME/payload.zwc" "$TEST_LOCAL_ENV.zwc"
        fi
        run zsh -dc '[[ ! -e "$HOME/bytecode-executado" && -z ${TEST_LOCAL_VALUE-} ]]'
        [ "$status" -eq 0 ]
        [[ "$output" == *'extensão Zsh recusada'* ]]
        run "$FOUNDRY_ROOT/bin/devshell" doctor --json
        [ "$status" -eq 3 ]
        printf '%s' "$output" | python3 -c 'import json,sys;assert any("compilado" in s and ".zshenv.local.zwc" in s for s in json.load(sys.stdin)["issues"])'
    done
}

@test 'doctor e setup recusam bytecode dos arquivos Zsh gerenciados' {
    configure_zshenv
    for source in "$HOME/.zshenv" "$XDG_CONFIG_HOME/zsh/.zprofile" "$XDG_CONFIG_HOME/zsh/.zshrc"; do
        printf 'cache não permitido' >"$source.zwc"
        run "$FOUNDRY_ROOT/bin/devshell" doctor --json
        [ "$status" -eq 3 ]
        printf '%s' "$output" | python3 -c 'import json,sys;assert any("compilado" in s for s in json.load(sys.stdin)["issues"])'
        run "$FOUNDRY_ROOT/bin/devshell" setup --dry-run --json
        [ "$status" -eq 0 ]
        printf '%s' "$output" | python3 -c 'import json,sys;assert any("compilado" in s for s in json.load(sys.stdin)["blockers"])'
        rm "$source.zwc"
    done
}

@test 'inspeção nunca executa extensão local e edição do bootstrap continua divergente' {
    configure_zshenv
    printf ': >"$HOME/extensao-executada"\n' >"$TEST_LOCAL_ENV"
    for command in plan diff status doctor; do
        run "$FOUNDRY_ROOT/bin/devshell" "$command" --json
        [ "$status" -eq 0 ]
        [ ! -e "$HOME/extensao-executada" ]
    done
    printf 'export TEST_CORE_EDITED=1\n' >>"$HOME/.zshenv"
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("arquivo gerenciado divergente" in s and s.endswith("/.zshenv") for s in json.load(sys.stdin)["issues"])'
    [ ! -e "$HOME/extensao-executada" ]
}

@test 'setup inclui extensão local insegura na revisão sem alterar permissões' {
    configure_zshenv
    write_local_env
    chmod 660 "$TEST_LOCAL_ENV"
    run "$FOUNDRY_ROOT/bin/devshell" setup --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,os,sys;assert any(i["path"]==os.environ["TEST_LOCAL_ENV"] and i["repairable"] for i in json.load(sys.stdin)["permissions"])'
    [ "$(stat -c %a "$TEST_LOCAL_ENV")" = 660 ]
}

@test 'migração preserva código pessoal e rollback restaura bootstrap anterior' {
    mkdir -p "$XDG_CONFIG_HOME/zsh"
    export TEST_LOCAL_ENV="$XDG_CONFIG_HOME/zsh/.zshenv.local"
    printf 'export TEST_PERSONAL="preserved"\n' >"$TEST_LOCAL_ENV"
    printf '# bootstrap anterior\nsource "$XDG_CONFIG_HOME/zsh/.zshenv.local"\n' >"$HOME/.zshenv"
    chmod 640 "$HOME/.zshenv"
    cp -p "$HOME/.zshenv" "$HOME/previous-zshenv"
    hash=$("$FOUNDRY_ROOT/bin/devshell" plan --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$FOUNDRY_ROOT/bin/devshell" apply --approve "$hash" --replace-existing
    run zsh -dc '[[ $TEST_PERSONAL == preserved ]]'
    [ "$status" -eq 0 ]
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 0 ]
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash"
    cmp "$HOME/.zshenv" "$HOME/previous-zshenv"
    [ "$(stat -c %a "$HOME/.zshenv")" = 640 ]
    [ -f "$TEST_LOCAL_ENV" ]
}
