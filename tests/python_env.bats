#!/usr/bin/env bats
# shellcheck disable=SC2016 # Programas literais executados pelas shells filhas.
load core_setup

prepare_python_envs() {
    local hash
    hash=$("$FOUNDRY_ROOT/bin/devshell" plan --profile personal --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$FOUNDRY_ROOT/bin/devshell" apply --profile personal --approve "$hash"
    # uv usa somente o interpretador já instalado, sem resolver ou baixar pacotes.
    export TEST_GENERAL="$XDG_DATA_HOME/devshell/venvs/geral"
    uv --no-config --offline venv --no-project --no-python-downloads --python "$(command -v python3)" "$TEST_GENERAL"
    export TEST_PROJECT="$HOME/projeto com espaços"
    mkdir -p "$TEST_PROJECT/sub" "$HOME/outro"
    uv --no-config --offline venv --no-project --no-python-downloads --python "$(command -v python3)" "$TEST_PROJECT/.venv"
    printf 'use devshell_python\n' >"$TEST_PROJECT/.envrc"
    printf 'touch "$HOME/activate-executado"\n' >"$TEST_PROJECT/.venv/bin/activate"
    export TERM=xterm-256color
    cd "$HOME" || return
}

@test 'ambiente pessoal seleciona Python real em Bash e Zsh sem duplicar PATH' {
    prepare_python_envs
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile --norc -ic); else options=(-fic); fi
        run "$shell" "${options[@]}" '
            source "$XDG_CONFIG_HOME/devshell/env.sh"
            source "$XDG_CONFIG_HOME/devshell/env.sh"
            [[ $VIRTUAL_ENV == "$TEST_GENERAL" ]] || exit 10
            python -c '\''import os,sys; assert sys.prefix == os.environ["TEST_GENERAL"]; assert os.environ["PATH"].split(":").count(sys.prefix+"/bin") == 1'\''
        '
        [ "$status" -eq 0 ]
    done
}

@test 'validação de venv rejeita diretório comum, configuração ausente e Python ausente' {
    prepare_python_envs
    helper="$XDG_CONFIG_HOME/devshell/safe-path.py"
    run python3 "$helper" --venv "$TEST_GENERAL/bin"
    [ "$output" = "$TEST_GENERAL/bin" ]
    mv "$TEST_GENERAL/pyvenv.cfg" "$TEST_GENERAL/config-backup"
    ln -s config-backup "$TEST_GENERAL/pyvenv.cfg"
    run python3 "$helper" --venv "$TEST_GENERAL/bin"
    [ -z "$output" ]
    rm "$TEST_GENERAL/pyvenv.cfg"
    run python3 "$helper" --venv "$TEST_GENERAL/bin"
    [ -z "$output" ]
    touch "$TEST_GENERAL/pyvenv.cfg"
    rm "$TEST_GENERAL/bin/python"
    run python3 "$helper" --venv "$TEST_GENERAL/bin"
    [ -z "$output" ]
    mkdir "$TEST_GENERAL/bin/python"
    run python3 "$helper" --venv "$TEST_GENERAL/bin"
    [ -z "$output" ]
}

@test 'ambiente pessoal respeita ativação manual, Conda, shell não interativa e perfil work' {
    prepare_python_envs
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile --norc -ic); else options=(-fic); fi
        run env VIRTUAL_ENV="$HOME/manual" "$shell" "${options[@]}" 'source "$XDG_CONFIG_HOME/devshell/env.sh"; [[ $VIRTUAL_ENV == "$HOME/manual" && :$PATH: != *":$TEST_GENERAL/bin:"* ]]'
        [ "$status" -eq 0 ]
        run env CONDA_PREFIX="$HOME/conda" "$shell" "${options[@]}" 'source "$XDG_CONFIG_HOME/devshell/env.sh"; [[ -z ${VIRTUAL_ENV-} && :$PATH: != *":$TEST_GENERAL/bin:"* ]]'
        [ "$status" -eq 0 ]
        run "$shell" -c 'source "$XDG_CONFIG_HOME/devshell/env.sh"; [[ -z ${VIRTUAL_ENV-} && :$PATH: != *":$TEST_GENERAL/bin:"* ]]'
        [ "$status" -eq 0 ]
    done
    printf 'bash zsh git uv chezmoi\n' >"$XDG_CONFIG_HOME/devshell/components"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/env.sh"; [[ -z ${VIRTUAL_ENV-} ]]'
    [ "$status" -eq 0 ]
}

@test 'ativação herdada mantém prioridade do interpretador sobre binários de usuário' {
    prepare_python_envs
    mkdir -p "$HOME/.local/bin"
    ln -s "$(command -v python3)" "$HOME/.local/bin/python3"
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then options=(--noprofile --norc -ic); else options=(-fic); fi
        run env VIRTUAL_ENV="$TEST_PROJECT/.venv" PATH="$TEST_PROJECT/.venv/bin:$PATH" "$shell" "${options[@]}" '
            source "$XDG_CONFIG_HOME/devshell/env.sh"
            python3 -c '\''import os,sys; assert sys.prefix == os.environ["TEST_PROJECT"]+"/.venv"'\''
        '
        [ "$status" -eq 0 ]
    done
    run env VIRTUAL_ENV="$TEST_PROJECT/.venv" PATH="$TEST_PROJECT/.venv/bin:$PATH" nu -i --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c 'python3 -c "import os,sys; assert sys.prefix == os.environ[\"TEST_PROJECT\"]+\"/.venv\""'
    [ "$status" -eq 0 ]
}

@test 'ambiente pessoal inseguro ou ausente não é ativado nem recriado' {
    prepare_python_envs
    chmod 777 "$TEST_GENERAL"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/env.sh"; [[ -z ${VIRTUAL_ENV-} ]]'
    [ "$status" -eq 0 ]
    chmod 700 "$TEST_GENERAL"
    mv "$TEST_GENERAL" "$TEST_GENERAL.backup"
    run bash --noprofile --norc -ic 'source "$XDG_CONFIG_HOME/devshell/env.sh"; [[ -z ${VIRTUAL_ENV-} && ! -e $TEST_GENERAL ]]'
    [ "$status" -eq 0 ]
}

@test 'direnv troca projeto, subpasta e retorno sem executar activate' {
    prepare_python_envs
    direnv allow "$TEST_PROJECT"
    for shell in bash zsh; do
        if [[ $shell == bash ]]; then
            options=(--noprofile --norc -ic)
            export TEST_SHELL_CONFIG="$XDG_CONFIG_HOME/devshell/bashrc"
        else
            options=(-fic)
            export TEST_SHELL_CONFIG="$XDG_CONFIG_HOME/zsh/.zshrc"
        fi
        run "$shell" "${options[@]}" '
            source "$TEST_SHELL_CONFIG"
            cd "$TEST_PROJECT"; _direnv_hook
            [[ $VIRTUAL_ENV == "$TEST_PROJECT/.venv" && :$PATH: != *":$TEST_GENERAL/bin:"* ]] || exit 10
            python -c '\''import os,sys; assert sys.prefix == os.environ["TEST_PROJECT"]+"/.venv"'\'' || exit 11
            cd sub; _direnv_hook
            [[ $VIRTUAL_ENV == "$TEST_PROJECT/.venv" ]] || exit 12
            cd "$HOME/outro"; _direnv_hook
            [[ $VIRTUAL_ENV == "$TEST_GENERAL" ]] || exit 13
            cd - >/dev/null; _direnv_hook
            [[ $VIRTUAL_ENV == "$TEST_PROJECT/.venv" ]] || exit 14
            cd "$HOME"; _direnv_hook
            [[ $VIRTUAL_ENV == "$TEST_GENERAL" && ! -e $HOME/activate-executado ]] || exit 15
        '
        [ "$status" -eq 0 ]
    done
}

@test 'direnv bloqueado não executa envrc nem seleciona o projeto' {
    prepare_python_envs
    printf 'touch "$HOME/envrc-executado"\n' >>"$TEST_PROJECT/.envrc"
    run bash --noprofile --norc -ic '
        source "$XDG_CONFIG_HOME/devshell/bashrc"
        cd "$TEST_PROJECT"; _direnv_hook
        [[ $VIRTUAL_ENV == "$TEST_GENERAL" && ! -e $HOME/envrc-executado ]]
    '
    [ "$status" -eq 0 ]
}

@test 'direnv remove ambiente pessoal quando venv falta e observa sua criação' {
    prepare_python_envs
    mv "$TEST_PROJECT/.venv" "$TEST_PROJECT/guardada"
    direnv allow "$TEST_PROJECT"
    run bash --noprofile --norc -ic '
        source "$XDG_CONFIG_HOME/devshell/bashrc"
        cd "$TEST_PROJECT"; _direnv_hook
        [[ -z ${VIRTUAL_ENV-} && :$PATH: != *":$TEST_GENERAL/bin:"* ]] || exit 10
        [[ ! -e .venv && -f guardada/pyvenv.cfg ]] || exit 11
        mv guardada .venv
        direnv reload; _direnv_hook
        [[ $VIRTUAL_ENV == "$TEST_PROJECT/.venv" ]] || exit 12
        cd "$HOME"; _direnv_hook
        [[ $VIRTUAL_ENV == "$TEST_GENERAL" ]]
    '
    [ "$status" -eq 0 ]
}

@test 'direnv recusa venv por symlink e caminhos inseguros' {
    prepare_python_envs
    mv "$TEST_PROJECT/.venv" "$TEST_PROJECT/guardada"
    ln -s guardada "$TEST_PROJECT/.venv"
    direnv allow "$TEST_PROJECT"
    run bash --noprofile --norc -ic '
        source "$XDG_CONFIG_HOME/devshell/bashrc"
        cd "$TEST_PROJECT"; _direnv_hook
        [[ -z ${VIRTUAL_ENV-} && :$PATH: != *":$TEST_GENERAL/bin:"* ]]
    '
    [ "$status" -eq 0 ]
}

@test 'configuração direnv acompanha o componente e rollback preserva ambientes' {
    prepare_python_envs
    [ -f "$XDG_CONFIG_HOME/direnv/lib/devshell-python.sh" ]
    hash=$("$FOUNDRY_ROOT/bin/devshell" rollback --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$FOUNDRY_ROOT/bin/devshell" rollback --approve "$hash"
    [ "$status" -eq 0 ]
    [ ! -e "$XDG_CONFIG_HOME/direnv/lib/devshell-python.sh" ]
    [ -f "$TEST_GENERAL/pyvenv.cfg" ]
    [ -f "$TEST_PROJECT/.venv/pyvenv.cfg" ]
    run "$FOUNDRY_ROOT/bin/devshell" plan --profile work --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys; assert all("/direnv/" not in f["path"] for f in json.load(sys.stdin)["files"])'
}

@test 'Nushell seleciona ambiente pessoal somente interativo e preserva Conda' {
    prepare_python_envs
    # shellcheck disable=SC2016 # Código Nushell literal.
    run nu -i --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c 'if $env.VIRTUAL_ENV? != $env.TEST_GENERAL { error make {msg: "env pessoal"} }; python -c "import os,sys; assert sys.prefix == os.environ[\"TEST_GENERAL\"]"'
    [ "$status" -eq 0 ]
    # shellcheck disable=SC2016 # Código Nushell literal.
    run nu --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c 'if $env.VIRTUAL_ENV? != null { error make {msg: "não interativo"} }'
    [ "$status" -eq 0 ]
    # shellcheck disable=SC2016 # Código Nushell literal.
    run env CONDA_PREFIX="$HOME/conda" nu -i --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c 'if $env.VIRTUAL_ENV? != null { error make {msg: "Conda"} }'
    [ "$status" -eq 0 ]
}

@test 'PTY: Bash Zsh e Nushell trocam projetos e abrem diretamente na venv autorizada' {
    prepare_python_envs
    direnv allow "$TEST_PROJECT"
    export TEST_OTHER="$HOME/outro"
    uv --no-config --offline venv --no-project --no-python-downloads --python "$(command -v python3)" "$TEST_OTHER/.venv"
    printf 'use devshell_python\n' >"$TEST_OTHER/.envrc"
    direnv allow "$TEST_OTHER"
    run python3 - <<'PY'
import errno, fcntl, os, pty, select, shlex, shutil, signal, struct, subprocess, termios, time
from pathlib import Path

home = Path(os.environ['HOME'])
config = Path(os.environ['XDG_CONFIG_HOME'])
project = Path(os.environ['TEST_PROJECT'])
other = Path(os.environ['TEST_OTHER'])
general = os.environ['TEST_GENERAL']
shared = home / 'completion-inseguro'
shared.mkdir()
shared.chmod(0o777)
(shared / '_fixture').write_text('#compdef fixture\n')
zsh_fpath = subprocess.check_output(['zsh', '-dfc', 'print -r -- "${(j.:.)fpath}"'], text=True).strip()
shells = {
    'bash': ['bash', '--noprofile', '--rcfile', str(config / 'devshell/bashrc'), '-i'],
    # Carregar o rc gerenciado sem o compinit global da distribuição.
    'zsh': ['zsh', '-d', '-i'],
    'nu': ['nu', '--env-config', str(config / 'nushell/env.nu'), '--config', str(config / 'nushell/config.nu'), '-i'],
}
for name, command in shells.items():
    for start in (home, project):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 160, 0, 0))
        def controlling_tty():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        environment = os.environ.copy()
        if name == 'zsh':
            environment['FPATH'] = str(shared) + ':' + zsh_fpath
        process = subprocess.Popen(command, cwd=start, stdin=slave, stdout=slave, stderr=slave,
                                   preexec_fn=controlling_tty, env=environment)
        os.close(slave)
        transcript = bytearray()
        query_tail = b''
        def expect(text):
            global query_tail
            deadline = time.monotonic() + 12
            while text.encode() not in transcript:
                assert time.monotonic() < deadline, (name, start, text, transcript.decode(errors='replace'))
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                        transcript.extend(chunk)
                        queries = query_tail + chunk
                        for _ in range(queries.count(b'\x1b[6n')):
                            os.write(master, b'\x1b[1;1R')
                        query_tail = queries[-3:]
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                        raise AssertionError((name, transcript.decode(errors='replace'))) from exc
            end = transcript.index(text.encode()) + len(text.encode())
            del transcript[:end]
        def send(command):
            if name == 'nu':
                expect('\x1b]133;B\x1b\\')
            os.write(master, (command + '\n').encode())
        def check(tag, expected):
            send('python3 -c ' + shlex.quote(
                f'import os,sys; assert sys.prefix == "{expected}"; '
                f'print("RESULT_"+"{tag}="+os.environ.get("VIRTUAL_ENV", ""))'))
            expect(f'RESULT_{tag}={expected}\r\n')
        try:
            check('START', str(project / '.venv') if start == project else general)
            send('cd ' + shlex.quote(str(project / 'sub')))
            check('SUB', str(project / '.venv'))
            send('cd ' + shlex.quote(str(other)))
            check('OTHER', str(other / '.venv'))
            send('cd ' + shlex.quote(str(home)))
            check('HOME', general)
            if name == 'zsh' and shutil.which('zoxide'):
                send('z ' + shlex.quote(str(project)))
                check('ZOXIDE', str(project / '.venv'))
                send('cd ' + shlex.quote(str(home)))
                check('AFTER_ZOXIDE', general)
            assert not (home / 'activate-executado').exists()
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
            os.close(master)
PY
    [ "$status" -eq 0 ]
}

@test 'direnv remove o caminho pessoal literalmente mesmo com metacaracteres no XDG' {
    export XDG_DATA_HOME="$HOME/dados [x]*"
    prepare_python_envs
    direnv allow "$TEST_PROJECT"
    run bash --noprofile --norc -ic '
        source "$XDG_CONFIG_HOME/devshell/bashrc"
        cd "$TEST_PROJECT"; _direnv_hook
        [[ $VIRTUAL_ENV == "$TEST_PROJECT/.venv" && :$PATH: != *":$TEST_GENERAL/bin:"* ]] || exit 10
        cd "$HOME"; _direnv_hook
        [[ $VIRTUAL_ENV == "$TEST_GENERAL" ]]
    '
    [ "$status" -eq 0 ]
}

@test 'Nushell aplica remoções do direnv sem perder código de saída e restaura geral' {
    prepare_python_envs
    mv "$TEST_PROJECT/.venv" "$TEST_PROJECT/guardada"
    direnv allow "$TEST_PROJECT"
    run nu -i --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c '
        cd $env.TEST_PROJECT
        $env.LAST_EXIT_CODE = 1
        for hook in $env.config.hooks.pre_prompt { do --env $hook }
        if $env.LAST_EXIT_CODE != 1 { error make {msg: "status perdido"} }
        if $env.VIRTUAL_ENV? != null { error make {msg: "ambiente pessoal retido"} }
        if (($env.TEST_GENERAL | path join "bin") in $env.PATH) { error make {msg: "PATH pessoal retido"} }
        cd $env.HOME
        for hook in $env.config.hooks.pre_prompt { do --env $hook }
        if $env.VIRTUAL_ENV? != $env.TEST_GENERAL { error make {msg: "sem retorno"} }
        if (($env.PATH | describe) !~ "list") { error make {msg: "PATH deixou de ser lista"} }
        ^true
    '
    [ "$status" -eq 0 ]
}

@test 'Nushell mantém prompt e status quando direnv bloqueia envrc não autorizado' {
    prepare_python_envs
    printf 'touch "$HOME/envrc-executado"\n' >>"$TEST_PROJECT/.envrc"
    run nu -i --env-config "$XDG_CONFIG_HOME/nushell/env.nu" --config "$XDG_CONFIG_HOME/nushell/config.nu" -c '
        cd $env.TEST_PROJECT
        $env.LAST_EXIT_CODE = 7
        for hook in $env.config.hooks.pre_prompt { do --env $hook }
        if $env.LAST_EXIT_CODE != 7 { error make {msg: "status perdido"} }
        if $env.VIRTUAL_ENV? != $env.TEST_GENERAL { error make {msg: "bloqueio ignorado"} }
        if ($env.HOME | path join "envrc-executado" | path exists) { error make {msg: "envrc executado"} }
        ^true
    '
    [ "$status" -eq 0 ]
}

@test 'direnv preserva Conda e orienta desativação explícita antes da troca uv' {
    prepare_python_envs
    direnv allow "$TEST_PROJECT"
    mkdir -p "$HOME/conda/bin"
    run env CONDA_PREFIX="$HOME/conda" PATH="$HOME/conda/bin:$PATH" bash --noprofile --norc -ic '
        source "$XDG_CONFIG_HOME/devshell/bashrc"
        cd "$TEST_PROJECT"; _direnv_hook
        [[ $CONDA_PREFIX == "$HOME/conda" && -z ${VIRTUAL_ENV-} && :$PATH: == *":$HOME/conda/bin:"* ]]
    '
    [ "$status" -eq 0 ]
    [[ "$output" == *Conda* ]]
}

@test 'inspeção e dry-run preservam configuração, ambientes e cache já preparados' {
    prepare_python_envs
    run python3 - <<'PY'
import hashlib, json, os, stat, subprocess
from pathlib import Path

home = Path(os.environ['HOME'])
def snapshot():
    result = {}
    for path in home.rglob('*'):
        mode = stat.S_IMODE(path.lstat().st_mode)
        content = path.readlink().as_posix() if path.is_symlink() else hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        result[str(path.relative_to(home))] = (mode, content)
    return result

before = snapshot()
cli = str(Path(os.environ['FOUNDRY_ROOT']) / 'bin/devshell')
for args in (['plan'], ['diff'], ['status'], ['doctor'], ['apply', '--dry-run'], ['update', '--dry-run'], ['setup', '--dry-run']):
    result = subprocess.run([cli, *args, '--profile', 'personal', '--offline', '--json'], capture_output=True, text=True)
    assert result.returncode in ((0, 3) if args == ['doctor'] else (0,)), (args, result.stderr)
    json.loads(result.stdout)
    after = snapshot()
    assert after == before, (args, set(after) ^ set(before))
PY
    [ "$status" -eq 0 ]
}
