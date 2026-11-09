#!/usr/bin/env bats
# shellcheck disable=SC2030,SC2031 # run em helpers do Bats preenche status e output.
bats_require_minimum_version 1.5.0
# R-022: comportamento do uv de que o lock com hash depende, sem rede.
load core_setup
eval "core_$(declare -f setup)"

setup() {
    core_setup
    unset UV_VENV_CLEAR UV_VENV_SEED
    export UV_OFFLINE=1
    WHEELS="$BATS_TEST_TMPDIR/wheels"
    LOCK="$BATS_TEST_TMPDIR/lock.txt"
    build_wheels "$WHEELS"
}

# Dois wheels mínimos: dlprobe-a (com executável) depende de dlprobe-b.
build_wheels() {
    python3 - "$1" <<'PY'
import base64, hashlib, sys, zipfile
from pathlib import Path

root = Path(sys.argv[1]); root.mkdir(parents=True)

def wheel(name, body, requires=(), scripts=None):
    module = name.replace('-', '_')
    info = f'{module}-1.0.dist-info'
    metadata = ['Metadata-Version: 2.1', f'Name: {name}', 'Version: 1.0', *(f'Requires-Dist: {r}' for r in requires)]
    entries = {f'{module}/__init__.py': body, f'{info}/METADATA': '\n'.join(metadata) + '\n',
               f'{info}/WHEEL': 'Wheel-Version: 1.0\nGenerator: teste\nRoot-Is-Purelib: true\nTag: py3-none-any\n'}
    if scripts:
        entries[f'{info}/entry_points.txt'] = f'[console_scripts]\n{scripts}\n'
    record = []
    for path, text in entries.items():
        data = text.encode()
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        record.append(f'{path},sha256={digest},{len(data)}')
    record.append(f'{info}/RECORD,,')
    entries[f'{info}/RECORD'] = '\n'.join(record) + '\n'
    with zipfile.ZipFile(root / f'{module}-1.0-py3-none-any.whl', 'w') as archive:
        for path, text in entries.items():
            archive.writestr(path, text)

wheel('dlprobe-b', 'VALUE = 1\n')
wheel('dlprobe-a', 'def main():\n    print("dlprobe ok")\n', requires=['dlprobe-b==1.0'], scripts='dlprobe-a = dlprobe_a:main')
PY
}

wheel_hash() { sha256sum "$WHEELS/$1-1.0-py3-none-any.whl" | cut -d' ' -f1; }
bad_hash() { printf '0%.0s' {1..64}; }
write_lock() {
    printf 'dlprobe-a==1.0 --hash=sha256:%s\n' "$1" >"$LOCK"
    [[ -z "${2:-}" ]] || printf 'dlprobe-b==1.0 --hash=sha256:%s\n' "$2" >>"$LOCK"
}
make_venv() { uv --no-config --no-progress venv --no-python-downloads --python "$(command -v python3)" "$1"; }
lock_install() {
    uv --no-config --no-progress pip install --python "$1/bin/python" --require-hashes --no-build --link-mode copy \
        --no-index --find-links "$WHEELS" -r "$LOCK"
}

@test 'R-022 uv pip install --require-hashes recusa hash errado de dependência transitiva' {
    write_lock "$(wheel_hash dlprobe_a)" "$(bad_hash)"
    make_venv "$BATS_TEST_TMPDIR/venv" 2>/dev/null
    run --separate-stderr lock_install "$BATS_TEST_TMPDIR/venv"
    [ "$status" -ne 0 ]
    [[ "$stderr" == *'Hash mismatch'* ]]
    [ ! -e "$BATS_TEST_TMPDIR/venv/bin/dlprobe-a" ]
}

@test 'R-022 uv pip install --require-hashes recusa dependência ausente do lock' {
    write_lock "$(wheel_hash dlprobe_a)"
    make_venv "$BATS_TEST_TMPDIR/venv" 2>/dev/null
    run --separate-stderr lock_install "$BATS_TEST_TMPDIR/venv"
    [ "$status" -ne 0 ]
    [[ "$stderr" == *'no trusted hash'* ]]
    [ ! -e "$BATS_TEST_TMPDIR/venv/bin/dlprobe-a" ]
}

@test 'R-022 lock correto instala sem hardlink para o cache' {
    write_lock "$(wheel_hash dlprobe_a)" "$(wheel_hash dlprobe_b)"
    make_venv "$BATS_TEST_TMPDIR/venv" 2>/dev/null
    run --separate-stderr lock_install "$BATS_TEST_TMPDIR/venv"
    [ "$status" -eq 0 ]
    run "$BATS_TEST_TMPDIR/venv/bin/dlprobe-a"
    [ "$output" = 'dlprobe ok' ]
    [ -z "$(find "$BATS_TEST_TMPDIR/venv/lib" -type f -links +1 -print -quit)" ]
}

@test 'R-022 uv venv cria em diretório vazio e recusa diretório com conteúdo' {
    mkdir -m 700 "$BATS_TEST_TMPDIR/vazio" "$BATS_TEST_TMPDIR/ocupado"
    : >"$BATS_TEST_TMPDIR/ocupado/arquivo"
    run make_venv "$BATS_TEST_TMPDIR/vazio"
    [ "$status" -eq 0 ]
    [ -f "$BATS_TEST_TMPDIR/vazio/pyvenv.cfg" ]
    run make_venv "$BATS_TEST_TMPDIR/ocupado"
    [ "$status" -ne 0 ]
    [ "$(ls "$BATS_TEST_TMPDIR/ocupado")" = arquivo ]
}

@test 'R-022 registra se uv tool install passou a aplicar hashes de constraints' {
    write_lock "$(wheel_hash dlprobe_a)" "$(bad_hash)"
    run --separate-stderr uv --no-config tool install --no-index --find-links "$WHEELS" --no-build --no-python-downloads \
        --python "$(command -v python3)" --constraints "$LOCK" dlprobe-a==1.0
    if ((status != 0)); then
        printf '# uv tool install passou a recusar o hash errado: revise o ADR 004.\n' >&3
    fi
}
