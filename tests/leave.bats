#!/usr/bin/env bats
# shellcheck disable=SC2016,SC2154 # Scripts Python entre aspas simples; run do Bats preenche status e output.
bats_require_minimum_version 1.5.0
# R-070 a R-074: saída completa, em HOME temporária.
load core_setup

approval_of() { python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])'; }
apply_profile() {
    "$FOUNDRY_ROOT/bin/devshell" apply --profile "$1" --approve "$("$FOUNDRY_ROOT/bin/devshell" plan --profile "$1" --json | approval_of)" --replace-existing >/dev/null
}
install_launcher() {
    "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$("$FOUNDRY_ROOT/bin/devshell" install --component devshell --json | approval_of)" >/dev/null
}
dotfiles() { find "$HOME" -path "$XDG_STATE_HOME" -prune -o -type f -print | sort; }

@test 'R-071 leave desinstala o lançador e desfaz a cadeia, com uma confirmação por etapa' {
    apply_profile minimal
    install_launcher
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Desinstalar o componente devshell=s" "Desfazer as=s" -- "$FOUNDRY_ROOT/bin/devshell" leave'
    [ "$status" -eq 0 ]
    [[ "$output" == *'Resumo da saída'* && "$output" == *'O que continua na máquina'* ]]
    [ ! -e "$HOME/.local/bin/devshell" ]
    [ ! -e "$HOME/.zshenv" ]
    [ -z "$(dotfiles)" ]
    [ -d "$XDG_STATE_HOME/devshell" ]
    [ ! -e "$XDG_STATE_HOME/devshell/latest" ]
}

@test 'R-071 arquivo editado para o leave antes da primeira pergunta' {
    apply_profile minimal
    install_launcher
    printf '# meu\n' >>"$HOME/.zshenv"
    run bash -c '"$FOUNDRY_ROOT/bin/devshell" leave </dev/null'
    [ "$status" -eq 2 ]
    [[ "$output" == *'bloqueio'* && "$output" == *'.zshenv'* ]]
    [[ "$output" != *'[s/N]'* ]]
    [ -e "$HOME/.local/bin/devshell" ]
}

@test 'R-071 recusar uma etapa cancela as seguintes e mantém as feitas' {
    apply_profile minimal
    install_launcher
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Desinstalar o componente devshell=n" -- "$FOUNDRY_ROOT/bin/devshell" leave'
    [ "$status" -eq 1 ]
    [[ "$output" == *'Para continuar: ./bin/devshell leave'* ]]
    [ -e "$HOME/.local/bin/devshell" ]
    [ -e "$HOME/.zshenv" ]
}

@test 'R-074 leave --purge-state apaga o estado só com a palavra apagar' {
    apply_profile minimal
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Desfazer as=s" "digite apagar=nao" -- "$FOUNDRY_ROOT/bin/devshell" leave --purge-state'
    [ "$status" -eq 0 ]
    [ -d "$XDG_STATE_HOME/devshell" ]
    apply_profile minimal
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Desfazer as=s" "digite apagar=apagar" -- "$FOUNDRY_ROOT/bin/devshell" leave --purge-state'
    [ "$status" -eq 0 ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
    [ -z "$(dotfiles)" ]
}

@test 'R-071 leave --dry-run não grava nada e recusa opções que não usa' {
    run "$FOUNDRY_ROOT/bin/devshell" leave --dry-run
    [ "$status" -eq 0 ]
    run "$FOUNDRY_ROOT/bin/devshell" leave --dry-run --json
    [ "$status" -eq 0 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
    for option in '--json' '--profile minimal' '--approve x' '--component python'; do
        # shellcheck disable=SC2086 # A opção com valor é dividida de propósito.
        run "$FOUNDRY_ROOT/bin/devshell" leave $option
        [ "$status" -eq 2 ]
    done
    run "$FOUNDRY_ROOT/bin/devshell" rollback --purge-state
    [ "$status" -eq 2 ]
}
