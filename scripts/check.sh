#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export PYTHONDONTWRITEBYTECODE=1
for tool in python3 bash shellcheck shfmt bats chezmoi zsh nu uv direnv; do
    command -v "$tool" >/dev/null || {
        printf 'Pré-requisito de teste ausente: %s\n' "$tool" >&2
        exit 3
    }
done
shellcheck -x bin/devshell bootstrap.sh lib/*.sh scripts/*.sh .claude/hooks/*.sh dotfiles/dot_bash_aliases dotfiles/dot_config/devshell/{env.sh,bashrc} dotfiles/dot_config/direnv/lib/*.sh tests/core_setup.bash tests/*.bats
shfmt -d -i 4 -ci bin/devshell bootstrap.sh lib/*.sh scripts/*.sh .claude/hooks/*.sh dotfiles/dot_bash_aliases dotfiles/dot_config/devshell/{env.sh,bashrc} dotfiles/dot_config/direnv/lib/*.sh tests/core_setup.bash
shfmt -ln bats -d -i 4 -ci tests/*.bats
for source in dotfiles/dot_zshenv dotfiles/dot_config/zsh/*; do zsh -n -- "$source"; done
python3 - <<'PY'
import ast
from pathlib import Path
for folder in ('lib', 'tests', 'dotfiles', 'examples'):
    for path in Path(folder).rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
PY
bats --print-output-on-failure tests
python3 -m unittest discover -s tests -p 'test_*.py'
