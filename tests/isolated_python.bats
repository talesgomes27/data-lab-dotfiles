#!/usr/bin/env bats
# shellcheck disable=SC2016 # Os scripts entre aspas simples são expandidos pela shell filha.
bats_require_minimum_version 1.5.0
load core_setup

# Um .venv ativo ou PYTHONPATH de projeto não pode injetar código na CLI nem nas shells.
prepare_hostile_python() {
    local site
    export HOSTILE_VENV="$BATS_TEST_TMPDIR/hostile-venv" HOSTILE_PATH="$BATS_TEST_TMPDIR/hostile-path"
    uv --no-config --offline venv --no-project --no-python-downloads --python "$(command -v python3)" "$HOSTILE_VENV" >/dev/null 2>&1
    site=$(printf '%s\n' "$HOSTILE_VENV"/lib/python3.*/site-packages)
    printf 'import pathlib; pathlib.Path("%s").touch()\n' "$HOME/pth-executed" >"$site/hostile.pth"
    mkdir -p "$HOSTILE_PATH" "$HOME/.local/bin" "$XDG_CONFIG_HOME/devshell"
    printf 'import pathlib; pathlib.Path("%s").touch()\n' "$HOME/pythonpath-executed" >"$HOSTILE_PATH/json.py"
    cp "$FOUNDRY_ROOT/dotfiles/dot_config/devshell/env.sh" "$FOUNDRY_ROOT/dotfiles/dot_config/devshell/safe-path.py" "$XDG_CONFIG_HOME/devshell/"
}

assert_not_loaded() {
    [ ! -e "$HOME/pth-executed" ]
    [ ! -e "$HOME/pythonpath-executed" ]
}

@test 'CLI não carrega .pth da venv ativa nem PYTHONPATH' {
    prepare_hostile_python
    local -a command
    for spec in plan doctor status 'install --component devshell' 'setup --dry-run'; do
        read -r -a command <<<"$spec"
        PATH="$HOSTILE_VENV/bin:$PATH" PYTHONPATH="$HOSTILE_PATH" run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" "${command[@]}" --json
        # shellcheck disable=SC2154 # $stderr vem de run --separate-stderr; ShellCheck antigo não o conhece.
        printf '%s => %s: %s\n' "$spec" "$status" "$stderr"
        [ "$status" -eq 0 ] || [ "$status" -eq 3 ]
        # JSON válido prova que o Python da CLI executou, não um erro de pré-requisito.
        printf '%s' "$output" | python3 -c 'import json,sys;assert json.load(sys.stdin)["operation"]'
    done
    assert_not_loaded
}

@test 'Bash e Zsh não carregam .pth da venv herdada ao filtrar PATH' {
    prepare_hostile_python
    local script='source "$XDG_CONFIG_HOME/devshell/env.sh"; case ":$PATH:" in *":$HOME/.local/bin:"*) exit 0 ;; esac; exit 7'
    PATH="$HOSTILE_VENV/bin:$PATH" PYTHONPATH="$HOSTILE_PATH" run bash --noprofile --norc -c "$script"
    [ "$status" -eq 0 ]
    PATH="$HOSTILE_VENV/bin:$PATH" PYTHONPATH="$HOSTILE_PATH" run zsh -fc "$script"
    [ "$status" -eq 0 ]
    assert_not_loaded
}

@test 'Nushell não carrega .pth da venv herdada ao filtrar PATH' {
    command -v nu >/dev/null || skip 'nu não disponível'
    prepare_hostile_python
    mkdir -p "$XDG_CONFIG_HOME/nushell"
    cp "$FOUNDRY_ROOT/dotfiles/dot_config/nushell/env.nu" "$FOUNDRY_ROOT/dotfiles/dot_config/nushell/config.nu" "$XDG_CONFIG_HOME/nushell/"
    PATH="$HOSTILE_VENV/bin:$PATH" PYTHONPATH="$HOSTILE_PATH" run nu --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c '$env.PATH | where {|p| $p == ($env.HOME | path join ".local" "bin") } | length'
    [ "$status" -eq 0 ]
    [ "$output" = 1 ]
    assert_not_loaded
}

@test 'helper direnv não carrega .pth da venv herdada ao validar .venv' {
    prepare_hostile_python
    local project="$BATS_TEST_TMPDIR/project"
    mkdir -p "$project"
    cp -a "$HOSTILE_VENV" "$project/.venv"
    rm -f "$project"/.venv/lib/python3.*/site-packages/hostile.pth
    cd "$project"
    # Stubs mínimos da stdlib do direnv; o helper é chamado como num .envrc autorizado.
    PATH="$HOSTILE_VENV/bin:$PATH" PYTHONPATH="$HOSTILE_PATH" run bash --noprofile --norc -c '
        watch_file() { :; }; log_error() { printf "%s\n" "$*" >&2; }; PATH_add() { PATH="$1:$PATH"; }
        source "$1"; use_devshell_python; [[ $VIRTUAL_ENV == "$PWD/.venv" ]]' _ "$FOUNDRY_ROOT/dotfiles/dot_config/direnv/lib/devshell-python.sh"
    [ "$status" -eq 0 ]
    assert_not_loaded
}
