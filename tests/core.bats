#!/usr/bin/env bats
setup() {
    umask 077
    export FOUNDRY_ROOT="$BATS_TEST_DIRNAME/.."
    export HOME="$BATS_TEST_TMPDIR/home"
    export XDG_CONFIG_HOME="$HOME/.config" XDG_STATE_HOME="$HOME/.local/state"
    export XDG_CACHE_HOME="$HOME/.cache" XDG_DATA_HOME="$HOME/.local/share"
    chmod go-w "$BATS_TEST_TMPDIR" "$BATS_TEST_TMPDIR/.."
    mkdir -p "$HOME"
    export DEVSHELL_OS_RELEASE="$BATS_TEST_DIRNAME/fixtures/os-release/ubuntu"
    export DEVSHELL_ARCH=x86_64
}
@test 'plan JSON descreve ubuntu apt e não escreve na HOME' {
    run "$FOUNDRY_ROOT/bin/devshell" plan --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["platform"]["adapter"]=="apt";assert "zsh" in p["components"];assert len(p["approval"])==64'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'perfis combinados eliminam componentes duplicados' {
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile work,science --offline --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);c=p["components"];assert len(c)==len(set(c));assert "uv" in c;assert "nu" not in c'
}
@test 'os-release não é executado como shell' {
    # shellcheck disable=SC2016 # Entrada maliciosa literal, não expandir.
    printf 'ID=ubuntu\nNAME=$(touch %s/pwned)\nID_LIKE=debian\n' "$HOME" >"$BATS_TEST_TMPDIR/os"
    export DEVSHELL_OS_RELEASE="$BATS_TEST_TMPDIR/os"
    run "$FOUNDRY_ROOT/bin/devshell" plan --json
    [ "$status" -eq 0 ]
    [ ! -e "$HOME/pwned" ]
}
@test 'arquitetura desconhecida recebe diagnóstico' {
    export DEVSHELL_ARCH=sparc
    run "$FOUNDRY_ROOT/bin/devshell" plan --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert not json.load(sys.stdin)["platform"]["supported_arch"]'
}
@test 'perfil inexistente e opção inválida falham sem mutação' {
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile unknown
    [ "$status" -eq 2 ]
    run "$FOUNDRY_ROOT/bin/devshell" apply --bogus
    [ "$status" -eq 2 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'apply exige aprovação e dry-run ignora aprovação sem escrever' {
    run "$FOUNDRY_ROOT/bin/devshell" apply
    [ "$status" -eq 2 ]
    run "$FOUNDRY_ROOT/bin/devshell" apply --dry-run --offline --json
    [ "$status" -eq 0 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
