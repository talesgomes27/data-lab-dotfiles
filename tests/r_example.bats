#!/usr/bin/env bats
load core_setup

configure_r_test() {
    export R_USER="$HOME" XDG_CACHE_HOME="$HOME/.cache" RENV_PATHS_ROOT="$HOME/.cache/renv"
    export RENV_CONFIG_SANDBOX_ENABLED=FALSE RENV_CONFIG_REPOS_OVERRIDE=https://cloud.r-project.org
}

@test 'exemplo R cria lock na cópia e recusa reinicializar um projeto existente' {
    command -v Rscript >/dev/null || skip 'R não disponível'
    Rscript --vanilla -e 'quit(status=if (requireNamespace("renv",quietly=TRUE)) 0 else 1)' || skip 'renv não disponível'
    cp -a "$FOUNDRY_ROOT/examples/r-science" "$HOME/project"
    configure_r_test
    cd "$HOME/project"
    run Rscript --vanilla init.R
    [ "$status" -eq 0 ]
    [ -f renv.lock ]
    [ -f .Rprofile ]
    python3 -c 'import json; p=json.load(open("renv.lock")); assert p["Packages"]["renv"]["Version"]'
    cp renv.lock "$BATS_TEST_TMPDIR/original.lock"
    run Rscript --vanilla init.R
    [ "$status" -ne 0 ]
    cmp renv.lock "$BATS_TEST_TMPDIR/original.lock"
}

@test 'exemplo R recusa .Rprofile com symlink quebrado sem criar destino' {
    command -v Rscript >/dev/null || skip 'R não disponível'
    Rscript --vanilla -e 'quit(status=if (requireNamespace("renv",quietly=TRUE)) 0 else 1)' || skip 'renv não disponível'
    cp -a "$FOUNDRY_ROOT/examples/r-science" "$HOME/project"
    configure_r_test
    cd "$HOME/project"
    ln -s "$HOME/target" .Rprofile
    run Rscript --vanilla init.R
    [ "$status" -ne 0 ]
    [ -L .Rprofile ]
    [ ! -e "$HOME/target" ]
    [ ! -e renv.lock ]
}
