#!/usr/bin/env bats
load core_setup
setup_file() { command -v chezmoi >/dev/null; }
configure() {
    hash=$("$FOUNDRY_ROOT/bin/devshell" plan --profile personal --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$FOUNDRY_ROOT/bin/devshell" apply --profile personal --approve "$hash"
    mkdir -p "$HOME/.local/bin"
    chmod 700 "$HOME/.local/bin"
}
@test 'Bash adiciona PATH uma vez e preserva inicialização existente' {
    configure
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/bashrc"; source "$XDG_CONFIG_HOME/devshell/bashrc"; printf "%s" "$PATH"'
    [ "$status" -eq 0 ]
    RESULT="$output" python3 -c 'import os;assert os.environ["RESULT"].count(os.environ["HOME"]+"/.local/bin")==1'
}
@test 'Bash recusa diretório bin gravável por outros usuários' {
    configure
    chmod 777 "$HOME/.local/bin"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/bashrc"; printf "%s" "$PATH"'
    [ "$status" -eq 0 ]
    [[ "$output" != *"$HOME/.local/bin"* ]]
}
@test 'Zsh tem completion histórico e PATH sem duplicação' {
    configure
    command -v zsh >/dev/null || skip 'zsh não disponível'
    run zsh -fic '
        if [[ -n ${FOUNDRY_TEST_ZSH_PREFIX:-} ]]; then
            module_path=("$FOUNDRY_TEST_ZSH_PREFIX"/usr/lib/*/zsh/*(N) $module_path)
            fpath=("$FOUNDRY_TEST_ZSH_PREFIX"/usr/share/zsh/functions/*(/N) $fpath)
        fi
        source "$HOME/.zshenv"
        source "$ZDOTDIR/.zshrc"
        source "$ZDOTDIR/.zshrc"
        (( $+functions[compdef] )) || exit 5
        [[ $HISTFILE == "$XDG_STATE_HOME/zsh/history" ]] || exit 6
        print -r -- "$PATH"
    '
    [ "$status" -eq 0 ]
    RESULT="$output" python3 -c 'import os;assert os.environ["RESULT"].count(os.environ["HOME"]+"/.local/bin")==1'
}
@test 'Nushell carrega configuração e processa JSON e CSV' {
    configure
    command -v nu >/dev/null || skip 'nu não disponível'
    # shellcheck disable=SC2016 # Código Nushell literal.
    run nu --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c 'let data = ("[{\"x\":2}]" | from json); let csv = ("a,b\n1,2" | from csv); if (($data | first | get x) != 2) or (($csv | length) != 1) { error make {msg: "dados"} }; $env.PATH | where {|p| $p == ($env.HOME | path join ".local" "bin") } | length'
    [ "$status" -eq 0 ]
    [ "$output" = 1 ]
}
@test 'regressão: Bash recusa ancestral inseguro e symlink no PATH' {
    configure
    mkdir -p "$HOME/shared/bin" "$HOME/private/bin"
    chmod 777 "$HOME/shared"
    chmod 700 "$HOME/shared/bin" "$HOME/private/bin"
    export UV_TOOL_BIN_DIR="$HOME/shared/bin"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/bashrc"; printf "%s" "$PATH"'
    [ "$status" -eq 0 ]
    [[ "$output" != *"$HOME/shared/bin"* ]]
    ln -s "$HOME/private" "$HOME/link"
    export UV_TOOL_BIN_DIR="$HOME/link/bin"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/bashrc"; printf "%s" "$PATH"'
    [[ "$output" != *"$HOME/link/bin"* ]]
}

@test 'PATH recusa diretório com dois-pontos que criaria entrada insegura' {
    configure
    mkdir -p "$HOME/seguro:$HOME/evil" "$HOME/evil"
    chmod 777 "$HOME/evil"
    bad_path="$HOME/seguro:$HOME/evil"
    UV_TOOL_BIN_DIR="$bad_path" run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/env.sh"; case ":$PATH:" in *":$HOME/evil:"*) exit 7 ;; esac'
    [ "$status" -eq 0 ]
    run python3 "$XDG_CONFIG_HOME/devshell/safe-path.py" "$bad_path"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}
@test 'regressão: Nu recusa .local gravável por outros usuários' {
    configure
    command -v nu >/dev/null || skip 'nu não disponível'
    chmod 777 "$HOME/.local"
    # shellcheck disable=SC2016 # Código Nushell literal.
    run nu --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c '$env.PATH | where {|p| $p == ($env.HOME | path join ".local" "bin") } | length'
    [ "$status" -eq 0 ]
    [ "$output" = 0 ]
}

mock_eza() {
    cat >"$HOME/.local/bin/eza" <<'BIN'
#!/bin/sh
printf '<%s>\n' "$@"
BIN
    chmod +x "$HOME/.local/bin/eza"
}

@test 'Bash carrega ls e la via bash_aliases e preserva argumentos do eza' {
    configure
    mock_eza
    # shellcheck disable=SC2016 # Código literal do bashrc da fixture.
    printf 'alias ls="ls --color=auto"\nalias la="ls -A"\nsource "$HOME/.bash_aliases"\n' >"$HOME/.bashrc"
    run bash --noprofile -ic 'ls "pasta com espaços"; la'
    [ "$status" -eq 0 ]
    [[ "$output" == *$'<--icons=auto>\n<--group-directories-first>\n<-s>\n<Extension>\n<pasta com espaços>'* ]]
    [[ "$output" == *$'<-a>\n<--group-directories-first>\n<--sort=ext>\n<--icons=always>'* ]]
}

@test 'Zsh carrega ls e la a partir da mesma configuração compartilhada' {
    configure
    mock_eza
    run zsh -ic 'ls "pasta com espaços"; la'
    [ "$status" -eq 0 ]
    [[ "$output" == *$'<--icons=auto>\n<--group-directories-first>\n<-s>\n<Extension>\n<pasta com espaços>'* ]]
    [[ "$output" == *$'<-a>\n<--group-directories-first>\n<--sort=ext>\n<--icons=always>'* ]]
}

@test 'Bash e Zsh oferecem os seis aliases eza com argumentos preservados' {
    configure
    mock_eza
    # shellcheck disable=SC2016 # Código literal da fixture Ubuntu.
    printf 'alias l="ls -CF"\nsource "$HOME/.bash_aliases"\n' >"$HOME/.bashrc"
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile -ic); else options=(-ic); fi
        run "$shell" "${options[@]}" '
            set -e
            l "pasta com espaços"
            la "pasta com espaços"
            ll "pasta com espaços"
            lla "pasta com espaços"
            lt "pasta com espaços"
            lta "pasta com espaços"
        '
        [ "$status" -eq 0 ]
        [[ "$output" == *$'<--group-directories-first>\n<--sort=ext>\n<--icons=always>\n<pasta com espaços>'* ]]
        [[ "$output" == *$'<-a>\n<--group-directories-first>\n<--sort=ext>\n<--icons=always>\n<pasta com espaços>'* ]]
        [[ "$output" == *$'<-lh>\n<--group-directories-first>\n<--sort=ext>\n<--icons=always>\n<--git>\n<--time-style=relative>\n<pasta com espaços>'* ]]
        [[ "$output" == *$'<-lah>\n<--group-directories-first>\n<--sort=ext>\n<--icons=always>\n<--git>\n<--time-style=relative>\n<pasta com espaços>'* ]]
        [[ "$output" == *$'<--tree>\n<--level=2>\n<--icons=always>\n<--group-directories-first>\n<pasta com espaços>'* ]]
        [[ "$output" == *$'<-a>\n<--tree>\n<--level=2>\n<--icons=always>\n<--group-directories-first>\n<pasta com espaços>'* ]]
        [[ "$output" != *'<-CF>'* ]]
    done
}

@test 'eza real aceita os seis aliases em Bash e Zsh' {
    command -v eza >/dev/null || skip 'eza não disponível'
    configure
    mkdir -p "$HOME/arquivos com espaços/pasta/subpasta"
    touch "$HOME/arquivos com espaços/exemplo.py" "$HOME/arquivos com espaços/.oculto"
    # shellcheck disable=SC2016 # Código literal do bashrc da fixture.
    printf 'source "$HOME/.bash_aliases"\n' >"$HOME/.bashrc"
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile -ic); else options=(-ic); fi
        # shellcheck disable=SC2016 # HOME é expandido pela shell filha.
        run "$shell" "${options[@]}" '
            set -e
            l "$HOME/arquivos com espaços"
            la "$HOME/arquivos com espaços"
            ll "$HOME/arquivos com espaços"
            lla "$HOME/arquivos com espaços"
            lt "$HOME/arquivos com espaços"
            lta "$HOME/arquivos com espaços"
        '
        [ "$status" -eq 0 ]
        [[ "$output" == *'exemplo.py'* && "$output" == *'.oculto'* ]]
    done
}

@test 'Zsh usa zoxide em cd e preserva navegação e comandos z existentes' {
    command -v zoxide >/dev/null || skip 'zoxide não disponível'
    configure
    export _ZO_DATA_DIR="$HOME/zoxide-data"
    mkdir -p "$_ZO_DATA_DIR" "$HOME/pastas/projeto exemplo/subpasta" "$HOME/outra"
    zoxide add "$HOME/pastas/projeto exemplo"
    run zsh -ic '
        # zoxide 0.9.3 usa aliases; versões recentes usam funções.
        (( ($+functions[cd] || $+aliases[cd]) && $+functions[z] && $+functions[zi] )) || exit 10
        cd "$HOME/outra" || exit 11
        cd "projeto exemplo" || exit 12
        [[ "$PWD" == "$HOME/pastas/projeto exemplo" ]] || exit 13
        cd subpasta || exit 14
        cd .. || exit 15
        [[ "$PWD" == "$HOME/pastas/projeto exemplo" ]] || exit 16
        cd - >/dev/null || exit 17
        [[ "$PWD" == "$HOME/pastas/projeto exemplo/subpasta" ]] || exit 18
        z "$HOME/outra" || exit 19
        cd || exit 20
        [[ "$PWD" == "$HOME" ]] || exit 21
    '
    [ "$status" -eq 0 ]
}

@test 'cd permanece nativo fora de shell interativa e sem perfil personal' {
    configure
    run zsh -c '(( $+functions[cd] )) && exit 1; builtin cd "$HOME" && [[ "$PWD" == "$HOME" ]]'
    [ "$status" -eq 0 ]
    printf 'bash zsh git uv chezmoi\n' >"$XDG_CONFIG_HOME/devshell/components"
    run zsh -ic '(( $+functions[cd] )) && exit 1; builtin cd "$HOME" && [[ "$PWD" == "$HOME" ]]'
    [ "$status" -eq 0 ]
}

@test 'Bash substitui o alias l padrão do Ubuntu sem repassar opções GNU ao eza' {
    configure
    mock_eza
    printf '#!/bin/sh\nprintf "GNU_LS_ARGS=%%s\\n" "$*"\n' >"$HOME/.local/bin/ls"
    chmod +x "$HOME/.local/bin/ls"
    # shellcheck disable=SC2016 # Código literal do bashrc da fixture.
    printf 'alias ls="ls --color=auto"\nalias l="ls -CF"\nsource "$HOME/.bash_aliases"\n' >"$HOME/.bashrc"
    run bash --noprofile -ic 'l'
    [ "$status" -eq 0 ]
    [[ "$output" == *$'<--group-directories-first>\n<--sort=ext>\n<--icons=always>'* ]]
    [[ "$output" != *'GNU_LS_ARGS='* && "$output" != *'<-CF>'* ]]
}

@test 'aliases eza exigem shell interativa e componente selecionado' {
    configure
    mock_eza
    run bash --noprofile --norc -c 'source "$XDG_CONFIG_HOME/devshell/env.sh"; alias ls >/dev/null 2>&1'
    [ "$status" -eq 1 ]
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile --norc -c); else options=(-fc); fi
        # shellcheck disable=SC2016 # Código literal executado pela shell filha.
        run "$shell" "${options[@]}" 'source "$XDG_CONFIG_HOME/devshell/env.sh"; for shortcut in l la ll lla lt lta; do alias "$shortcut" >/dev/null 2>&1 && exit 9; done; exit 0'
        [ "$status" -eq 0 ]
    done
    printf 'bash zsh git uv chezmoi\n' >"$XDG_CONFIG_HOME/devshell/components"
    # shellcheck disable=SC2016 # Código literal do bashrc da fixture.
    printf 'alias ls="ls --color=auto"\nalias l="ls -CF"\nsource "$HOME/.bash_aliases"\n' >"$HOME/.bashrc"
    run bash --noprofile -ic '[[ ${BASH_ALIASES[ls]} == "ls --color=auto" && ${BASH_ALIASES[l]} == "ls -CF" ]] || exit 10; for shortcut in la ll lla lt lta; do alias "$shortcut" >/dev/null 2>&1 && exit 9; done; exit 0'
    [ "$status" -eq 0 ]
}

@test 'atalhos interativos preservam comandos existentes e oferecem gst gl du1' {
    configure
    cat >"$HOME/.local/bin/gs" <<'BIN'
#!/bin/sh
printf 'ghostscript existente\n'
BIN
    chmod +x "$HOME/.local/bin/gs"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/env.sh"; alias gst gl du1; gs; alias gs >/dev/null 2>&1 && exit 9; exit 0'
    [ "$status" -eq 0 ]
    [[ "$output" == *"git status --short --branch"* && "$output" == *"git log --oneline --decorate -10"* && "$output" == *"du -h --max-depth=1"* && "$output" == *'ghostscript existente'* ]]
    run zsh -fic 'source "$XDG_CONFIG_HOME/devshell/env.sh"; alias gst gl du1; gs; (( $+aliases[gs] )) && exit 9; exit 0'
    [ "$status" -eq 0 ]
    [[ "$output" == *'ghostscript existente'* && "$output" == *'git status --short --branch'* ]]
}

@test 'atalhos respeitam aliases pessoais previamente definidos' {
    configure
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile --norc -ic); else options=(-fic); fi
        # shellcheck disable=SC2016 # A shell filha expande o diretório XDG.
        run "$shell" "${options[@]}" 'alias gst="echo pessoal"; alias gl="echo historico"; alias du1="echo espaco"; source "$XDG_CONFIG_HOME/devshell/env.sh" || exit 5; alias gst gl du1'
        [ "$status" -eq 0 ]
        [[ "$output" == *'echo pessoal'* && "$output" == *'echo historico'* && "$output" == *'echo espaco'* ]]
    done
}

@test 'prévia fzf é opcional e preserva configuração existente' {
    configure
    printf '#!/bin/sh\nexit 0\n' >"$HOME/.local/bin/batcat"
    chmod +x "$HOME/.local/bin/batcat"
    run bash --noprofile --norc -ic 'unset FZF_CTRL_T_OPTS; source "$XDG_CONFIG_HOME/devshell/env.sh"; printf "%s" "${FZF_CTRL_T_OPTS-}"'
    [ "$status" -eq 0 ]
    [[ "$output" == *'--preview'* && "$output" == *'batcat'* ]]
    run bash --noprofile --norc -ic 'FZF_CTRL_T_OPTS="minha-opcao"; source "$XDG_CONFIG_HOME/devshell/env.sh"; printf "%s" "$FZF_CTRL_T_OPTS"'
    [ "$status" -eq 0 ]
    [[ "$output" == *'minha-opcao'* && "$output" != *'--preview'* ]]
}

@test 'jlab executa Jupyter no grupo notebook e preserva argumentos' {
    configure
    printf 'bash zsh uv python-tools\n' >"$XDG_CONFIG_HOME/devshell/components"
    cat >"$HOME/.local/bin/uv" <<'BIN'
#!/bin/sh
printf '<%s>\n' "$@"
BIN
    chmod +x "$HOME/.local/bin/uv"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/env.sh"; jlab --no-browser "arquivo com espaços"'
    [ "$status" -eq 0 ]
    [[ "$output" == *$'<run>\n<--locked>\n<--group>\n<notebook>\n<jupyter>\n<lab>\n<--no-browser>\n<arquivo com espaços>'* ]]
    run bash --noprofile --norc -c 'source "$XDG_CONFIG_HOME/devshell/env.sh"; command -v jlab >/dev/null'
    [ "$status" -eq 1 ]
}

@test 'alias jlab existente não impede inicialização Bash ou Zsh' {
    configure
    printf 'bash zsh uv python-tools fzf\n' >"$XDG_CONFIG_HOME/devshell/components"
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile --norc -ic); else options=(-fic); fi
        # shellcheck disable=SC2016 # A shell filha expande o diretório XDG.
        run "$shell" "${options[@]}" 'alias jlab="echo existente"; source "$XDG_CONFIG_HOME/devshell/env.sh" || exit 5; alias jlab; printf "\nFIM_OK\n"'
        [ "$status" -eq 0 ]
        [[ "$output" == *'echo existente'* && "$output" == *FIM_OK* ]]
    done
}

@test 'Starship mostra Git, ambiente Python, duração e falha quando presentes' {
    command -v starship >/dev/null || skip 'starship não disponível'
    mkdir -p "$HOME/project" "$HOME/envs/demo"
    git -C "$HOME/project" init -q
    touch "$HOME/project/untracked.txt"
    branch=$(git -C "$HOME/project" symbolic-ref --short HEAD)
    run env TERM=xterm-256color STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" \
        VIRTUAL_ENV="$HOME/envs/demo" starship prompt --path "$HOME/project" --status 7 --cmd-duration 3000
    [ "$status" -eq 0 ]
    [[ "$output" == *"$branch"* && "$output" == *'?'* && "$output" == *'(demo)'* ]]
    [[ "$output" == *'3s'* && "$output" == *'erro 7'* && "$output" == *'❯'* && "$output" == *''* ]]
    [[ "$output" != *'Unknown'* && "$output" != *'ERROR'* ]]
    run env -u VIRTUAL_ENV TERM=xterm-256color STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" \
        starship prompt --path "$HOME" --status 0 --cmd-duration 100
    [ "$status" -eq 0 ]
    [[ "$output" != *'erro '* && "$output" != *'em '* && "$output" != *'(demo)'* ]]
}

@test 'Starship reconhece projetos R, JavaScript, TypeScript, Quarto e Astro' {
    command -v starship >/dev/null && command -v R >/dev/null && command -v node >/dev/null && command -v quarto >/dev/null || skip 'ferramentas de linguagem ausentes'
    mkdir -p "$HOME/tech"
    export STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" TERM=xterm-256color
    unset VIRTUAL_ENV
    touch "$HOME/tech/example.R" "$HOME/tech/example.qmd" "$HOME/tech/astro.config.mjs" "$HOME/tech/example.js"
    run starship prompt --path "$HOME/tech" --status 0
    [ "$status" -eq 0 ]
    [[ "$output" == *'R v'* && "$output" == *'Node v'* && "$output" == *'JS'* && "$output" == *'Quarto v'* && "$output" == *'Astro'* ]]
    rm "$HOME/tech/example.js" "$HOME/tech/astro.config.mjs"
    touch "$HOME/tech/example.ts"
    run starship prompt --path "$HOME/tech" --status 0
    [ "$status" -eq 0 ]
    [[ "$output" == *'Node v'* && "$output" == *'TS'* && "$output" != *'Astro'* && "$output" != *'JS'* ]]
    rm "$HOME/tech/example.ts"
    touch "$HOME/tech/example.tsx"
    run starship prompt --path "$HOME/tech" --status 0
    [ "$status" -eq 0 ]
    [[ "$output" == *'Node v'* ]]
}

@test 'Starship cobre linguagens com executáveis simulados e sem downloads' {
    command -v starship >/dev/null || skip 'starship não disponível'
    mkdir -p "$HOME/tech" "$BATS_TEST_TMPDIR/languages"
    printf '#!/bin/sh\nprintf "R version 4.5.0\\n"\n' >"$BATS_TEST_TMPDIR/languages/R"
    printf '#!/bin/sh\nprintf "v22.1.0\\n"\n' >"$BATS_TEST_TMPDIR/languages/node"
    printf '#!/bin/sh\nprintf "1.6.0\\n"\n' >"$BATS_TEST_TMPDIR/languages/quarto"
    chmod +x "$BATS_TEST_TMPDIR/languages/"*
    touch "$HOME/tech/example.R" "$HOME/tech/example.qmd" "$HOME/tech/astro.config.mjs" "$HOME/tech/example.tsx"
    run env -u VIRTUAL_ENV PATH="$BATS_TEST_TMPDIR/languages:$PATH" STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" TERM=xterm-256color starship prompt --path "$HOME/tech" --status 0
    [ "$status" -eq 0 ]
    [[ "$output" == *'R v4.5.0'* && "$output" == *'Node v22.1.0'* && "$output" == *'Quarto v1.6.0'* && "$output" == *'Astro'* && "$output" == *'TS'* && "$output" == *'JS'* ]]
}

@test 'Starship detecta Java Rust e Go e oculta módulos fora dos projetos' {
    command -v starship >/dev/null || skip 'starship não disponível'
    local language marker expected
    mkdir -p "$BATS_TEST_TMPDIR/languages" "$HOME/tech" "$HOME/neutral"
    printf '#!/bin/sh\nprintf "OpenJDK 64-Bit Server VM (21.0.2+fixture) for linux-amd64 JRE (21.0.2+fixture), built on fixture\\n" >&2\n' >"$BATS_TEST_TMPDIR/languages/java"
    printf '#!/bin/sh\nprintf "rustc 1.85.0 (fixture 2025-02-20)\\n"\n' >"$BATS_TEST_TMPDIR/languages/rustc"
    printf '#!/bin/sh\nexit 1\n' >"$BATS_TEST_TMPDIR/languages/rustup"
    printf '#!/bin/sh\nprintf "go version go1.23.2 linux/amd64\\n"\n' >"$BATS_TEST_TMPDIR/languages/go"
    chmod +x "$BATS_TEST_TMPDIR/languages/"*
    for entry in 'Java Main.java' 'Java pom.xml' 'Java build.gradle.kts' 'Rust main.rs' 'Rust Cargo.toml' 'Go main.go' 'Go go.mod' 'Go go.work'; do
        read -r language marker <<<"$entry"
        touch "$HOME/tech/$marker"
        run env -u VIRTUAL_ENV -u JAVA_HOME -u RUSTUP_TOOLCHAIN PATH="$BATS_TEST_TMPDIR/languages:$PATH" STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" TERM=xterm-256color starship prompt --path "$HOME/tech" --status 0
        [ "$status" -eq 0 ]
        case "$language" in
            Java) expected='Java v21.0.2' ;;
            Rust) expected='Rust v1.85.0' ;;
            Go) expected='Go v1.23.2' ;;
        esac
        printf '%s: %s\n' "$marker" "$output"
        [[ "$output" == *"$expected"* && "$output" == *''* ]]
        [[ "$output" != *'WARN'* && "$output" != *'ERROR'* ]]
        rm "$HOME/tech/$marker"
    done
    run env -u VIRTUAL_ENV -u JAVA_HOME -u RUSTUP_TOOLCHAIN PATH="$BATS_TEST_TMPDIR/languages:$PATH" STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" TERM=xterm-256color starship prompt --path "$HOME/neutral" --status 0
    [ "$status" -eq 0 ]
    [[ "$output" != *'Java '* && "$output" != *'Rust '* && "$output" != *'Go '* ]]
    touch "$HOME/tech/Main.java" "$HOME/tech/main.rs" "$HOME/tech/main.go"
    run env -u VIRTUAL_ENV -u JAVA_HOME -u RUSTUP_TOOLCHAIN PATH="$BATS_TEST_TMPDIR/languages:$PATH" STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" TERM=xterm-256color starship prompt --path "$HOME/tech" --status 0
    [ "$status" -eq 0 ]
    [[ "$output" == *'Java v21.0.2'* && "$output" == *'Rust v1.85.0'* && "$output" == *'Go v1.23.2'* ]]
    for language in java rustc go; do
        printf '#!/bin/sh\nexit 127\n' >"$BATS_TEST_TMPDIR/languages/$language"
    done
    run env -u VIRTUAL_ENV -u JAVA_HOME -u RUSTUP_TOOLCHAIN PATH="$BATS_TEST_TMPDIR/languages:$PATH" STARSHIP_CONFIG="$FOUNDRY_ROOT/dotfiles/dot_config/starship.toml" TERM=xterm-256color starship prompt --path "$HOME/tech" --status 0
    [ "$status" -eq 0 ]
    [[ "$output" != *'v21.0.2'* && "$output" != *'v1.85.0'* && "$output" != *'v1.23.2'* ]]
    [[ "$output" != *'WARN'* && "$output" != *'ERROR'* ]]
}
