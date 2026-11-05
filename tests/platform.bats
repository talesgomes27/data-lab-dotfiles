#!/usr/bin/env bats
load core_setup
@test 'relatório textual exibe o nome Data Lab Dotfiles' {
    run "$FOUNDRY_ROOT/bin/devshell" plan --offline
    [ "$status" -eq 0 ]
    [[ "$output" == 'Data Lab Dotfiles — plan'* ]]
}
@test 'seleciona os cinco adaptadores por ID e ID_LIKE' {
    for pair in 'debian apt' 'fedora dnf' 'arch pacman' 'opensuse-leap zypper' 'unknown manual'; do
        read -r distro expected <<<"$pair"
        printf 'ID=%s\n' "$distro" >"$BATS_TEST_TMPDIR/os"
        DEVSHELL_OS_RELEASE="$BATS_TEST_TMPDIR/os" run "$FOUNDRY_ROOT/bin/devshell" plan --json
        [ "$status" -eq 0 ]
        printf '%s' "$output" | EXPECTED="$expected" python3 -c 'import json,os,sys;assert json.load(sys.stdin)["platform"]["adapter"]==os.environ["EXPECTED"]'
    done
    printf 'ID=derivada\nID_LIKE="fedora rhel"\n' >"$BATS_TEST_TMPDIR/os"
    DEVSHELL_OS_RELEASE="$BATS_TEST_TMPDIR/os" run "$FOUNDRY_ROOT/bin/devshell" plan --json
    printf '%s' "$output" | python3 -c 'import json,sys;assert json.load(sys.stdin)["platform"]["adapter"]=="dnf"'
}
@test 'aarch64 é reconhecida e fd bat aceitam nomes Debian' {
    export DEVSHELL_ARCH=arm64
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile personal --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["platform"]["arch"]=="aarch64";c=p["dependencies"]["manual_system_command"];assert "fd-find" in c or "fd" not in p["dependencies"]["missing"]'
}
@test 'extras declara ferramentas e mapeia tldr para tealdeer no Ubuntu' {
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile personal,extras --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert {"btop","ncdu","tldr","lazygit"} <= set(p["components"]);assert "tealdeer" in p["dependencies"]["manual_system_command"] or "tldr" not in p["dependencies"]["missing"]'
}
@test 'plan diff status doctor e update dry-run não criam estado' {
    for command in plan diff status doctor; do
        run "$FOUNDRY_ROOT/bin/devshell" "$command" --offline --json
        [[ "$status" -eq 0 || "$status" -eq 3 ]]
        printf '%s' "$output" | python3 -m json.tool >/dev/null
    done
    run "$FOUNDRY_ROOT/bin/devshell" update --dry-run
    [ "$status" -eq 0 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'doctor identifica uv incompatível sem escrever na HOME' {
    mkdir "$BATS_TEST_TMPDIR/old"
    printf '#!/bin/sh\nprintf "uv 0.1.0\\n"\n' >"$BATS_TEST_TMPDIR/old/uv"
    chmod +x "$BATS_TEST_TMPDIR/old/uv"
    PATH="$BATS_TEST_TMPDIR/old:$PATH" run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("versão incompatível: uv" in i for i in json.load(sys.stdin)["issues"])'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'update sem aprovação apenas mostra plano' {
    run "$FOUNDRY_ROOT/bin/devshell" update --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert json.load(sys.stdin)["approval"]'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
