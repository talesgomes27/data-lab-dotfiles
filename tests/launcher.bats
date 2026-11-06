#!/usr/bin/env bats
# shellcheck disable=SC2030,SC2031 # Cada teste Bats tem subshell e setup próprios.
load core_setup

launcher_hash() {
    "$FOUNDRY_ROOT/bin/devshell" install --component devshell --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])'
}

install_launcher() {
    local approval
    approval=$(launcher_hash)
    "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$approval" --offline --json
}

@test 'launcher plan e dry-run são locais e não escrevem na HOME' {
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,os,sys;p=json.load(sys.stdin);assert p["operation"]=="install-devshell";assert p["checkout"]==os.path.realpath(os.environ["FOUNDRY_ROOT"]);assert any(f["path"]==os.environ["HOME"]+"/.local/bin/devshell" for f in p["files"]);assert len(p["approval"])==64'
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --dry-run --approve invalido --offline
    [ "$status" -eq 0 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}

@test 'launcher requer aprovação e instalação offline repete sem novas escritas' {
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve invalido --offline
    [ "$status" -eq 2 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
    install_launcher
    [ "$(stat -c %a "$HOME/.local/bin/devshell")" = 755 ]
    [ "$(stat -c %a "$XDG_STATE_HOME/devshell/launcher.json")" = 600 ]
    [ ! -e "$XDG_CACHE_HOME" ]
    inode=$(stat -c %i "$HOME/.local/bin/devshell")
    records=$(find "$XDG_STATE_HOME/devshell/launcher-backups" -name manifest.json | wc -l)
    hash=$(launcher_hash)
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$hash" --offline --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert json.load(sys.stdin)["changed"]==0'
    [ "$(stat -c %i "$HOME/.local/bin/devshell")" = "$inode" ]
    [ "$(find "$XDG_STATE_HOME/devshell/launcher-backups" -name manifest.json | wc -l)" = "$records" ]
}

@test 'launcher preserva argumentos e checkout com espaços aspas e metacaracteres' {
    # shellcheck disable=SC2016 # Metacaracteres literais no caminho de teste.
    export LAUNCHER_REPO="$BATS_TEST_TMPDIR/repo com espaços e 'aspas' "'$(touch LAUNCHER_INJECTED)'
    mkdir -p "$LAUNCHER_REPO"
    cp -a "$FOUNDRY_ROOT/"{bin,lib,manifests,profiles,dotfiles,.chezmoiroot} "$LAUNCHER_REPO/"
    hash=$("$LAUNCHER_REPO/bin/devshell" install --component devshell --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$LAUNCHER_REPO/bin/devshell" install --component devshell --approve "$hash" --offline
    export LAUNCHER_PROJECT="$HOME/projeto com espaços"
    uv --no-config --offline venv --no-project --no-python-downloads --python "$(command -v python3)" "$LAUNCHER_PROJECT/.venv"
    cd "$HOME"
    run "$HOME/.local/bin/devshell" project doctor --path "$LAUNCHER_PROJECT" --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,os,sys;assert json.load(sys.stdin)["project"]==os.environ["LAUNCHER_PROJECT"]'
    [ ! -e "$HOME/LAUNCHER_INJECTED" ]
}

@test 'launcher diferente exige substituição explícita e guarda backup exato' {
    mkdir -p "$HOME/.local/bin"
    printf '#!/bin/sh\nprintf anterior\\n\n' >"$HOME/.local/bin/devshell"
    chmod 700 "$HOME/.local/bin/devshell"
    cp "$HOME/.local/bin/devshell" "$BATS_TEST_TMPDIR/original"
    hash=$(launcher_hash)
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$hash" --offline
    [ "$status" -eq 2 ]
    cmp "$HOME/.local/bin/devshell" "$BATS_TEST_TMPDIR/original"
    [ ! -e "$XDG_STATE_HOME/devshell" ]
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$hash" --replace-existing --offline --json
    [ "$status" -eq 0 ]
    python3 - "$BATS_TEST_TMPDIR/original" <<'PY'
import json,os,stat,sys
from pathlib import Path
original=Path(sys.argv[1]).read_bytes()
root=Path(os.environ['XDG_STATE_HOME'])/'devshell/launcher-backups'
record,=root.glob('*/manifest.json')
report=json.loads(record.read_text())
assert report['status']=='complete'
entry=next(e for e in report['plan']['files'] if e['path'].endswith('/bin/devshell'))
assert entry['before']['mode']==0o700
backup=record.parent/entry['backup']
assert backup.read_bytes()==original
assert stat.S_IMODE(backup.stat().st_mode)==0o600
PY
}

@test 'launcher recusa aprovação vencida sem sobrescrever novo arquivo' {
    hash=$(launcher_hash)
    mkdir -p "$HOME/.local/bin"
    printf 'preservar\n' >"$HOME/.local/bin/devshell"
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --approve "$hash" --replace-existing
    [ "$status" -eq 2 ]
    [ "$(cat "$HOME/.local/bin/devshell")" = preservar ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'launcher recusa symlink hardlink e caminho de backup inseguro' {
    mkdir -p "$HOME/.local/bin"
    printf 'preservar\n' >"$HOME/original"
    ln -s "$HOME/original" "$HOME/.local/bin/devshell"
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --json
    [ "$status" -eq 2 ]
    rm "$HOME/.local/bin/devshell"
    ln "$HOME/original" "$HOME/.local/bin/devshell"
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --json
    [ "$status" -eq 2 ]
    rm "$HOME/.local/bin/devshell"
    mkdir -p "$XDG_STATE_HOME/devshell" "$HOME/fora"
    ln -s "$HOME/fora" "$XDG_STATE_HOME/devshell/launcher-backups"
    run "$FOUNDRY_ROOT/bin/devshell" install --component devshell --json
    [ "$status" -eq 2 ]
    [ ! -e "$HOME/.local/bin/devshell" ]
    [ -z "$(find "$HOME/fora" -mindepth 1 -print -quit)" ]
}

@test 'doctor confere launcher registrado sem executar arquivo divergente' {
    install_launcher
    printf '#!/bin/sh\ntouch "%s"\n' "$HOME/EXECUTOU" >"$HOME/.local/bin/devshell"
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert any("lançador devshell" in i for i in p["issues"])'
    [ ! -e "$HOME/EXECUTOU" ]
    rm "$HOME/.local/bin/devshell"
    run "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("lançador devshell" in i for i in json.load(sys.stdin)["issues"])'
}

@test 'launcher informa checkout ausente sem procurar outra cópia' {
    export LAUNCHER_REPO="$BATS_TEST_TMPDIR/repo"
    mkdir -p "$LAUNCHER_REPO"
    cp -a "$FOUNDRY_ROOT/"{bin,lib,manifests,profiles,dotfiles,.chezmoiroot} "$LAUNCHER_REPO/"
    hash=$("$LAUNCHER_REPO/bin/devshell" install --component devshell --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$LAUNCHER_REPO/bin/devshell" install --component devshell --approve "$hash" --offline
    mv "$LAUNCHER_REPO" "$LAUNCHER_REPO-movido"
    run "$HOME/.local/bin/devshell" --help
    [ "$status" -eq 3 ]
    [[ "$output" == *'checkout'* && "$output" == *'instal'* ]]
}
