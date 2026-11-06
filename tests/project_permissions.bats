#!/usr/bin/env bats
# shellcheck disable=SC2030,SC2031 # Cada teste Bats tem subshell e setup próprios.
load core_setup

prepare_project() {
    export TEST_PROJECT="$HOME/Insync/repos/projeto com espaços"
    uv --no-config --offline venv --no-project --no-python-downloads --python "$(command -v python3)" "$TEST_PROJECT/.venv"
    mkdir "$TEST_PROJECT/nao-alterar"
    printf 'fixture\n' >"$TEST_PROJECT/nao-alterar/dados.txt"
    chmod 777 "$TEST_PROJECT/nao-alterar"
    chmod 666 "$TEST_PROJECT/nao-alterar/dados.txt"
    chmod 775 "$HOME/Insync" "$HOME/Insync/repos" "$TEST_PROJECT" "$TEST_PROJECT/.venv" "$TEST_PROJECT/.venv/bin"
}

project_hash() {
    "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --dry-run --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])'
}

@test 'project doctor aponta os diretórios exatos e não grava estado' {
    prepare_project
    run "$FOUNDRY_ROOT/bin/devshell" project doctor --path "$TEST_PROJECT" --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,os,sys;p=json.load(sys.stdin);assert len(p["permissions"])==5;assert all(i["from_mode"]=="0775" and i["to_mode"]=="0755" and i["repairable"] for i in p["permissions"]);assert os.environ["HOME"]+"/Insync" in {i["path"] for i in p["issues"]}'
    [ ! -e "$XDG_STATE_HOME/devshell" ]
    [ ! -e "$XDG_DATA_HOME/direnv" ]
}

@test 'project fix dry-run não usa aprovação nem altera modos ou estado' {
    prepare_project
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --dry-run --approve invalido --json
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$TEST_PROJECT")" = 775 ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'project fix exige confirmação própria e recusa EOF ou não' {
    prepare_project
    run bash -c '"$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" </dev/null'
    [ "$status" -eq 1 ]
    run bash -c 'printf "n\n" | "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT"'
    [ "$status" -eq 1 ]
    [ "$(stat -c %a "$TEST_PROJECT")" = 775 ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --yes
    [ "$status" -eq 2 ]
}

@test 'project fix com hash registra modos e não toca filhos ou recria venv' {
    prepare_project
    inode=$(stat -c %i "$TEST_PROJECT/.venv")
    hash=$(project_hash)
    export TEST_APPROVAL="$hash"
    run bash -c '"$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --approve "$TEST_APPROVAL" --json 2>"$BATS_TEST_TMPDIR/repair-stderr"'
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,os,sys;from pathlib import Path;p=json.load(sys.stdin);assert p["changed"]==5;record=Path(p["record"]);data=json.loads(record.read_text());assert data["status"]=="complete";assert len(data["completed"])==5;assert all(i["from_mode"]=="0775" and i["to_mode"]=="0755" for i in data["plan"]["permissions"]);assert record.stat().st_mode & 0o777==0o600'
    [ "$(stat -c %a "$TEST_PROJECT")" = 755 ]
    [ "$(stat -c %a "$TEST_PROJECT/.venv/bin")" = 755 ]
    [ "$(stat -c %i "$TEST_PROJECT/.venv")" = "$inode" ]
    [ "$(stat -c %a "$TEST_PROJECT/nao-alterar")" = 777 ]
    [ "$(stat -c %a "$TEST_PROJECT/nao-alterar/dados.txt")" = 666 ]
    [ ! -e "$TEST_PROJECT/.envrc" ]
    [ ! -e "$XDG_DATA_HOME/direnv" ]
    run "$FOUNDRY_ROOT/bin/devshell" project doctor --path "$TEST_PROJECT" --json
    [ "$status" -eq 0 ]
}

@test 'project fix aceita sim após apresentar o plano' {
    prepare_project
    run bash -c 'printf "sim\n" | "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT"'
    [ "$status" -eq 0 ]
    [[ "$output" == *'0775 -> 0755'* ]]
}

@test 'project fix recusa aprovação vencida e inode substituído' {
    prepare_project
    hash=$(project_hash)
    mv "$TEST_PROJECT/.venv/bin" "$TEST_PROJECT/.venv/bin-antigo"
    cp -a "$TEST_PROJECT/.venv/bin-antigo" "$TEST_PROJECT/.venv/bin"
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --approve "$hash"
    [ "$status" -eq 2 ]
    [ "$(stat -c %a "$HOME/Insync")" = 775 ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'project fix recusa symlink sem chmod no destino' {
    prepare_project
    mv "$HOME/Insync/repos" "$HOME/Insync/repos-reais"
    ln -s "$HOME/Insync/repos-reais" "$HOME/Insync/repos"
    hash=$(project_hash)
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --approve "$hash"
    [ "$status" -eq 2 ]
    [ "$(stat -c %a "$HOME/Insync/repos-reais")" = 775 ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'project fix não altera diretórios fora da HOME mesmo com venv válida' {
    export TEST_PROJECT="$BATS_TEST_TMPDIR/fora-da-home"
    uv --no-config --offline venv --no-project --no-python-downloads --python "$(command -v python3)" "$TEST_PROJECT/.venv"
    chmod 775 "$TEST_PROJECT"
    hash=$(project_hash)
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --approve "$hash"
    [ "$status" -eq 2 ]
    [ "$(stat -c %a "$TEST_PROJECT")" = 775 ]
    [ -f "$TEST_PROJECT/.venv/pyvenv.cfg" ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'project fix não cria ou sincroniza venv ausente dentro da HOME' {
    export TEST_PROJECT="$HOME/projeto-sem-ambiente"
    mkdir "$TEST_PROJECT"
    chmod 775 "$TEST_PROJECT"
    hash=$(project_hash)
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --approve "$hash"
    [ "$status" -eq 2 ]
    [ "$(stat -c %a "$TEST_PROJECT")" = 775 ]
    [ ! -e "$TEST_PROJECT/.venv" ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'helper explica recusa em stderr sem inserir diagnóstico no PATH' {
    prepare_project
    run python3 - "$FOUNDRY_ROOT" "$TEST_PROJECT" <<'PY'
import subprocess,sys
from pathlib import Path
root,project=map(Path,sys.argv[1:])
p=subprocess.run(['python3',str(root/'dotfiles/dot_config/devshell/safe-path.py'),'--venv','--explain',str(project/'.venv/bin')],capture_output=True,text=True)
assert p.returncode==0
assert not p.stdout
assert str(project) in p.stderr and '0775' in p.stderr,p.stderr
assert 'permiss' in p.stderr
PY
    [ "$status" -eq 0 ]
}

@test 'project não executa Python da venv ativa durante diagnóstico ou reparo' {
    prepare_project
    rm "$TEST_PROJECT/.venv/bin/python3"
    # shellcheck disable=SC2016 # Código do stub, avaliado apenas no processo filho.
    printf '#!/bin/sh\n: >"$HOME/python-da-venv-executado"\nexit 0\n' >"$TEST_PROJECT/.venv/bin/python3"
    chmod 755 "$TEST_PROJECT/.venv/bin/python3"
    PATH="$TEST_PROJECT/.venv/bin:$PATH" run "$FOUNDRY_ROOT/bin/devshell" project doctor --path "$TEST_PROJECT" --json
    [ "$status" -eq 3 ]
    [ ! -e "$HOME/python-da-venv-executado" ]
}

@test 'project não executa utilitários encontrados na venv ativa' {
    prepare_project
    for utility in dirname uname getconf ldd grep; do
        # shellcheck disable=SC2016 # Código do stub, avaliado no processo filho.
        printf '#!/bin/sh\n: >"$HOME/utilitario-da-venv-executado"\nexec /usr/bin/%s "$@"\n' "$utility" >"$TEST_PROJECT/.venv/bin/$utility"
        chmod 755 "$TEST_PROJECT/.venv/bin/$utility"
    done
    PATH="$TEST_PROJECT/.venv/bin:$PATH" run "$FOUNDRY_ROOT/bin/devshell" project doctor --path "$TEST_PROJECT" --json
    [ "$status" -eq 3 ]
    [ ! -e "$HOME/utilitario-da-venv-executado" ]
    PATH="$TEST_PROJECT/.venv/bin:$PATH" run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --dry-run --json
    [ "$status" -eq 0 ]
    [ ! -e "$HOME/utilitario-da-venv-executado" ]
}

@test 'project não executa sitecustomize injetado via PYTHONPATH' {
    prepare_project
    mkdir "$HOME/python-injetado"
    printf 'import os\nfrom pathlib import Path\nPath(os.environ["HOME"],"sitecustomize-executado").touch()\n' >"$HOME/python-injetado/sitecustomize.py"
    PYTHONPATH="$HOME/python-injetado" run "$FOUNDRY_ROOT/bin/devshell" project doctor --path "$TEST_PROJECT" --json
    [ "$status" -eq 3 ]
    [ ! -e "$HOME/sitecustomize-executado" ]
}

@test 'project informa previamente quando o registro está sob HOME insegura' {
    prepare_project
    chmod 775 "$HOME"
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,os,sys;p=json.load(sys.stdin);assert p["blockers"];assert any(i["path"]==os.environ["HOME"] and not i["repairable"] for i in p["permissions"])'
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'project doctor e dry-run não criam bytecode nas fontes da CLI' {
    prepare_project
    copy="$BATS_TEST_TMPDIR/cli-copy"
    python3 - "$FOUNDRY_ROOT" "$copy" <<'PY'
import shutil,sys
from pathlib import Path
root,copy=map(Path,sys.argv[1:])
for name in ('bin','lib','manifests','profiles','dotfiles'):
    shutil.copytree(root/name,copy/name,ignore=shutil.ignore_patterns('__pycache__'))
PY
    run "$copy/bin/devshell" project doctor --path "$TEST_PROJECT" --json
    [ "$status" -eq 3 ]
    [ -z "$(find "$copy" -name __pycache__ -print -quit)" ]
    run "$copy/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --dry-run --json
    [ "$status" -eq 0 ]
    [ -z "$(find "$copy" -name __pycache__ -print -quit)" ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'project usa diretório atual e não cria registro quando nada precisa de reparo' {
    prepare_project
    hash=$(project_hash)
    "$FOUNDRY_ROOT/bin/devshell" project fix-permissions --path "$TEST_PROJECT" --approve "$hash"
    rm -r "$XDG_STATE_HOME/devshell/permission-repairs"
    cd "$TEST_PROJECT" || return
    run "$FOUNDRY_ROOT/bin/devshell" project doctor --json
    [ "$status" -eq 0 ]
    run "$FOUNDRY_ROOT/bin/devshell" project fix-permissions
    [ "$status" -eq 0 ]
    [ ! -e "$XDG_STATE_HOME/devshell/permission-repairs" ]
}

@test 'direnv informa o caminho recusado e oferece o reparo explícito' {
    prepare_project
    hash=$("$FOUNDRY_ROOT/bin/devshell" plan --profile personal --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$FOUNDRY_ROOT/bin/devshell" apply --profile personal --approve "$hash"
    printf 'use devshell_python\n' >"$TEST_PROJECT/.envrc"
    direnv allow "$TEST_PROJECT"
    cd "$TEST_PROJECT" || return
    run direnv export bash
    [[ "$output" == *"$HOME/Insync"* ]]
    [[ "$output" == *'0775'* ]]
    [[ "$output" == *'project fix-permissions'* ]]
}
