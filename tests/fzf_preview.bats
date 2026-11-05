#!/usr/bin/env bats
load core_setup

@test 'prévia fzf trata nomes com aspas e substituição de comando como texto' {
    command -v fzf >/dev/null || skip 'fzf não disponível'
    mkdir -p "$XDG_CONFIG_HOME/devshell" "$HOME/.local/bin"
    cp "$FOUNDRY_ROOT/dotfiles/dot_config/devshell/safe-path.py" "$XDG_CONFIG_HOME/devshell/"
    printf 'fzf\n' >"$XDG_CONFIG_HOME/devshell/components"
    export FZF_PREVIEW_LOG="$HOME/preview.log"
    cat >"$HOME/.local/bin/batcat" <<'BIN'
#!/bin/sh
printf '%s\n' "$@" >"$FZF_PREVIEW_LOG"
BIN
    chmod +x "$HOME/.local/bin/batcat"
    export FOUNDRY_ENV="$FOUNDRY_ROOT/dotfiles/dot_config/devshell/env.sh"
    run python3 - <<'PY'
import fcntl, os, pty, select, signal, struct, subprocess, termios, time
from pathlib import Path

env = os.environ.copy()
env.pop('FZF_CTRL_T_OPTS', None)
env['PATH'] = str(Path(env['HOME']) / '.local/bin') + ':' + env['PATH']
env['TERM'] = 'xterm-256color'
env['SHELL'] = '/bin/bash'
result = subprocess.run(['bash', '--noprofile', '--norc', '-ic',
    'source "$FOUNDRY_ENV"; printf "%s" "$FZF_CTRL_T_OPTS"'], env=env, capture_output=True, text=True, check=True)
env['FZF_DEFAULT_OPTS'] = result.stdout
marker = Path(env['HOME']) / 'injected'
candidate = f"$(touch {marker}) ' espaço"
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 110, 0, 0))
def controlling_tty():
    os.setsid()
    fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
process = subprocess.Popen(['fzf'], stdin=subprocess.PIPE, stdout=slave, stderr=slave, env=env, preexec_fn=controlling_tty)
os.close(slave)
try:
    process.stdin.write((candidate + '\n').encode())
    process.stdin.close()
    deadline = time.monotonic() + 8
    log = Path(env['FZF_PREVIEW_LOG'])
    while time.monotonic() < deadline:
        if log.exists() and log.read_text().splitlines()[-1:] == [candidate]:
            break
        ready, _, _ = select.select([master], [], [], 0.1)
        if ready:
            os.read(master, 65536)
    assert log.exists(), 'prévia não executada'
    assert log.read_text().splitlines()[-1] == candidate
    assert not marker.exists(), 'nome executou código'
finally:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=5)
    os.close(master)
PY
    [ "$status" -eq 0 ]
}
