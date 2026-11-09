#!/usr/bin/env bats
# shellcheck disable=SC2016,SC2030,SC2031 # Scripts Python entre aspas simples; run em helpers do Bats preenche status e output.
bats_require_minimum_version 1.5.0
# R-001 a R-006: histórico e poda de transações em HOME temporária.
load core_setup

state_dir() { printf '%s\n' "$XDG_STATE_HOME/devshell"; }
approval_of() { python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])'; }
apply_version() {
    printf '%s\n' "$1" >"$HOME/.zshenv"
    "$FOUNDRY_ROOT/bin/devshell" apply --approve "$("$FOUNDRY_ROOT/bin/devshell" plan --json | approval_of)" --replace-existing >/dev/null
}
make_transactions() {
    local index
    for ((index = 1; index <= $1; index++)); do apply_version "versão $index"; done
}
tree_digest() { (cd "$(state_dir)" && find . -print0 | sort -z | xargs -0 -I{} sh -c 'printf "%s " "{}"; if [ -f "{}" ]; then sha256sum <"{}"; else echo dir; fi'); }
kept_digest() {
    local id
    cd "$(state_dir)" || return 1
    for id in "$@"; do find "transactions/$id" -type f -exec sha256sum {} +; done | sort
    sha256sum latest current.json
}
prune_plan() { "$FOUNDRY_ROOT/bin/devshell" rollback --prune --keep "$1" --json; }

@test 'R-001 lista transações com status, cadeia e sem criar estado' {
    run "$FOUNDRY_ROOT/bin/devshell" rollback --list --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["transactions"]==[],d'
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
    make_transactions 3
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash" >/dev/null
    before=$(tree_digest)
    home_before=$(find "$HOME" -printf '%p %s %T@\n' | sort)
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" rollback --list --json
    [ "$status" -eq 0 ]
    [ "$(tree_digest)" = "$before" ]
    [ "$(find "$HOME" -printf '%p %s %T@\n' | sort)" = "$home_before" ]
    printf '%s' "$output" | python3 -c '
import json,sys
d=json.load(sys.stdin); t=d["transactions"]
assert len(t)==3, t
chain=sorted((x for x in t if x["chain"] is not None), key=lambda x:x["chain"])
assert [x["chain"] for x in chain]==[0,1], t
assert all(x["status"]=="committed" for x in chain), t
outside=[x for x in t if x["chain"] is None]
assert len(outside)==1 and outside[0]["status"]=="rolled-back", t
assert all(isinstance(x["files"],int) for x in t), t'
    run "$FOUNDRY_ROOT/bin/devshell" rollback --list
    [ "$status" -eq 0 ]
    [[ "$output" == *rolled-back* ]]
}

@test 'R-001 entrada inválida aparece na listagem sem abortar' {
    make_transactions 1
    mkdir -m 700 "$(state_dir)/transactions/0123456789abcdef0123456789abcdef"
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" rollback --list --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c '
import json,sys
t=json.load(sys.stdin)["transactions"]
bad=[x for x in t if x["status"]=="invalida"]
assert len(bad)==1 and bad[0]["reason"], t'
}

@test 'R-002 transação nova registra created em UTC' {
    make_transactions 1
    latest=$(cat "$(state_dir)/latest")
    python3 -c 'import json,re,sys;m=json.load(open(sys.argv[1]));assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",m["created"]),m' "$(state_dir)/transactions/$latest/manifest.json"
}

@test 'R-002 manifesto antigo sem created continua aceito' {
    make_transactions 2
    for manifest in "$(state_dir)"/transactions/*/manifest.json; do
        python3 -c 'import json,sys;p=sys.argv[1];m=json.load(open(p));m.pop("created",None);open(p,"w").write(json.dumps(m))' "$manifest"
    done
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" rollback --list --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert all(x["created"] is None for x in json.load(sys.stdin)["transactions"])'
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    run "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash"
    [ "$status" -eq 0 ]
}

@test 'R-003 plano de poda não altera o estado e avisa sobre os originais' {
    make_transactions 5
    before=$(tree_digest)
    run --separate-stderr prune_plan 2
    [ "$status" -eq 0 ]
    [ "$(tree_digest)" = "$before" ]
    printf '%s' "$output" | python3 -c '
import json,re,sys
d=json.load(sys.stdin); t=d["transactions"]
assert sorted(x["action"] for x in t)==["delete"]*3+["keep"]*2, t
assert sorted(x["chain"] for x in t if x["action"]=="delete")==[2,3,4], t
assert re.fullmatch(r"[0-9a-f]{64}", d["approval"]) and d["bytes"]>0, d
assert any("primeira" in w for w in d["warnings"]), d'
    run "$FOUNDRY_ROOT/bin/devshell" rollback --prune --keep 2 --dry-run --json
    [ "$status" -eq 0 ]
    [ "$(tree_digest)" = "$before" ]
}

@test 'R-003 combinações inválidas de opções saem com 2' {
    for args in '--prune' '--prune --keep 0' '--prune --keep x' '--keep 2' '--list --prune --keep 1' '--list --approve abc' '--list --keep 1'; do
        read -r -a options <<<"$args"
        run "$FOUNDRY_ROOT/bin/devshell" rollback "${options[@]}"
        [ "$status" -eq 2 ]
    done
    for option in --list --prune; do
        run "$FOUNDRY_ROOT/bin/devshell" plan "$option"
        [ "$status" -eq 2 ]
    done
    run "$FOUNDRY_ROOT/bin/devshell" status --keep 1
    [ "$status" -eq 2 ]
    [ -z "$(find "$HOME" -mindepth 1 -print -quit)" ]
}

oldest_id() {
    python3 -c 'import json,os,sys
d=sys.argv[1]
for n in os.listdir(d):
    if json.load(open(f"{d}/{n}/manifest.json"))["previous_latest"] is None: print(n)' "$(state_dir)/transactions"
}
set_status() { python3 -c 'import json,sys;p=sys.argv[1];m=json.load(open(p));m["status"]=sys.argv[2];open(p,"w").write(json.dumps(m))' "$1" "$2"; }
assert_prune_refused() {
    local before
    before=$(tree_digest)
    run prune_plan 1
    [ "$status" -eq 2 ]
    [[ "$output" == *SECURITY* ]]
    [ "$(tree_digest)" = "$before" ]
}

@test 'R-004 transação interrompida ou status desconhecido bloqueiam a poda' {
    make_transactions 3
    manifest="$(state_dir)/transactions/$(oldest_id)/manifest.json"
    for status_value in pending rolling-back desconhecido; do
        set_status "$manifest" "$status_value"
        assert_prune_refused
    done
}

@test 'R-004 interrompida fora da cadeia não sugere rollback' {
    make_transactions 2
    outside=$(cat "$(state_dir)/latest")
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash" >/dev/null
    set_status "$(state_dir)/transactions/$outside/manifest.json" pending
    assert_prune_refused
    [[ "$output" == *'fora da cadeia'* ]]
    [[ "$output" != *'conclua com rollback'* ]]
}

@test 'R-004 entradas inválidas bloqueiam a poda sem alterar o estado' {
    make_transactions 3
    transactions="$(state_dir)/transactions"
    oldest=$(oldest_id)
    : >"$transactions/$oldest/.devshell-temporario"
    assert_prune_refused
    rm "$transactions/$oldest/.devshell-temporario"
    mkdir -m 700 "$transactions/0123456789abcdef0123456789abcdef"
    assert_prune_refused
    rmdir "$transactions/0123456789abcdef0123456789abcdef"
    mkdir -m 700 "$transactions/nao-hex"
    assert_prune_refused
    rmdir "$transactions/nao-hex"
    ln -s "$transactions/$oldest" "$transactions/fedcba9876543210fedcba9876543210"
    assert_prune_refused
    rm "$transactions/fedcba9876543210fedcba9876543210"
    cp "$transactions/$oldest/manifest.json" "$BATS_TEST_TMPDIR/manifest.json"
    printf '{' >"$transactions/$oldest/manifest.json"
    assert_prune_refused
    cp "$BATS_TEST_TMPDIR/manifest.json" "$transactions/$oldest/manifest.json"
    run --separate-stderr prune_plan 1
    [ "$status" -eq 0 ]
    latest=$(cat "$(state_dir)/latest")
    printf '%s' "$output" | python3 -c 'import json,sys;t=json.load(sys.stdin)["transactions"];assert [x["id"] for x in t if x["action"]=="keep"]==[sys.argv[1]],t' "$latest"
}

@test 'R-001 listagem marca symlink, nome inválido e temporário' {
    make_transactions 2
    transactions="$(state_dir)/transactions"
    oldest=$(oldest_id)
    : >"$transactions/$oldest/.devshell-temporario"
    ln -s "$transactions/$oldest" "$transactions/fedcba9876543210fedcba9876543210"
    mkdir -m 700 "$transactions/nao-hex"
    before=$(tree_digest)
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" rollback --list --json
    [ "$status" -eq 0 ]
    [ "$(tree_digest)" = "$before" ]
    printf '%s' "$output" | python3 -c '
import json,sys
t={x["id"]:x for x in json.load(sys.stdin)["transactions"]}
for name in (sys.argv[1], "fedcba9876543210fedcba9876543210", "nao-hex"):
    assert t[name]["status"]=="invalida" and t[name]["reason"], t[name]' "$oldest"
}

@test 'R-003 dry-run descarta a aprovação' {
    make_transactions 2
    hash=$(prune_plan 1 | approval_of)
    before=$(tree_digest)
    run "$FOUNDRY_ROOT/bin/devshell" rollback --prune --keep 1 --dry-run --approve "$hash"
    [ "$status" -eq 0 ]
    [ "$(tree_digest)" = "$before" ]
}

@test 'R-003 sem transação atual o plano avisa que remove todas' {
    make_transactions 1
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash" >/dev/null
    run --separate-stderr prune_plan 3
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert all(x["action"]=="delete" for x in d["transactions"]);assert any("não há transação atual" in w for w in d["warnings"]),d'
}

@test 'R-002 doctor aceita manifesto antigo sem created' {
    make_transactions 1
    for manifest in "$(state_dir)"/transactions/*/manifest.json; do
        python3 -c 'import json,sys;p=sys.argv[1];m=json.load(open(p));m.pop("created",None);open(p,"w").write(json.dumps(m))' "$manifest"
    done
    run --separate-stderr "$FOUNDRY_ROOT/bin/devshell" doctor --json
    [ "$status" -eq 0 ] || [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["operation"]=="doctor";assert not [i for i in d["issues"] if "transação" in i or "manifest" in i],d["issues"]'
}

@test 'R-005 poda aprovada remove só o plano e preserva o restante' {
    make_transactions 4
    plan=$(prune_plan 2)
    hash=$(printf '%s' "$plan" | approval_of)
    kept=$(printf '%s' "$plan" | python3 -c 'import json,sys;print(" ".join(x["id"] for x in json.load(sys.stdin)["transactions"] if x["action"]=="keep"))')
    read -r -a kept_ids <<<"$kept"
    keep_digest=$(kept_digest "${kept_ids[@]}")
    run "$FOUNDRY_ROOT/bin/devshell" rollback --prune --keep 2 --approve "$hash"
    [ "$status" -eq 0 ]
    [ "$(find "$(state_dir)/transactions" -mindepth 1 -maxdepth 1 | wc -l)" -eq 2 ]
    [ "$(kept_digest "${kept_ids[@]}")" = "$keep_digest" ]
    [ -z "$(find "$(state_dir)/pruning" -mindepth 1 -print -quit 2>/dev/null)" ]
}

@test 'R-005 aprovação vencida não remove nada' {
    make_transactions 3
    hash=$(prune_plan 1 | approval_of)
    apply_version 'versão nova'
    before=$(tree_digest)
    run "$FOUNDRY_ROOT/bin/devshell" rollback --prune --keep 1 --approve "$hash"
    [ "$status" -eq 2 ]
    [ "$(tree_digest)" = "$before" ]
    run "$FOUNDRY_ROOT/bin/devshell" rollback --prune --keep 2 --approve "$(prune_plan 1 | approval_of)"
    [ "$status" -eq 2 ]
}

@test 'R-006 rollback da última transação mantida limpa latest e apply segue' {
    make_transactions 3
    "$FOUNDRY_ROOT/bin/devshell" rollback --prune --keep 1 --approve "$(prune_plan 1 | approval_of)" >/dev/null
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | approval_of)
    run "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash"
    [ "$status" -eq 0 ]
    [ ! -e "$(state_dir)/latest" ]
    run "$FOUNDRY_ROOT/bin/devshell" rollback
    [ "$status" -eq 0 ]
    [[ "$output" == *'Nenhuma transação para restaurar.'* ]]
    run apply_version 'depois da poda'
    [ "$status" -eq 0 ]
}
