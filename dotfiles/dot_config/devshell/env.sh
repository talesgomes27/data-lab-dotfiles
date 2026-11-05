# shellcheck shell=bash
# Compartilhado somente por Bash e Zsh; Nushell lê os mesmos dados separadamente.
case "${XDG_CONFIG_HOME-}" in /*) _foundry_config=$XDG_CONFIG_HOME ;; *) _foundry_config=$HOME/.config ;; esac
DEVSHELL_COMPONENTS=''
if [ -r "$_foundry_config/devshell/components" ]; then
    IFS= read -r DEVSHELL_COMPONENTS <"$_foundry_config/devshell/components"
fi
devshell_enabled() {
    case " $DEVSHELL_COMPONENTS " in *" $1 "*) return 0 ;; *) return 1 ;; esac
}
case "${XDG_DATA_HOME-}" in /*) _foundry_uv_bin="${XDG_DATA_HOME%/*}/bin" ;; *) _foundry_uv_bin="$HOME/.local/bin" ;; esac
_foundry_uv_bin=${UV_TOOL_BIN_DIR:-${XDG_BIN_HOME:-$_foundry_uv_bin}}
if command -v python3 >/dev/null; then
    while IFS= read -r _foundry_directory; do
        case ":$PATH:" in *":$_foundry_directory:"*) ;; *) export PATH="$_foundry_directory:$PATH" ;; esac
    done < <(python3 "$_foundry_config/devshell/safe-path.py" "$HOME/.local/bin" "$_foundry_uv_bin")
fi
unset _foundry_uv_bin _foundry_directory
export STARSHIP_CONFIG="$_foundry_config/starship.toml"
if [[ $- == *i* ]] && devshell_enabled eza && command -v eza >/dev/null; then
    alias ls='eza --icons=auto --group-directories-first -s Extension'
    alias la='eza --icons=auto --group-directories-first -s Extension -a'
fi
if [[ $- == *i* ]] && devshell_enabled terminal-shortcuts; then
    command -v gst >/dev/null 2>&1 || alias gst='git status --short --branch'
    command -v gs >/dev/null 2>&1 || alias gs='git status --short --branch'
    command -v gl >/dev/null 2>&1 || alias gl='git log --oneline --decorate -10'
    command -v du1 >/dev/null 2>&1 || alias du1='du -h --max-depth=1'
fi
if [[ $- == *i* ]] && devshell_enabled python-tools && command -v uv >/dev/null 2>&1 && ! command -v jlab >/dev/null 2>&1; then
    function jlab { command uv run --locked --group notebook jupyter lab "$@"; }
fi
if [[ $- == *i* ]] && devshell_enabled fzf && [[ ! ${FZF_CTRL_T_OPTS+x} ]]; then
    _foundry_bat=''
    if command -v batcat >/dev/null 2>&1; then
        _foundry_bat=batcat
    elif command -v bat >/dev/null 2>&1; then _foundry_bat=bat; fi
    if [[ -n $_foundry_bat ]]; then
        export FZF_CTRL_T_OPTS="--preview 'if [ -d {} ]; then command ls -lah -- {}; else command $_foundry_bat --color=always --style=numbers --line-range=:100 -- {}; fi'"
    fi
    unset _foundry_bat
fi
unset _foundry_config
