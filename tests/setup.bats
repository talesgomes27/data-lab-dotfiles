#!/usr/bin/env bats
# shellcheck disable=SC2030,SC2031,SC2143 # run em helpers do Bats; no Bats, `! grep` não falha o teste, então a ausência é conferida pela saída vazia.
load core_setup

prepare_setup() {
    local original_python original_chezmoi utility
    export SETUP_ORIGINAL_PATH="$PATH"
    original_python=$(command -v python3)
    original_chezmoi=$(command -v chezmoi)
    export SETUP_BIN="$BATS_TEST_TMPDIR/bin" SETUP_LOG="$BATS_TEST_TMPDIR/actions.log"
    export SETUP_REAL_CHEZMOI="$original_chezmoi"
    export SETUP_REPO="$BATS_TEST_TMPDIR/repo"
    mkdir -p "$SETUP_BIN" "$SETUP_REPO"
    cp -a "$FOUNDRY_ROOT/bin" "$FOUNDRY_ROOT/lib" "$FOUNDRY_ROOT/manifests" "$FOUNDRY_ROOT/profiles" "$FOUNDRY_ROOT/dotfiles" "$FOUNDRY_ROOT/.chezmoiroot" "$SETUP_REPO/"
    for utility in bash dirname uname getconf grep cat; do ln -s "$(command -v "$utility")" "$SETUP_BIN/$utility"; done
    ln -s "$original_python" "$SETUP_BIN/python3"
    for utility in git zsh uv nu starship fzf zoxide direnv rg fdfind batcat eza delta shellcheck shfmt bats fc-cache btop ncdu tldr lazygit pyinit; do
        cat >"$SETUP_BIN/$utility" <<'BIN'
#!/usr/bin/env bash
case ${0##*/} in
    uv)
        if [[ ${1:-} == --version ]]; then printf 'uv 0.13.5\n'; else
            printf 'uv %s\n' "$*" >> "$SETUP_LOG"
            python3 - "$@" <<'PY'
import base64,hashlib,os,sys
from pathlib import Path
args=sys.argv[1:]
if 'python' in args and 'install' in args:
    version=args[-1]
    path=Path(os.environ['UV_PYTHON_INSTALL_DIR'])/f'cpython-{version}-fixture/bin/python3'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(f'#!/bin/sh\nprintf "Python {version}\\n"\n');path.chmod(0o755)
    header=path.parent.parent/'include'/('python'+'.'.join(version.split('.')[:2]))/'patchlevel.h'
    header.parent.mkdir(parents=True,exist_ok=True);header.write_text(f'#define PY_VERSION "{version}"\n')
if 'venv' in args or 'pip' in args:
    import json
    with open(os.environ['SETUP_LOG']+'.env','a') as stream:
        stream.write(json.dumps(sorted(k for k in os.environ if k.startswith('UV_') or k in ('VIRTUAL_ENV','CONDA_PREFIX')))+'\n')
if 'venv' in args:
    venv=Path(args[-1]);version=args[args.index('--python')+1];minor='.'.join(version.split('.')[:2])
    interpreter=Path(os.environ['UV_PYTHON_INSTALL_DIR'])/f'cpython-{version}-fixture/bin/python3'
    (venv/'bin').mkdir(parents=True,exist_ok=True);(venv/'bin/python').symlink_to(interpreter)
    (venv/'pyvenv.cfg').write_text(f'home = {interpreter.parent}\nversion_info = {version}\n')
    (venv/'lib'/f'python{minor}'/'site-packages').mkdir(parents=True,exist_ok=True)
elif 'pip' in args and 'install' in args:
    venv=Path(args[args.index('--python')+1]).parent.parent;lock=Path(args[args.index('-r')+1]);name=lock.stem
    if os.environ.get('SETUP_UV_PIP_FAIL') in ('1', name):
        sys.exit(1)
    site=next((venv/'lib').glob('python*/site-packages'))
    versions={}
    for line in lock.read_text().splitlines():
        if line and not line[0].isspace() and not line.startswith('#') and ';' not in line.split('\\')[0]:
            dist,version=line.split()[0].split('==');versions[dist]=version
    for dist,version in versions.items():
        info=site/f'{dist.replace("-","_")}-{version}.dist-info';info.mkdir(parents=True,exist_ok=True)
        (info/'METADATA').write_text(f'Name: {dist}\nVersion: {version}\n');(info/'METADATA').chmod(0o664)
    binary=venv/'bin'/name;binary.write_text(f'#!{venv}/bin/python\nprintf "{versions[name]}\\n"\n');binary.chmod(0o755)
    dist=site/f'{name.replace("-","_")}-{versions[name]}.dist-info'
    checksum=base64.urlsafe_b64encode(hashlib.sha256(binary.read_bytes()).digest()).decode().rstrip('=')
    records=[f'../../../bin/{name},sha256={checksum},{binary.stat().st_size}\n']
    required={'pre-commit':['pre_commit/__init__.py','pre_commit/main.py'], 'ipython':['IPython/__init__.py']}.get(name,[])
    for relative in required:
        module=site/relative;module.parent.mkdir(parents=True,exist_ok=True);module.write_text('# fixture\n')
        digest=base64.urlsafe_b64encode(hashlib.sha256(module.read_bytes()).digest()).decode().rstrip('=')
        records.append(f'{relative},sha256={digest},{module.stat().st_size}\n')
    (dist/'RECORD').write_text(''.join(records))
PY
        fi ;;
    nu) printf '0.116.1\n' ;;
    zsh) printf 'zsh 5.9\n' ;;
    fc-cache)
        printf 'fc-cache %s\n' "$*" >> "$SETUP_LOG"
        exit "${SETUP_FONT_CACHE_FAIL:-0}" ;;
esac
BIN
        chmod +x "$SETUP_BIN/$utility"
    done
    cat >"$SETUP_BIN/chezmoi" <<'BIN'
#!/usr/bin/env bash
exec "$SETUP_REAL_CHEZMOI" "$@"
BIN
    cat >"$SETUP_BIN/sudo" <<'BIN'
#!/usr/bin/env bash
printf 'sudo %s\n' "$*" >> "$SETUP_LOG"
[[ ${1:-} != -- ]] || shift
exec "$@"
BIN
    cat >"$SETUP_BIN/apt-get" <<'BIN'
#!/usr/bin/env bash
printf 'apt-get %s\n' "$*" >> "$SETUP_LOG"
if [[ ${SETUP_NATIVE_FAIL:-0} == 1 ]]; then exit 17; fi
printf '#!/usr/bin/env bash\nexit 0\n' > "$SETUP_BIN/starship"
chmod +x "$SETUP_BIN/starship"
BIN
    # chmod é chamado apenas pelo mock de pacote dentro de /tmp.
    ln -s "$(command -v chmod)" "$SETUP_BIN/chmod"
    chmod +x "$SETUP_BIN/chezmoi" "$SETUP_BIN/sudo" "$SETUP_BIN/apt-get"
    seed_artifact pyinit
    export PATH="$SETUP_BIN"
}

@test 'setup dry-run JSON agrega permissões e não altera modo ou arquivos' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/.local/bin" "$HOME/.config/nushell"
    /usr/bin/chmod 775 "$HOME/.local" "$HOME/.local/bin" "$HOME/.config/nushell"
    run "$SETUP_REPO/bin/devshell" setup --profile personal,science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys,os;p=json.load(sys.stdin);assert p["operation"]=="setup";paths={i["path"] for i in p["permissions"]};assert os.environ["HOME"]+"/.local" in paths;assert os.environ["HOME"]+"/.local/bin" in paths;assert os.environ["HOME"]+"/.config/nushell" in paths'
    [ "$(/usr/bin/stat -c %a "$HOME/.local")" = 775 ]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$XDG_STATE_HOME/devshell" ]
}

@test 'setup EOF recusa reparos sem mudar permissões' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/.local/bin"
    /usr/bin/chmod 775 "$HOME/.local" "$HOME/.local/bin"
    run "$SETUP_REPO/bin/devshell" setup --profile minimal </dev/null
    [ "$status" -ne 0 ]
    [ "$(/usr/bin/stat -c %a "$HOME/.local")" = 775 ]
    [ ! -e "$SETUP_LOG" ]
}

@test 'setup não aceita flags que dispensem as confirmações' {
    prepare_setup
    run "$SETUP_REPO/bin/devshell" setup --approve invalid
    [ "$status" -eq 2 ]
    run "$SETUP_REPO/bin/devshell" setup --json
    [ "$status" -eq 2 ]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup com ferramentas compatíveis aplica dotfiles sem reinstalar ou sudo' {
    prepare_setup
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    [ -f "$HOME/.zshenv" ]
    [ -f "$XDG_CONFIG_HOME/zsh/.zshrc" ]
    [ ! -e "$SETUP_LOG" ]
    first=$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")
    run "$SETUP_REPO/bin/devshell" setup --profile minimal </dev/null
    [ "$status" -eq 0 ]
    [ "$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")" = "$first" ]
}

@test 'setup exibe e exige confirmação separada antes de sudo' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "privilégios administrativos=n" -- "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 1 ]
    [[ "$output" == *'apt-get install -- starship'* ]]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'extras oferece somente pacotes mapeados e exige confirmação administrativa' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/btop" "$SETUP_BIN/ncdu" "$SETUP_BIN/tldr" "$SETUP_BIN/lazygit"
    run "$SETUP_REPO/bin/devshell" setup --profile extras --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["native_command"]==["apt-get","install","--","btop","lazygit","ncdu","tealdeer"]'
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "privilégios administrativos=n" -- "$SETUP_REPO/bin/devshell" setup --profile extras'
    [ "$status" -eq 1 ]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup offline não chama gerenciador de pacotes com respostas positivas' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship"
    # As respostas positivas só seriam lidas se, por regressão, o setup pedisse o sudo offline.
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" --allow-unused "privilégios administrativos=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile personal --offline'
    [ "$status" -eq 3 ]
    [[ "$output" == *offline* ]]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup interrompe após falha administrativa e não aplica dotfiles' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship"
    export SETUP_NATIVE_FAIL=1
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "privilégios administrativos=s" -- "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 17 ]
    [ -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup não sobrescreve conflito sem confirmação explícita' {
    prepare_setup
    printf 'minha configuração\n' >"$HOME/.zshenv"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Aplicar os dotfiles=s" "digite substituir=<EOF>" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 1 ]
    [ "$(/usr/bin/cat "$HOME/.zshenv")" = 'minha configuração' ]
    [ ! -e "$XDG_STATE_HOME/devshell/latest" ]
}

@test 'setup aceita conflito com confirmação e mantém backup para rollback' {
    prepare_setup
    printf 'minha configuração\n' >"$HOME/.zshenv"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Aplicar os dotfiles=s" "digite substituir=substituir" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    hash=$("$SETUP_REPO/bin/devshell" rollback --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$SETUP_REPO/bin/devshell" rollback --approve "$hash"
    [ "$(/usr/bin/cat "$HOME/.zshenv")" = 'minha configuração' ]
}

@test 'R-053 setup só remove órfãos depois da palavra retirar e não pergunta sobre registrar perfis' {
    prepare_setup
    hash=$("$SETUP_REPO/bin/devshell" plan --profile personal --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$SETUP_REPO/bin/devshell" apply --profile personal --approve "$hash" >/dev/null
    starship="$XDG_CONFIG_HOME/starship.toml"
    [ -f "$starship" ]
    latest=$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Aplicar os dotfiles=s" "digite retirar=<EOF>" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 1 ]
    [ -f "$starship" ]
    [ "$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")" = "$latest" ]
    [[ "$output" != *'Registrar os perfis'* ]]
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Aplicar os dotfiles=s" "digite retirar=retirar" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    [[ "$output" == *'a remover'* && "$output" == *"remove: $starship"* ]]
    [ ! -e "$starship" ]
    run "$SETUP_REPO/bin/devshell" doctor --profile minimal
    [[ "$output" != *'fora dos perfis'* ]]
}

@test 'R-053 plano só com órfãos pede retirar e nunca vira "Registrar os perfis"' {
    prepare_setup
    hash=$("$SETUP_REPO/bin/devshell" plan --profile minimal --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$SETUP_REPO/bin/devshell" apply --profile minimal --approve "$hash" >/dev/null
    # Alvo do universo registrado e no disco, sem nada a escrever: só a retirada.
    orphan="$XDG_CONFIG_HOME/starship.toml"
    /usr/bin/cp "$SETUP_REPO/dotfiles/dot_config/starship.toml" "$orphan"
    python3 -c 'import hashlib,json,sys;p,o=sys.argv[1:];d=json.load(open(p));d[o]=hashlib.sha256(open(o,"rb").read()).hexdigest();json.dump(d,open(p,"w"))' \
        "$XDG_STATE_HOME/devshell/current.json" "$orphan"
    "$SETUP_REPO/bin/devshell" plan --profile minimal --json | python3 -c 'import json,sys;d=json.load(sys.stdin);assert not [f for f in d["files"] if f["action"]=="write"] and [r["action"] for r in d["retire"]]==["remove"],d["retire"]'
    latest=$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Aplicar os dotfiles=s" "digite retirar=sim" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 1 ]
    [ -f "$orphan" ]
    [ "$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")" = "$latest" ]
    [[ "$output" != *'Registrar os perfis'* ]]
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Aplicar os dotfiles=s" "digite retirar=retirar" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    [[ "$output" != *'Registrar os perfis'* ]]
    [ ! -e "$orphan" ]
}

teardown() {
    export PATH="${SETUP_ORIGINAL_PATH:-$PATH}"
}

seed_artifact() {
    local component=$1
    python3 - "$component" <<'PY'
import hashlib,io,json,os,zipfile
from pathlib import Path
component=__import__('sys').argv[1]
repo=Path(os.environ['SETUP_REPO'])
cache=Path(os.environ['XDG_CACHE_HOME'])/'devshell/artifacts'
cache.mkdir(parents=True,exist_ok=True)
records=[]
if component=='firacode':
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('FiraCodeNerdFontMono-Regular.ttf',b'font fixture')
        archive.writestr('LICENSE',b'license fixture')
    payloads=[(component,'',stream.getvalue())]
elif component=='plugins':
    payloads=[('autosuggestions','zsh-autosuggestions.zsh',b'# fixture de plugin\n'),('highlighting','zsh-syntax-highlighting.zsh',b'# fixture de plugin\n'),('highlighting','highlighters/main/main-highlighter.zsh',b'# fixture highlighter\n')]
else:
    payloads=[(component,component,Path(os.environ['SETUP_BIN'],component).read_bytes())]
for name,binary,content in payloads:
    checksum=hashlib.sha256(content).hexdigest()
    (cache/checksum).write_bytes(content)
    record={'component':component,'name':name,'binary':binary,'format':'zip' if component=='firacode' else 'raw','arch':'any','libc':'any','version':'fixture','sha256':checksum,'url':'https://github.com/example/fixture'}
    if component=='plugins': record['health']={binary:hashlib.sha256(content).hexdigest()}
    if component=='firacode': record['health']={n:hashlib.sha256(b).hexdigest() for n,b in [('FiraCodeNerdFontMono-Regular.ttf',b'font fixture'),('LICENSE',b'license fixture')]}
    records.append(record)
path=repo/'manifests/artifacts.json'
manifest=json.loads(path.read_text())
manifest['artifacts']=[a for a in manifest['artifacts'] if a['component']!=component]+records
path.write_text(json.dumps(manifest))
PY
}

@test 'setup repara somente modos aprovados e prossegue até aplicar' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/.local/bin"
    /usr/bin/chmod 775 "$HOME/.local" "$HOME/.local/bin"
    /usr/bin/mkdir "$HOME/.local/unrelated"
    /usr/bin/chmod 777 "$HOME/.local/unrelated"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Retirar escrita=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    [ "$(/usr/bin/stat -c %a "$HOME/.local")" = 755 ]
    [ "$(/usr/bin/stat -c %a "$HOME/.local/bin")" = 755 ]
    [ "$(/usr/bin/stat -c %a "$HOME/.local/unrelated")" = 777 ]
    [ -f "$HOME/.zshenv" ]
}

@test 'setup instala componente ausente do cache com o hash interno' {
    prepare_setup
    seed_artifact chezmoi
    /usr/bin/rm "$SETUP_BIN/chezmoi"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente chezmoi conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile minimal --offline'
    [ "$status" -eq 0 ]
    [ -x "$HOME/.local/bin/chezmoi" ]
    [ -f "$HOME/.zshenv" ]
    [ ! -e "$SETUP_LOG" ]
}

@test 'atualização manual preserva versão anterior e permite restaurar backup' {
    prepare_setup
    seed_artifact chezmoi
    /usr/bin/mkdir -p "$HOME/.local/bin" "$HOME/backup"
    printf '#!/bin/sh\nprintf antigo\n' >"$HOME/.local/bin/chezmoi"
    /usr/bin/chmod 700 "$HOME/.local/bin/chezmoi"
    hash=$("$SETUP_REPO/bin/devshell" install --component chezmoi --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run "$SETUP_REPO/bin/devshell" install --component chezmoi --approve "$hash" --offline
    [ "$status" -eq 2 ]
    /usr/bin/mv "$HOME/.local/bin/chezmoi" "$HOME/backup/chezmoi-antigo"
    run "$SETUP_REPO/bin/devshell" install --component chezmoi --approve "$hash" --offline
    [ "$status" -eq 0 ]
    /usr/bin/mv "$HOME/.local/bin/chezmoi" "$HOME/backup/chezmoi-novo"
    /usr/bin/mv "$HOME/backup/chezmoi-antigo" "$HOME/.local/bin/chezmoi"
    [ "$(/usr/bin/stat -c %a "$HOME/.local/bin/chezmoi")" = 700 ]
    [[ "$(/usr/bin/cat "$HOME/.local/bin/chezmoi")" == *antigo* ]]
}

@test 'setup personal instala pacote aprovado e verifica plugins sem rede' {
    prepare_setup
    seed_artifact plugins
    seed_artifact firacode
    /usr/bin/rm "$SETUP_BIN/starship"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "privilégios administrativos=s" "componente plugins conforme=s" "componente firacode conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 0 ]
    [ -x "$SETUP_BIN/starship" ]
    [ -f "$XDG_DATA_HOME/devshell/plugins/autosuggestions/zsh-autosuggestions.zsh" ]
    [ -f "$XDG_CONFIG_HOME/nushell/config.nu" ]
    [ "$(/usr/bin/stat -c %a "$XDG_DATA_HOME/fonts/FiraCodeNerdFont/FiraCodeNerdFontMono-Regular.ttf")" = 644 ]
    /usr/bin/grep -q '^fc-cache -f ' "$SETUP_LOG"
    /usr/bin/grep -q '^sudo -- apt-get install -- starship$' "$SETUP_LOG"
}

@test 'fonte repete cache após falha sem regravar arquivos e recusa conflito' {
    prepare_setup
    seed_artifact firacode
    hash=$("$SETUP_REPO/bin/devshell" install --component firacode --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    export SETUP_FONT_CACHE_FAIL=7
    run "$SETUP_REPO/bin/devshell" install --component firacode --approve "$hash" --offline
    [ "$status" -eq 2 ]
    export SETUP_FONT_CACHE_FAIL=0
    run "$SETUP_REPO/bin/devshell" install --component firacode --approve "$hash" --offline --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert json.load(sys.stdin)["changed"]==0'
    [ "$(/usr/bin/grep -c '^fc-cache ' "$SETUP_LOG")" = 2 ]
    printf 'preservar\n' >"$XDG_DATA_HOME/fonts/FiraCodeNerdFont/FiraCodeNerdFontMono-Regular.ttf"
    run "$SETUP_REPO/bin/devshell" install --component firacode --approve "$hash" --offline
    [ "$status" -eq 2 ]
    [[ "$output" == *preexistente* ]]
    [ "$(/usr/bin/cat "$XDG_DATA_HOME/fonts/FiraCodeNerdFont/FiraCodeNerdFontMono-Regular.ttf")" = preservar ]
}

@test 'setup science exige confirmação própria antes de instalar pyinit' {
    prepare_setup
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "componente pyinit conforme=n" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 1 ]
    [[ "$output" == *'componente pyinit conforme este plano?'* ]]
    [ ! -e "$HOME/.local/bin/pyinit" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup science reutiliza uv compatível e instala Python isolado e pyinit' {
    prepare_setup
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "componente pyinit conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [ -x "$HOME/.local/bin/pyinit" ]
    python3 - <<'PY'
import os
calls=open(os.environ['SETUP_LOG']).read().splitlines()
assert len(calls)==8,calls
assert sum(' python install --no-bin ' in line for line in calls)==2
assert sum(' venv --managed-python --no-python-downloads ' in line for line in calls)==3
tools=os.environ['XDG_DATA_HOME']+'/devshell/tools/'
pip=[line for line in calls if ' pip install ' in line]
assert len(pip)==3 and all(f'--python {tools}' in line and ' --require-hashes --no-build --link-mode copy -r ' in line for line in pip),pip
assert not any(' tool ' in line for line in calls),calls
assert all('--offline' in line and '--force' not in line for line in calls)
PY
}

@test 'science informa DuckDB opcional ausente sem bloquear outras instalações' {
    prepare_setup
    run "$SETUP_REPO/bin/devshell" setup --profile science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert "duckdb" in p["components"];assert "duckdb" in p["dependencies"]["optional_missing"];assert not p["blockers"]'
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "componente pyinit conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [[ "$output" == *'DuckDB opcional ausente'* ]]
}

@test 'doctor alerta DuckDB obtido de diretório de PATH inseguro' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/shared"
    /usr/bin/chmod 777 "$HOME/shared"
    /usr/bin/ln -s /usr/bin/true "$HOME/shared/duckdb"
    PATH="$HOME/shared:$PATH" run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("DuckDB detectado em caminho inseguro" in w for w in json.load(sys.stdin)["warnings"])'
}

install_science() {
    prepare_setup
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "componente pyinit conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    TOOLS="$XDG_DATA_HOME/devshell/tools"
}
doctor_issue() {
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;i=json.load(sys.stdin)["issues"];assert any(all(p in s for p in sys.argv[1:]) for s in i),i' "$@"
}

@test 'R-043 setup oferece e aplica a correção dos modos das venvs do Data Lab' {
    install_science
    /usr/bin/chmod g+w "$TOOLS"/ipython/lib/python3.13/site-packages/*.dist-info/METADATA "$TOOLS/ipython/lib/python3.13/site-packages"
    /usr/bin/mkdir -p "$HOME/fora"
    printf 'x\n' >"$HOME/fora/arquivo"
    /usr/bin/chmod 664 "$HOME/fora/arquivo"
    run bash -c '"$SETUP_REPO/bin/devshell" setup --profile science --dry-run --json 2>/dev/null'
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c '
import json,sys
p=json.load(sys.stdin);items=[i for i in p["permissions"] if i["kind"]=="venv-mode"]
assert items and all(i["repairable"] for i in items),p["permissions"]
assert all("/devshell/tools/ipython/" in i["path"] for i in items),items
assert not p["blockers"],p["blockers"]'
    run bash -c '"$SETUP_REPO/bin/devshell" setup --profile science --dry-run'
    [[ "$output" == *'venv ipython:'* ]]
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Retirar escrita=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [ -z "$(/usr/bin/find "$TOOLS" -perm /022 ! -type l -print -quit)" ]
    [ "$(/usr/bin/stat -c %a "$HOME/fora/arquivo")" = 664 ]
    [ -L "$TOOLS/ipython/bin/python" ]
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    printf '%s' "$output" | python3 -c 'import json,sys;i=[s for s in json.load(sys.stdin)["issues"] if "ferramenta" in s];assert not i,i'
}

@test 'R-043 doctor tem mensagem própria para modos inseguros na venv' {
    install_science
    /usr/bin/chmod g+w "$TOOLS"/ruff/lib/python3.13/site-packages/ruff-*.dist-info/METADATA
    doctor_issue ruff 'modos inseguros na venv' 'setup'
}

@test 'R-043 venv com milhares de arquivos é revista agrupada e em tempo curto' {
    install_science
    python3 - "$TOOLS/ipython/lib/python3.13/site-packages" <<'MANY'
import os,sys
from pathlib import Path
root=Path(sys.argv[1])/'muitos'
root.mkdir()
for index in range(2000):
    path=root/f'm{index}.py';path.write_text('#\n');path.chmod(0o664)
MANY
    start=$SECONDS
    run bash -c '"$SETUP_REPO/bin/devshell" setup --profile science --dry-run'
    [ "$status" -eq 0 ]
    [ $((SECONDS - start)) -lt 20 ]
    [[ "$output" == *'venv ipython: 2000 '* ]]
    [ "$(printf '%s\n' "$output" | /usr/bin/grep -c 'muitos/m')" -le 3 ]
}

@test 'R-041 resumo é a primeira saída e diz que cada etapa pede a sua confirmação' {
    prepare_setup
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=n" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 1 ]
    printf '%s' "$output" | python3 -c '
import sys
text=sys.stdin.read()
summary=text.index("Resumo do setup")
assert summary < text.index("[s/N]"),text
block=text[summary:text.index("[s/N]")]
assert "cada etapa pede a própria confirmação" in block,block
assert "componente python: instalar ou atualizar" in block and "componente pyinit: instalar ou atualizar" in block,block
assert "dotfiles:" in block and "a atualizar" in block,block'
}

@test 'R-040 setup pergunta antes de registrar os perfis quando os dotfiles já estão em dia' {
    install_science
    /usr/bin/rm "$XDG_STATE_HOME/devshell/profiles"
    latest=$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Registrar os perfis science=n" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [[ "$output" == *'Perfis não registrados'* ]]
    [ ! -e "$XDG_STATE_HOME/devshell/profiles" ]
    [ "$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")" = "$latest" ]
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Registrar os perfis science=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [ "$(/usr/bin/cat "$XDG_STATE_HOME/devshell/profiles")" = science ]
    # R-048: registrar os perfis abre uma transação sem arquivos (o rollback dela é testado em RememberedProfiles).
    new=$(/usr/bin/cat "$XDG_STATE_HOME/devshell/latest")
    [ "$new" != "$latest" ]
    python3 -c 'import json,sys;m=json.load(open(sys.argv[1]));assert m["files"]==[] and m["status"]=="committed" and m["previous_profiles"] is None,m' \
        "$XDG_STATE_HOME/devshell/transactions/$new/manifest.json"
}

@test 'R-041 com tudo em dia o setup diz nada a fazer, sai com 0 e não pergunta' {
    install_science
    run "$SETUP_REPO/bin/devshell" setup --offline </dev/null
    [ "$status" -eq 0 ]
    [[ "$output" == *'Nada a fazer: tudo em dia.'* ]]
    [[ "$output" != *'[s/N]'* ]]
    run bash -c '"$SETUP_REPO/bin/devshell" setup --dry-run --json 2>/dev/null'
    printf '%s' "$output" | python3 -c 'import json,sys;s=json.load(sys.stdin)["summary"];assert s["nothing_to_do"] is True,s;assert all(step["status"]=="em dia" for step in s["steps"]),s'
}

@test 'R-042 atualização do projeto só pergunta pelo que mudou' {
    install_science
    printf '# versão nova\n' >>"$SETUP_REPO/dotfiles/dot_config/devshell/env.sh"
    /usr/bin/rm "$UV_TOOL_BIN_DIR/ruff"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --offline'
    [ "$status" -eq 0 ]
    [[ "$output" == *'componente pyinit: em dia'* ]]
    [ "$(/usr/bin/readlink "$UV_TOOL_BIN_DIR/ruff")" = "$TOOLS/ruff/bin/ruff" ]
    [ "$(/usr/bin/tail -n 1 "$XDG_CONFIG_HOME/devshell/env.sh")" = '# versão nova' ]
}

@test 'R-041 com reparo pendente as etapas dependentes são reavaliadas depois' {
    install_science
    /usr/bin/chmod 775 "$HOME/.local"
    run bash -c '"$SETUP_REPO/bin/devshell" setup --dry-run --json 2>/dev/null'
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c '
import json,sys
s=json.load(sys.stdin)["summary"];steps={x["step"]:x for x in s["steps"]}
assert steps["permissões"]["status"]=="corrigir",steps
assert steps["componente python"]["status"]=="reavaliado depois do reparo de permissões",steps
assert s["nothing_to_do"] is False'
}

@test 'R-044 doctor termina com o próximo passo e o JSON traz next_step' {
    prepare_setup
    run "$SETUP_REPO/bin/devshell" doctor --profile science --offline
    [ "$status" -eq 3 ]
    [[ "$(printf '%s\n' "$output" | /usr/bin/tail -n 1)" == 'Próximo passo: ./bin/devshell setup --profile science'* ]]
    run bash -c '"$SETUP_REPO/bin/devshell" doctor --profile science --json 2>/dev/null'
    printf '%s' "$output" | python3 -c 'import json,sys;s=json.load(sys.stdin)["next_step"];assert s["kind"]=="setup" and s["command"][-2:]==["--profile","science"],s'
}

@test 'R-044 depois de um setup sem nada a fazer o doctor não sugere setup' {
    install_science
    run "$SETUP_REPO/bin/devshell" setup --offline </dev/null
    [[ "$output" == *'Nada a fazer: tudo em dia.'* ]]
    run bash -c '"$SETUP_REPO/bin/devshell" doctor --json 2>/dev/null'
    printf '%s' "$output" | python3 -c 'import json,sys;d=json.load(sys.stdin);s=d["next_step"];assert s is None or s["kind"]!="setup",(s,d["issues"])'
}

@test 'R-023 doctor relata link ausente e versão divergente do lock' {
    install_science
    /usr/bin/rm "$UV_TOOL_BIN_DIR/ruff"
    doctor_issue 'sem-link' ruff
    /usr/bin/ln -s "$TOOLS/ruff/bin/ruff" "$UV_TOOL_BIN_DIR/ruff"
    /usr/bin/sed -i 's/^Version: .*/Version: 0.1.0/' "$TOOLS"/ruff/lib/python3.13/site-packages/ruff-*.dist-info/METADATA
    doctor_issue divergente 'ruff 0.1.0, lock 0.17.3'
}

@test 'R-023 doctor relata distribuição fora do lock e dependência do lock ausente' {
    install_science
    site=$(printf '%s\n' "$TOOLS"/pre-commit/lib/python3.13/site-packages)
    /usr/bin/mkdir "$site/estranho-1.0.dist-info"
    printf 'Name: estranho\nVersion: 1.0\n' >"$site/estranho-1.0.dist-info/METADATA"
    doctor_issue pre-commit 'estranho 1.0 fora do lock'
    /usr/bin/rm -r "$site/estranho-1.0.dist-info" "$site"/pyyaml-*.dist-info
    doctor_issue pre-commit 'pyyaml' 'não instalado'
}

@test 'R-023 doctor relata interpretador da venv diferente de tool_python' {
    install_science
    /usr/bin/sed -i 's/^version_info = .*/version_info = 3.12.12/' "$TOOLS/ruff/pyvenv.cfg"
    doctor_issue ruff 'Python da venv 3.12.12'
}

@test 'R-023 doctor recusa interpretador fora do CPython gerenciado' {
    install_science
    /usr/bin/rm "$TOOLS/ruff/bin/python"
    /usr/bin/ln -s "$(command -v python3)" "$TOOLS/ruff/bin/python"
    doctor_issue ruff 'fora do CPython gerenciado'
}

@test 'R-023 doctor não executa ferramenta alterada e aponta divergência do RECORD' {
    install_science
    printf '#!/bin/sh\ntouch "%s"\nprintf "0.17.3\\n"\n' "$HOME/doctor-executou" >"$TOOLS/ruff/bin/ruff"
    doctor_issue ruff 'executável diverge do RECORD'
    [ ! -e "$HOME/doctor-executou" ]
}

@test 'R-023 doctor detecta interpretador ausente no launcher mesmo com RECORD válido' {
    install_science
    printf '#!/caminho/inexistente/python\n' >"$TOOLS/ruff/bin/ruff"
    python3 - <<'RECORD'
import base64,hashlib,os
from pathlib import Path
root=Path(os.environ['XDG_DATA_HOME'])/'devshell/tools/ruff'
binary=root/'bin/ruff'
record=next((root/'lib').glob('python*/site-packages/ruff-*.dist-info/RECORD'))
checksum=base64.urlsafe_b64encode(hashlib.sha256(binary.read_bytes()).digest()).decode().rstrip('=')
record.write_text(f'../../../bin/ruff,sha256={checksum},{binary.stat().st_size}\n')
RECORD
    doctor_issue ruff 'interpretador do launcher'
}

@test 'R-023 doctor detecta módulo essencial ausente na venv' {
    install_science
    /usr/bin/rm "$TOOLS/pre-commit/lib/python3.13/site-packages/pre_commit/main.py"
    doctor_issue pre-commit 'módulo essencial'
}

pending_of() {
    "$SETUP_REPO/bin/devshell" install --component "$1" --profile "$2" --offline --json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["pending"])'
}

@test 'R-042 pending do pyinit, plugins e fonte acompanha o que está instalado' {
    prepare_setup
    seed_artifact plugins
    seed_artifact firacode
    [ "$(pending_of pyinit science)" = True ]
    [ "$(pending_of plugins personal)" = True ]
    [ "$(pending_of firacode personal)" = True ]
    for spec in 'pyinit science' 'plugins personal' 'firacode personal'; do
        read -r component profile <<<"$spec"
        hash=$("$SETUP_REPO/bin/devshell" install --component "$component" --profile "$profile" --offline --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
        "$SETUP_REPO/bin/devshell" install --component "$component" --profile "$profile" --offline --approve "$hash" >/dev/null
        [ "$(pending_of "$component" "$profile")" = False ]
    done
    /usr/bin/chmod a-x "$HOME/.local/bin/pyinit"
    [ "$(pending_of pyinit science)" = True ]
    printf 'modificado' >"$XDG_DATA_HOME/devshell/plugins/autosuggestions/zsh-autosuggestions.zsh"
    [ "$(pending_of plugins personal)" = True ]
}

@test 'R-042 pending do Python fica falso com interpretadores e ferramentas conformes' {
    prepare_setup
    [ "$(pending_of python science)" = True ]
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "componente pyinit conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [ "$(pending_of python science)" = False ]
    /usr/bin/rm "$UV_TOOL_BIN_DIR/ruff"
    [ "$(pending_of python science)" = True ]
}

@test 'R-042 pending fica fora do hash de aprovação' {
    prepare_setup
    before=$("$SETUP_REPO/bin/devshell" install --component pyinit --profile science --offline --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$SETUP_REPO/bin/devshell" install --component pyinit --profile science --offline --approve "$before" >/dev/null
    [ "$(pending_of pyinit science)" = False ]
    after=$("$SETUP_REPO/bin/devshell" install --component pyinit --profile science --offline --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    [ "$before" = "$after" ]
}
@test 'R-025 setup science repara permissão de grupo antes de avaliar as ferramentas' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/.local/bin"
    /usr/bin/chmod 775 "$HOME/.local" "$HOME/.local/bin"
    run "$SETUP_REPO/bin/devshell" setup --profile science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["permissions"] and all(i["repairable"] for i in p["permissions"]),p["permissions"];assert not p["blockers"],p["blockers"]'
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Retirar escrita=s" "componente python conforme=s" "componente pyinit conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [ "$(/usr/bin/stat -c %a "$HOME/.local")" = 755 ]
    [ "$(/usr/bin/readlink "$UV_TOOL_BIN_DIR/ruff")" = "$XDG_DATA_HOME/devshell/tools/ruff/bin/ruff" ]
}

@test 'R-025 dry-run mostra conflito do uv tool mesmo com reparo de permissão pendente' {
    prepare_setup
    /usr/bin/mkdir -p "$UV_TOOL_DIR/ruff/bin" "$UV_TOOL_BIN_DIR"
    printf '#!/bin/sh\n' >"$UV_TOOL_DIR/ruff/bin/ruff"
    /usr/bin/ln -s "$UV_TOOL_DIR/ruff/bin/ruff" "$UV_TOOL_BIN_DIR/ruff"
    /usr/bin/chmod 775 "$HOME/.local"
    run "$SETUP_REPO/bin/devshell" setup --profile science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["permissions"],p;assert any("uv tool uninstall ruff" in b for b in p["blockers"]),p["blockers"]'
    [ "$(/usr/bin/stat -c %a "$HOME/.local")" = 775 ]
}

@test 'R-023 doctor aponta link da ferramenta para fora da venv' {
    install_science
    /usr/bin/ln -sfn /usr/bin/true "$UV_TOOL_BIN_DIR/ruff"
    doctor_issue conflito ruff 'uv tool uninstall ruff'
}

@test 'R-022 falha na terceira ferramenta lista as concluídas e mantém as anteriores' {
    prepare_setup
    hash=$("$SETUP_REPO/bin/devshell" install --component python --profile science --offline --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    SETUP_UV_PIP_FAIL=ipython run "$SETUP_REPO/bin/devshell" install --component python --profile science --offline --approve "$hash"
    [ "$status" -eq 2 ]
    [[ "$output" == *'concluídas: ruff, pre-commit'* ]]
    [ ! -e "$XDG_DATA_HOME/devshell/tools/ipython" ]
    [ -L "$UV_TOOL_BIN_DIR/ruff" ]
    [ -L "$UV_TOOL_BIN_DIR/pre-commit" ]
}

@test 'R-021 install aprovado com --json emite um único documento' {
    prepare_setup
    hash=$("$SETUP_REPO/bin/devshell" install --component python --profile science --offline --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    run bash -c '"$SETUP_REPO/bin/devshell" install --component python --profile science --offline --approve "$1" --json 2>/dev/null' _ "$hash"
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;json.load(sys.stdin)'
    run "$UV_TOOL_BIN_DIR/ruff"
    [ "$status" -eq 0 ]
}

@test 'R-025 instalação do uv tool bloqueia setup e install sem alterar nada' {
    prepare_setup
    /usr/bin/mkdir -p "$UV_TOOL_DIR/ruff/bin" "$UV_TOOL_DIR/outra/bin" "$UV_TOOL_BIN_DIR"
    printf '#!/bin/sh\n' >"$UV_TOOL_DIR/ruff/bin/ruff"
    printf '#!/bin/sh\n' >"$UV_TOOL_DIR/outra/bin/outra"
    /usr/bin/ln -s "$UV_TOOL_DIR/ruff/bin/ruff" "$UV_TOOL_BIN_DIR/ruff"
    /usr/bin/ln -s "$UV_TOOL_DIR/outra/bin/outra" "$UV_TOOL_BIN_DIR/outra"
    /usr/bin/rm "$SETUP_BIN/shellcheck"
    before=$(/usr/bin/find "$HOME" -printf '%p %l\n' | /usr/bin/sort)
    run "$SETUP_REPO/bin/devshell" setup --profile science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert p["native_command"],p;b=p["blockers"];assert any("conflito: ruff" in x and "uv tool uninstall ruff" in x for x in b),b'
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 3 ]
    [ -z "$(/usr/bin/grep -s '^sudo ' "$SETUP_LOG")" ]
    run "$SETUP_REPO/bin/devshell" install --component python --profile science --json
    [ "$status" -eq 2 ]
    [[ "$output" == *'uv tool uninstall ruff'* ]]
    [ "$(/usr/bin/find "$HOME" -printf '%p %l\n' | /usr/bin/sort)" = "$before" ]
}

@test 'R-021 instalação preserva venv ativa de outro projeto e não chama uv tool' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/projeto/.venv/bin"
    printf 'marcador\n' >"$HOME/projeto/.venv/marcador"
    before=$(/usr/bin/find "$HOME/projeto" -printf '%p %s\n' | /usr/bin/sort)
    /usr/bin/mkdir -p "$UV_TOOL_DIR/outra/bin" "$UV_TOOL_BIN_DIR"
    printf '#!/bin/sh\n' >"$UV_TOOL_DIR/outra/bin/outra"
    /usr/bin/ln -s "$UV_TOOL_DIR/outra/bin/outra" "$UV_TOOL_BIN_DIR/outra"
    VIRTUAL_ENV="$HOME/projeto/.venv" CONDA_PREFIX="$HOME/conda" UV_VENV_CLEAR=1 UV_INDEX_URL=https://exemplo.invalid \
        run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "componente pyinit conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [ "$(/usr/bin/find "$HOME/projeto" -printf '%p %s\n' | /usr/bin/sort)" = "$before" ]
    [ "$(/usr/bin/readlink "$UV_TOOL_BIN_DIR/outra")" = "$UV_TOOL_DIR/outra/bin/outra" ]
    python3 -c 'import json,sys;rows=[json.loads(l) for l in open(sys.argv[1])];assert len(rows)==6,rows;assert all(set(r)=={"UV_CACHE_DIR","UV_PYTHON_INSTALL_DIR"} for r in rows),rows' "$SETUP_LOG.env"
    [ -z "$(/usr/bin/grep "$HOME/projeto" "$SETUP_LOG")" ]
    [ -z "$(/usr/bin/grep -E '^uv .* tool ' "$SETUP_LOG")" ]
    [ "$(/usr/bin/readlink "$UV_TOOL_BIN_DIR/ruff")" = "$XDG_DATA_HOME/devshell/tools/ruff/bin/ruff" ]
}

@test 'R-021 instalação tira escrita de grupo dos arquivos copiados do cache do uv' {
    install_science
    [ -z "$(/usr/bin/find "$TOOLS" -perm /022 ! -type l -print -quit)" ]
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    printf '%s' "$output" | python3 -c 'import json,sys;i=[s for s in json.load(sys.stdin)["issues"] if "ferramenta" in s];assert not i,i'
}

@test 'R-021 repetir a instalação conforme não chama o uv para as ferramentas' {
    install_science
    hash=$("$SETUP_REPO/bin/devshell" install --component python --profile science --offline --json | python3 -c 'import json,sys;p=json.load(sys.stdin);assert {t["state"] for t in p["tools"]}=={"conforme"},p["tools"];print(p["approval"])')
    calls=$(/usr/bin/wc -l <"$SETUP_LOG")
    run "$SETUP_REPO/bin/devshell" install --component python --profile science --offline --approve "$hash"
    [ "$status" -eq 0 ]
    [ -z "$(/usr/bin/tail -n "+$((calls + 1))" "$SETUP_LOG" | /usr/bin/grep -E ' (venv|pip) ')" ]
    run "$SETUP_REPO/bin/devshell" setup --profile science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert not p["blockers"] and not p["permissions"],p'
}

@test 'R-022 falha do uv pip install remove só a venv criada e sai com 2' {
    prepare_setup
    hash=$("$SETUP_REPO/bin/devshell" install --component python --profile science --offline --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    SETUP_UV_PIP_FAIL=1 run "$SETUP_REPO/bin/devshell" install --component python --profile science --offline --approve "$hash"
    [ "$status" -eq 2 ]
    [[ "$output" == *'venv foi removida'* && "$output" == *'concluídas: nenhuma'* ]]
    [ -z "$(/usr/bin/find "$XDG_DATA_HOME/devshell/tools" -mindepth 1 -print -quit)" ]
    [ ! -e "$UV_TOOL_BIN_DIR/ruff" ]
    [ ! -L "$UV_TOOL_BIN_DIR/ruff" ]
}

@test 'doctor identifica metadado de versão incorreto no interpretador uv' {
    prepare_setup
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente python conforme=s" "componente pyinit conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    printf '#define PY_VERSION "3.1.0"\n' >"$UV_PYTHON_INSTALL_DIR/cpython-3.12.12-fixture/include/python3.12/patchlevel.h"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("interpretador uv divergente: 3.12.12" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'doctor detecta alteração dos arquivos essenciais de plugin e fonte' {
    prepare_setup
    seed_artifact plugins
    seed_artifact firacode
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente plugins conforme=s" "componente firacode conforme=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile personal --offline'
    [ "$status" -eq 0 ]
    printf 'modificado' >"$XDG_DATA_HOME/devshell/plugins/autosuggestions/zsh-autosuggestions.zsh"
    printf 'modificado' >"$XDG_DATA_HOME/fonts/FiraCodeNerdFont/FiraCodeNerdFontMono-Regular.ttf"
    printf 'modificado' >"$XDG_DATA_HOME/devshell/plugins/highlighting/highlighters/main/main-highlighter.zsh"
    run "$SETUP_REPO/bin/devshell" doctor --profile personal --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;s=" ".join(json.load(sys.stdin)["issues"]);assert "integridade" in s and "autosuggestions" in s and "main-highlighter" in s and "FiraCode" in s,s'
}

@test 'setup sem sudo diagnostica pacotes ausentes sem pedir outros ajustes' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/sudo" "$SETUP_BIN/starship"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" -- "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 3 ]
    [[ "$output" == *'sudo ausente'* ]]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup recusa versão incompatível em vez de substituir executável' {
    prepare_setup
    printf '#!/usr/bin/env bash\nprintf "uv 0.1.0\\n"\n' >"$SETUP_BIN/uv"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" -- "$SETUP_REPO/bin/devshell" setup --profile science'
    [ "$status" -eq 3 ]
    [[ "$output" == *'uv incompatível'* ]]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup mantém a aprovação original quando arquivo muda durante confirmação' {
    prepare_setup
    run python3 - <<'PY'
import os,select,subprocess,time
from pathlib import Path
process=subprocess.Popen([os.environ['SETUP_REPO']+'/bin/devshell','setup','--profile','minimal'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
output=b''
deadline=time.monotonic()+10
try:
    while b'Aplicar os dotfiles apresentados' not in output:
        assert time.monotonic()<deadline,output.decode()
        if not select.select([process.stdout],[],[],1)[0]:continue
        chunk=os.read(process.stdout.fileno(),4096)
        assert chunk,output.decode()
        output+=chunk
    Path(os.environ['HOME'],'.zshenv').write_text('alterado durante confirmação\n')
    tail,_=process.communicate(b's\n',timeout=10)
    output+=tail
    assert process.returncode==2,output.decode()
    assert Path(os.environ['HOME'],'.zshenv').read_text()=='alterado durante confirmação\n'
    assert not Path(os.environ['XDG_STATE_HOME'],'devshell/latest').exists()
finally:
    if process.poll() is None:process.kill();process.wait()
PY
    [ "$status" -eq 0 ]
}

@test 'setup não aceita --component mesmo com o valor default' {
    prepare_setup
    run "$SETUP_REPO/bin/devshell" setup --component uv </dev/null
    [ "$status" -eq 2 ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup não tenta uma instalação parcial quando há pacote sem mapeamento' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship" "$SETUP_BIN/zsh"
    printf 'ID=fedora\n' >"$BATS_TEST_TMPDIR/fedora"
    DEVSHELL_OS_RELEASE="$BATS_TEST_TMPDIR/fedora" run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" -- "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 3 ]
    [[ "$output" == *'sem pacote/adaptador definido: starship'* ]]
    [ ! -e "$SETUP_LOG" ]
}

@test 'setup preserva verificação de checksum do instalador existente' {
    prepare_setup
    seed_artifact chezmoi
    /usr/bin/rm "$SETUP_BIN/chezmoi"
    python3 - <<'PY'
import json,os
from pathlib import Path
manifest=json.loads(Path(os.environ['SETUP_REPO'],'manifests/artifacts.json').read_text())
artifact=next(a for a in manifest['artifacts'] if a['component']=='chezmoi')
Path(os.environ['XDG_CACHE_HOME'],'devshell/artifacts',artifact['sha256']).write_bytes(b'corrompido')
PY
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "componente chezmoi conforme=s" -- "$SETUP_REPO/bin/devshell" setup --profile minimal --offline'
    [ "$status" -eq 2 ]
    [[ "$output" == *'cache corrompido:'* && "$output" == *'/devshell/artifacts/'* ]]
    [ ! -e "$HOME/.local/bin/chezmoi" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup sem adaptador não tenta pacote ou download com confirmação positiva' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship"
    printf 'ID=unknown\n' >"$BATS_TEST_TMPDIR/unknown"
    DEVSHELL_OS_RELEASE="$BATS_TEST_TMPDIR/unknown" run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" -- "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 3 ]
    [[ "$output" == *'sem pacote/adaptador definido'* ]]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup detecta binário incompatível que passará a ter prioridade no PATH' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/.local/bin"
    printf '#!/usr/bin/env bash\nprintf "uv 0.1.0\\n"\n' >"$HOME/.local/bin/uv"
    /usr/bin/chmod 755 "$HOME/.local/bin/uv"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 3 ]
    [[ "$output" == *'uv incompatível'* ]]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup redetecta ferramentas após reparar um diretório do PATH' {
    prepare_setup
    /usr/bin/mkdir -p "$HOME/.local/bin"
    printf '#!/usr/bin/env bash\nprintf "uv 0.1.0\\n"\n' >"$HOME/.local/bin/uv"
    /usr/bin/chmod 755 "$HOME/.local/bin/uv"
    /usr/bin/chmod 775 "$HOME/.local/bin"
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Retirar escrita=s" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 3 ]
    [[ "$output" == *'uv incompatível'* ]]
    [ "$(/usr/bin/stat -c %a "$HOME/.local/bin")" = 755 ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup inclui o diretório de transações na revisão antes da aplicação' {
    prepare_setup
    /usr/bin/mkdir -p "$XDG_STATE_HOME/devshell/transactions"
    /usr/bin/chmod 775 "$XDG_STATE_HOME/devshell/transactions"
    run "$SETUP_REPO/bin/devshell" setup --profile minimal --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys,os;p=json.load(sys.stdin);assert any(i["path"]==os.environ["XDG_STATE_HOME"]+"/devshell/transactions" for i in p["permissions"])'
    run bash -c 'python3 "$FOUNDRY_ROOT/tests/answer.py" "Retirar escrita=s" "Aplicar os dotfiles=s" -- "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    [ "$(/usr/bin/stat -c %a "$XDG_STATE_HOME/devshell/transactions")" = 755 ]
    [ -f "$HOME/.zshenv" ]
}
