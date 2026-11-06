#!/usr/bin/env bats
load core_setup

pyinit_plan() {
    "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --json
}

seed_pyinit() {
    mkdir -p "$XDG_CACHE_HOME/devshell/artifacts"
    python3 - "$FOUNDRY_ROOT" "$XDG_CACHE_HOME" <<'PY'
import json,sys
from pathlib import Path
root,cache=map(Path,sys.argv[1:])
artifact=next(a for a in json.loads((root/'manifests/artifacts.json').read_text())['artifacts'] if a['component']=='pyinit')
(cache/'devshell/artifacts'/artifact['sha256']).write_bytes((root/'templates/python-template-linux/scripts/init_project.sh').read_bytes())
PY
}

@test 'science seleciona pyinit e dry-run não escreve na HOME' {
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile science --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert "pyinit" in json.load(sys.stdin)["components"]'
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --dry-run --json
    [ "$status" -eq 0 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile minimal --json
    printf '%s' "$output" | python3 -c 'import json,sys;assert "pyinit" not in json.load(sys.stdin)["components"]'
}

@test 'manifesto pyinit corresponde aos bytes e ao commit do submódulo' {
    run python3 - "$FOUNDRY_ROOT" <<'PY'
import hashlib,json,re,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1])
artifact=next(a for a in json.loads((root/'manifests/artifacts.json').read_text())['artifacts'] if a['component']=='pyinit')
assert re.fullmatch('[a-f0-9]{40}',artifact['version'])
assert artifact['url']==f"https://github.com/talesgomes27/python-template-linux/raw/{artifact['version']}/scripts/init_project.sh"
assert (artifact['binary'],artifact['format'],artifact['arch'],artifact['libc'])==('pyinit','raw','any','any')
assert hashlib.sha256((root/'templates/python-template-linux/scripts/init_project.sh').read_bytes()).hexdigest()==artifact['sha256']
if (root/'.git').exists():
    entry=subprocess.check_output(['git','-C',str(root),'ls-files','--stage','templates/python-template-linux'],text=True).split()
    assert entry[:2]==['160000',artifact['version']],entry
PY
    [ "$status" -eq 0 ]
}

@test 'pyinit requer aprovação e cache íntegro para instalação offline' {
    hash=$(pyinit_plan | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --approve "$hash" --offline
    [ "$status" -eq 2 ]
    [ ! -e "$HOME/.local/bin/pyinit" ]
    seed_pyinit
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --approve invalido --offline
    [ "$status" -eq 2 ]
    [ ! -e "$HOME/.local/bin/pyinit" ]
    printf 'corrompido' >"$(find "$XDG_CACHE_HOME/devshell/artifacts" -type f -print -quit)"
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --approve "$hash" --offline
    [ "$status" -eq 2 ]
    [[ "$output" == *'cache corrompido'* ]]
}

@test 'pyinit instala com hash aprovado sem gerar projeto e repete sem mudanças' {
    seed_pyinit
    hash=$(pyinit_plan | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --approve "$hash" --offline --json
    [ "$status" -eq 0 ]
    [ "$(stat -c %a "$HOME/.local/bin/pyinit")" = 755 ]
    cmp "$HOME/.local/bin/pyinit" "$FOUNDRY_ROOT/templates/python-template-linux/scripts/init_project.sh"
    run "$HOME/.local/bin/pyinit" --help
    [ "$status" -eq 0 ]
    [ ! -e "$HOME/.envrc" ]
    [ ! -e "$HOME/.venv" ]
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --approve "$hash" --offline --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert json.load(sys.stdin)["changed"]==0'
    run "$FOUNDRY_ROOT/bin/devshell" doctor --profile science --json
    printf '%s' "$output" | python3 -c 'import json,sys;assert not any("pyinit" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'pyinit recusa destino divergente e doctor não executa o script' {
    seed_pyinit
    mkdir -p "$HOME/.local/bin"
    printf '#!/bin/sh\ntouch "%s"\n' "$HOME/executou" >"$HOME/.local/bin/pyinit"
    chmod 755 "$HOME/.local/bin/pyinit"
    hash=$(pyinit_plan | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --approve "$hash" --offline
    [ "$status" -eq 2 ]
    run "$FOUNDRY_ROOT/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("pyinit" in s and "integridade" in s for s in json.load(sys.stdin)["issues"])'
    [ ! -e "$HOME/executou" ]
    rm "$HOME/.local/bin/pyinit"
    ln -s "$HOME/outro" "$HOME/.local/bin/pyinit"
    run "$FOUNDRY_ROOT/bin/devshell" install --component pyinit --approve "$hash" --offline
    [ "$status" -eq 2 ]
    [ ! -e "$HOME/outro" ]
}
