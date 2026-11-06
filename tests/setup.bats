#!/usr/bin/env bats
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
elif 'tool' in args and 'install' in args:
    name,version=args[-1].split('==')
    receipt=Path(os.environ['UV_TOOL_DIR'])/name/'uv-receipt.toml'
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(f'[tool]\nrequirements = [{{ name = "{name}", specifier = "=={version}" }}]\n')
    binary=Path(os.environ['UV_TOOL_DIR'])/name/'bin'/name
    binary.parent.mkdir(parents=True,exist_ok=True);binary.write_text(f'#!/bin/sh\nprintf "{version}\\n"\n');binary.chmod(0o755)
    entry=Path(os.environ['UV_TOOL_BIN_DIR'])/name
    entry.parent.mkdir(parents=True,exist_ok=True);entry.symlink_to(binary)
    dist=binary.parent.parent/'lib/python3.13/site-packages'/f'{name.replace("-", "_")}-{version}.dist-info'
    dist.mkdir(parents=True,exist_ok=True)
    (dist/'METADATA').write_text(f'Name: {name}\nVersion: {version}\n')
    checksum=base64.urlsafe_b64encode(hashlib.sha256(binary.read_bytes()).digest()).decode().rstrip('=')
    records=[f'../../../bin/{name},sha256={checksum},{binary.stat().st_size}\n']
    required={'pre-commit':['pre_commit/__init__.py','pre_commit/main.py'], 'ipython':['IPython/__init__.py']}.get(name,[])
    for relative in required:
        module=dist.parent/relative;module.parent.mkdir(parents=True,exist_ok=True);module.write_text('# fixture\n')
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
    run bash -c 'printf "s\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal'
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
    run bash -c 'printf "n\n" | "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -ne 0 ]
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
    run bash -c 'printf "n\n" | "$SETUP_REPO/bin/devshell" setup --profile extras'
    [ "$status" -ne 0 ]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup offline não chama gerenciador de pacotes com respostas positivas' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship"
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile personal --offline'
    [ "$status" -ne 0 ]
    [[ "$output" == *offline* ]]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup interrompe após falha administrativa e não aplica dotfiles' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship"
    export SETUP_NATIVE_FAIL=1
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 17 ]
    [ -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup não sobrescreve conflito sem confirmação explícita' {
    prepare_setup
    printf 'minha configuração\n' >"$HOME/.zshenv"
    run bash -c 'printf "s\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -ne 0 ]
    [ "$(/usr/bin/cat "$HOME/.zshenv")" = 'minha configuração' ]
    [ ! -e "$XDG_STATE_HOME/devshell/latest" ]
}

@test 'setup aceita conflito com confirmação e mantém backup para rollback' {
    prepare_setup
    printf 'minha configuração\n' >"$HOME/.zshenv"
    run bash -c 'printf "s\nsubstituir\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    hash=$("$SETUP_REPO/bin/devshell" rollback --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["approval"])')
    "$SETUP_REPO/bin/devshell" rollback --approve "$hash"
    [ "$(/usr/bin/cat "$HOME/.zshenv")" = 'minha configuração' ]
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
    run bash -c 'printf "s\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal'
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
    run bash -c 'printf "s\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal --offline'
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
    run bash -c 'printf "s\ns\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile personal'
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
    run bash -c 'printf "s\nn\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 1 ]
    [[ "$output" == *'componente pyinit conforme este plano?'* ]]
    [ ! -e "$HOME/.local/bin/pyinit" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup science reutiliza uv compatível e instala Python isolado e pyinit' {
    prepare_setup
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    [ -x "$HOME/.local/bin/pyinit" ]
    python3 - <<'PY'
import os
calls=open(os.environ['SETUP_LOG']).read().splitlines()
assert len(calls)==5,calls
assert sum(' python install --no-bin ' in line for line in calls)==2
assert sum(' tool install --managed-python --no-python-downloads ' in line for line in calls)==3
assert all('--offline' in line and '--force' not in line for line in calls)
PY
}

@test 'science informa DuckDB opcional ausente sem bloquear outras instalações' {
    prepare_setup
    run "$SETUP_REPO/bin/devshell" setup --profile science --dry-run --json
    [ "$status" -eq 0 ]
    printf '%s' "$output" | python3 -c 'import json,sys;p=json.load(sys.stdin);assert "duckdb" in p["components"];assert "duckdb" in p["dependencies"]["optional_missing"];assert not p["blockers"]'
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
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

@test 'doctor relata ferramenta uv removida ou com versão divergente' {
    prepare_setup
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    /usr/bin/rm "$UV_TOOL_BIN_DIR/ruff"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("ferramenta uv ausente: ruff" in s for s in json.load(sys.stdin)["issues"])'
    printf '#!/usr/bin/env bash\nexit 0\n' >"$UV_TOOL_BIN_DIR/ruff"
    /usr/bin/chmod +x "$UV_TOOL_BIN_DIR/ruff"
    printf '[tool]\nrequirements = [{ name = "ruff", specifier = "==0.1.0" }]\n' >"$UV_TOOL_DIR/ruff/uv-receipt.toml"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("versão da ferramenta uv divergente: ruff" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'doctor identifica recibo inválido e binário uv de versão incorreta' {
    prepare_setup
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    printf '[tool]\nrequirements = ["ruff"]\n' >"$UV_TOOL_DIR/ruff/uv-receipt.toml"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("recibo" in s and "ruff" in s for s in json.load(sys.stdin)["issues"])'
    printf '[tool]\nrequirements = [{ name = "ruff", specifier = "==0.17.3" }]\n' >"$UV_TOOL_DIR/ruff/uv-receipt.toml"
    printf '#!/usr/bin/env bash\nprintf "ruff 0.1.0\\n"\n' >"$UV_TOOL_BIN_DIR/ruff"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("executável uv divergente: ruff" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'doctor identifica metadado de versão incorreto no interpretador uv' {
    prepare_setup
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    printf '#define PY_VERSION "3.1.0"\n' >"$UV_PYTHON_INSTALL_DIR/cpython-3.12.12-fixture/include/python3.12/patchlevel.h"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("interpretador uv divergente: 3.12.12" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'doctor não executa ferramenta uv alterada ao verificar sua versão' {
    prepare_setup
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    printf '#!/bin/sh\ntouch "%s"\nprintf "0.17.3\\n"\n' "$HOME/doctor-executou" >"$UV_TOOL_BIN_DIR/ruff"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    [ ! -e "$HOME/doctor-executou" ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("executável uv divergente: ruff" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'doctor detecta interpretador ausente no launcher mesmo com RECORD válido' {
    prepare_setup
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    printf '#!/caminho/inexistente/python\n' >"$UV_TOOL_BIN_DIR/ruff"
    python3 - <<'PY'
import base64,hashlib,os
from pathlib import Path
root=Path(os.environ['UV_TOOL_DIR'])/'ruff'
binary=root/'bin/ruff'
record=next((root/'lib').glob('python*/site-packages/ruff-*.dist-info/RECORD'))
checksum=base64.urlsafe_b64encode(hashlib.sha256(binary.read_bytes()).digest()).decode().rstrip('=')
record.write_text(f'../../../bin/ruff,sha256={checksum},{binary.stat().st_size}\n')
PY
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("interpretador do launcher" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'doctor detecta módulo essencial ausente em ferramenta uv' {
    prepare_setup
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science --offline'
    [ "$status" -eq 0 ]
    /usr/bin/rm "$UV_TOOL_DIR/pre-commit/lib/python3.13/site-packages/pre_commit/main.py"
    run "$SETUP_REPO/bin/devshell" doctor --profile science --json
    [ "$status" -eq 3 ]
    printf '%s' "$output" | python3 -c 'import json,sys;assert any("módulo essencial" in s and "pre-commit" in s for s in json.load(sys.stdin)["issues"])'
}

@test 'doctor detecta alteração dos arquivos essenciais de plugin e fonte' {
    prepare_setup
    seed_artifact plugins
    seed_artifact firacode
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile personal --offline'
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
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile personal'
    [ "$status" -eq 3 ]
    [[ "$output" == *'sudo ausente'* ]]
    [ ! -e "$SETUP_LOG" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup recusa versão incompatível em vez de substituir executável' {
    prepare_setup
    printf '#!/usr/bin/env bash\nprintf "uv 0.1.0\\n"\n' >"$SETUP_BIN/uv"
    run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile science'
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
    DEVSHELL_OS_RELEASE="$BATS_TEST_TMPDIR/fedora" run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile personal'
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
    run bash -c 'printf "s\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal --offline'
    [ "$status" -eq 2 ]
    [[ "$output" == *'cache corrompido:'* && "$output" == *'/devshell/artifacts/'* ]]
    [ ! -e "$HOME/.local/bin/chezmoi" ]
    [ ! -e "$HOME/.zshenv" ]
}

@test 'setup sem adaptador não tenta pacote ou download com confirmação positiva' {
    prepare_setup
    /usr/bin/rm "$SETUP_BIN/starship"
    printf 'ID=unknown\n' >"$BATS_TEST_TMPDIR/unknown"
    DEVSHELL_OS_RELEASE="$BATS_TEST_TMPDIR/unknown" run bash -c 'printf "s\ns\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile personal'
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
    run bash -c 'printf "s\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal'
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
    run bash -c 'printf "s\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal'
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
    run bash -c 'printf "s\ns\n" | "$SETUP_REPO/bin/devshell" setup --profile minimal'
    [ "$status" -eq 0 ]
    [ "$(/usr/bin/stat -c %a "$XDG_STATE_HOME/devshell/transactions")" = 755 ]
    [ -f "$HOME/.zshenv" ]
}
