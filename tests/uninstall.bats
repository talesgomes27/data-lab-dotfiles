#!/usr/bin/env bats
# shellcheck disable=SC2016,SC2154 # Scripts Python entre aspas simples; run do Bats preenche status e output.
bats_require_minimum_version 1.5.0
# R-060 a R-064: desinstalação com prova de dono, em HOME temporária.
load core_setup

approval_of() { python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])'; }
state_digest() { (cd "$HOME" && find . -print0 | sort -z | xargs -0 -I{} sh -c 'printf "%s " "{}"; if [ -f "{}" ]; then sha256sum <"{}"; else echo dir; fi'); }

@test 'R-063 uninstall devshell remove o lançador e o recibo depois da aprovação' {
    hash=$("$FOUNDRY_ROOT/bin/devshell" install --component devshell --json | approval_of)
    "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$hash" >/dev/null
    [ -x "$HOME/.local/bin/devshell" ]
    before=$(state_digest)
    run "$FOUNDRY_ROOT/bin/devshell" uninstall --component devshell --dry-run
    [ "$status" -eq 0 ]
    [[ "$output" == *"remove: $HOME/.local/bin/devshell"* ]]
    [ "$(state_digest)" = "$before" ]
    hash=$("$FOUNDRY_ROOT/bin/devshell" uninstall --component devshell --json | approval_of)
    run "$FOUNDRY_ROOT/bin/devshell" uninstall --component devshell --approve "$hash"
    [ "$status" -eq 0 ]
    [[ "$output" == *'install --component devshell'* ]]
    [ ! -e "$HOME/.local/bin/devshell" ]
    [ ! -e "$XDG_STATE_HOME/devshell/launcher.json" ]
}

@test 'R-061 lançador editado fica como manual e não é removido' {
    hash=$("$FOUNDRY_ROOT/bin/devshell" install --component devshell --json | approval_of)
    "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$hash" >/dev/null
    printf '# meu\n' >>"$HOME/.local/bin/devshell"
    hash=$("$FOUNDRY_ROOT/bin/devshell" uninstall --component devshell --json | approval_of)
    run "$FOUNDRY_ROOT/bin/devshell" uninstall --component devshell --approve "$hash"
    [ "$status" -eq 0 ]
    [ -e "$HOME/.local/bin/devshell" ]
    [[ "$output" == *'manual:'* ]]
}

@test 'R-060 uninstall recusa uv, chezmoi, nu, componente ausente e --profile' {
    for component in uv chezmoi nu desconhecido; do
        run "$FOUNDRY_ROOT/bin/devshell" uninstall --component "$component"
        [ "$status" -eq 2 ]
    done
    run "$FOUNDRY_ROOT/bin/devshell" uninstall
    [ "$status" -eq 2 ]
    run "$FOUNDRY_ROOT/bin/devshell" uninstall --component python --profile personal
    [ "$status" -eq 2 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
