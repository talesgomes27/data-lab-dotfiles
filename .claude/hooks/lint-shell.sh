#!/usr/bin/env bash
# PostToolUse: formata e confere o arquivo shell editado com os argumentos de scripts/check.sh.
# Saída 2 devolve os apontamentos ao Claude; arquivos de outros tipos passam sem ação.
set -uo pipefail
file=$(jq -r '.tool_input.file_path // empty') || exit 0
[[ -f "$file" ]] || exit 0
cd -- "${CLAUDE_PROJECT_DIR:-.}" || exit 0
case "$file" in
    *.bats) shfmt -ln bats -w -i 4 -ci -- "$file" && shellcheck -x -- "$file" >&2 || exit 2 ;;
    *.sh | *.bash | */bin/devshell | */dotfiles/dot_bash_aliases | */devshell/bashrc)
        shfmt -w -i 4 -ci -- "$file" && shellcheck -x -- "$file" >&2 || exit 2
        ;;
    */dotfiles/dot_zshenv | */dotfiles/dot_config/zsh/*) zsh -n -- "$file" || exit 2 ;;
esac
exit 0
