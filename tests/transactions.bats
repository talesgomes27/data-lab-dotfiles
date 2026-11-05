#!/usr/bin/env bats
# shellcheck disable=SC2120,SC2119 # Bats run repassa argumentos ao helper.
load core_setup
approve() { "$FOUNDRY_ROOT/bin/devshell" plan --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])'; }
apply_config() { "$FOUNDRY_ROOT/bin/devshell" apply --approve "$(approve)" "$@"; }
@test 'apply cria dotfiles e segunda aplicação não cria novo backup' {
    run apply_config
    [ "$status" -eq 0 ]
    [ -f "$HOME/.zshenv" ]
    [ -f "$XDG_CONFIG_HOME/zsh/.zshrc" ]
    first=$(cat "$XDG_STATE_HOME/devshell/latest")
    run apply_config
    [ "$status" -eq 0 ]
    [ "$(cat "$XDG_STATE_HOME/devshell/latest")" = "$first" ]
}
@test 'conflito exige opt-in e rollback restaura conteúdo e modo' {
    printf 'original\n' >"$HOME/.zshenv"
    chmod 640 "$HOME/.zshenv"
    run apply_config
    [ "$status" -eq 2 ]
    [ "$(cat "$HOME/.zshenv")" = original ]
    run apply_config --replace-existing
    [ "$status" -eq 0 ]
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash"
    [ "$status" -eq 0 ]
    [ "$(cat "$HOME/.zshenv")" = original ]
    [ "$(stat -c %a "$HOME/.zshenv")" = 640 ]
    [ ! -e "$XDG_CONFIG_HOME/zsh/.zshrc" ]
}
@test 'aprovação vencida recusa aplicação antes de escrever' {
    hash=$(approve)
    printf 'novo\n' >"$HOME/.zshenv"
    run "$FOUNDRY_ROOT/bin/devshell" apply --approve "$hash" --replace-existing
    [ "$status" -eq 2 ]
    [ ! -d "$XDG_STATE_HOME/devshell" ]
}
@test 'rollback recusa edição posterior sem tocar nos demais arquivos' {
    apply_config
    printf 'edição posterior\n' >>"$HOME/.zshenv"
    run "$FOUNDRY_ROOT/bin/devshell" rollback --approve invalid
    [ "$status" -eq 2 ]
    [ -e "$XDG_CONFIG_HOME/zsh/.zshrc" ]
    [[ "$(cat "$HOME/.zshenv")" == *'edição posterior'* ]]
}
@test 'symlink de alvo e de ancestral são recusados' {
    mkdir -p "$BATS_TEST_TMPDIR/external"
    ln -s "$BATS_TEST_TMPDIR/external" "$XDG_CONFIG_HOME"
    run "$FOUNDRY_ROOT/bin/devshell" plan
    [ "$status" -eq 2 ]
    [ -z "$(find "$BATS_TEST_TMPDIR/external" -mindepth 1 -print -quit)" ]
}
@test 'XDG absoluto com espaços funciona; XDG relativo usa default' {
    export XDG_CONFIG_HOME="$HOME/configuração com espaço"
    apply_config
    [ -e "$XDG_CONFIG_HOME/zsh/.zshrc" ]
    export XDG_CONFIG_HOME=relativo
    run "$FOUNDRY_ROOT/bin/devshell" plan --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys,os;assert any(f["path"]==os.environ["HOME"]+"/.config/zsh/.zshrc" for f in json.load(sys.stdin)["files"])'
}
@test 'falha de renderização não altera alvos' {
    mkdir "$BATS_TEST_TMPDIR/fake"
    printf '#!/bin/sh\nexit 42\n' >"$BATS_TEST_TMPDIR/fake/chezmoi"
    chmod +x "$BATS_TEST_TMPDIR/fake/chezmoi"
    export PATH="$BATS_TEST_TMPDIR/fake:$PATH"
    run apply_config
    [ "$status" -ne 0 ]
    [ ! -e "$HOME/.zshenv" ]
}
@test 'doctor detecta divergência de arquivo gerenciado' {
    apply_config
    printf 'editado\n' >>"$HOME/.zshenv"
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("arquivo gerenciado divergente" in i for i in json.load(sys.stdin)["issues"])'
}
@test 'doctor informa arquivos esperados ausentes antes da primeira aplicação' {
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("arquivo esperado ausente" in i and ".zshenv" in i for i in json.load(sys.stdin)["issues"])'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'doctor distingue arquivo idêntico não registrado de arquivo ausente' {
    cp "$FOUNDRY_ROOT/dotfiles/dot_zshenv" "$HOME/.zshenv"
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert any("não registrado" in s and ".zshenv" in s for s in p["warnings"]);assert not any("arquivo esperado ausente" in s and ".zshenv" in s for s in p["issues"])'
}
@test 'doctor identifica plugins fontes e componentes uv ausentes após aplicar dotfiles' {
    hash=$("$FOUNDRY_ROOT/bin/devshell" plan --profile personal,science --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$FOUNDRY_ROOT/bin/devshell" apply --profile personal,science --approve "$hash"
    run "$FOUNDRY_ROOT/bin/devshell" doctor --profile personal,science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);s=" ".join(p["issues"]);assert all(x in s for x in ("autosuggestions", "highlighting", "FiraCode", "3.12.12", "3.13.11", "ruff", "pre-commit", "ipython")),s'
}
