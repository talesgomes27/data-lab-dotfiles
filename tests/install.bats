#!/usr/bin/env bats
load core_setup
@test 'instalação sem aprovação apenas descreve artefatos fixados' {
    run "$FOUNDRY_ROOT/bin/devshell" install --component uv --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["artifacts"][0]["sha256"];assert "releases/download/" in p["artifacts"][0]["url"]'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'fonte planeja download fixado e cache sem escrever na HOME' {
    run "$FOUNDRY_ROOT/bin/devshell" install --component firacode --profile personal --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys,os;p=json.load(sys.stdin);assert p["destination"]==os.environ["XDG_DATA_HOME"]+"/fonts/FiraCodeNerdFont";a=p["artifacts"][0];assert a["format"]=="zip" and len(a["sha256"])==64;assert p["commands"]==[["fc-cache","-f",p["destination"]]]'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'python planeja interpretadores sem bin genérico e ferramentas isoladas' {
    run "$FOUNDRY_ROOT/bin/devshell" install --component python --profile science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);c=p["commands"];assert "--no-bin" in c[0];assert not any("tool" in r for r in c);pip=[r for r in c if "pip" in r];assert len(pip)==3 and all("--require-hashes" in r and r[r.index("-r")+1].endswith(".txt") for r in pip);assert {t["state"] for t in p["tools"]}=={"ausente"};assert all("--force" not in r for r in c)'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'instalador offline sem cache falha sem baixar ou criar binários' {
    hash=$("$FOUNDRY_ROOT/bin/devshell" install --component uv --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" install --component uv --approve "$hash" --offline
    [ "$status" -eq 2 ]
    [ ! -d "$HOME/.local/bin" ]
}
@test 'instalador não oferece arquitetura inexistente nem alvo desconhecido' {
    export DEVSHELL_ARCH=sparc
    run "$FOUNDRY_ROOT/bin/devshell" install --component uv
    [ "$status" -eq 2 ]
    run "$FOUNDRY_ROOT/bin/devshell" install --component untrusted
    [ "$status" -eq 2 ]
}
prepare_uv() {
    export PATH="$FOUNDRY_ROOT/tests/fixtures/bin:$PATH" FOUNDRY_UV_LOG="$BATS_TEST_TMPDIR/uv.log"
}
@test 'regressão: Python minimal não executa tool install vazio' {
    prepare_uv
    hash=$("$FOUNDRY_ROOT/bin/devshell" install --component python --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" install --component python --approve "$hash" --offline
    [ "$status" -eq 0 ]
    python3 -c 'import json,os;calls=[json.loads(s)["args"] for s in open(os.environ["FOUNDRY_UV_LOG"])];assert len(calls)==2;assert all("tool" not in c and "--offline" in c and "--no-bin" in c for c in calls)'
}
@test 'regressão: uv executa somente nos diretórios aprovados com XDG_BIN_HOME' {
    prepare_uv
    unset UV_TOOL_BIN_DIR
    export XDG_BIN_HOME="$HOME/custom/bin"
    hash=$("$FOUNDRY_ROOT/bin/devshell" install --component python --profile science --json | python3 -c 'import json,sys,os;p=json.load(sys.stdin);assert p["directories"]["UV_TOOL_BIN_DIR"]==os.environ["XDG_BIN_HOME"];print(p["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" install --component python --profile science --approve "$hash"
    [ "$status" -eq 0 ]
    python3 -c 'import json,os;calls=[json.loads(s) for s in open(os.environ["FOUNDRY_UV_LOG"])];assert len(calls)==8;assert all(c["dirs"]["UV_TOOL_BIN_DIR"]==os.environ["XDG_BIN_HOME"] for c in calls if "python" in c["args"][2:4]);assert all(c["dirs"]["UV_TOOL_BIN_DIR"] is None for c in calls if "venv" in c["args"] or "pip" in c["args"])'
    for tool in ruff pre-commit ipython; do [ "$(readlink "$XDG_BIN_HOME/$tool")" = "$XDG_DATA_HOME/devshell/tools/$tool/bin/$tool" ]; done
}
@test 'instalação Python recusa diretório binário que não cabe no PATH' {
    export UV_TOOL_BIN_DIR="$HOME/bin:outro"
    run "$FOUNDRY_ROOT/bin/devshell" install --component python --profile science --json
    [ "$status" -eq 2 ]
    [[ "$output" == *'UV_TOOL_BIN_DIR'* && "$output" == *'PATH'* ]]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}
@test 'falha uv propaga código e interrompe instalações restantes' {
    prepare_uv
    export FOUNDRY_UV_FAIL=1
    hash=$("$FOUNDRY_ROOT/bin/devshell" install --component python --profile science --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" install --component python --profile science --approve "$hash"
    [ "$status" -eq 7 ]
    [ "$(wc -l <"$FOUNDRY_UV_LOG")" -eq 1 ]
}
