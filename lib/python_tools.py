#!/usr/bin/env python3
"""Ferramentas Python em venvs próprias, instaladas por lock com hash obrigatório (ADR 004)."""
import base64
import csv
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

# -I exclui o diretório do script; somente a lib da CLI é adicionada.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import state as fs

LOCKS = fs.ROOT / 'manifests/python-tools'
UV_FLOOR = fs.UV_HASH_FLOOR
REQUIREMENT = re.compile(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)')
HASH = re.compile(r'--hash=sha256:([0-9a-f]{64})')
ESSENTIAL = {'pre-commit': ['pre_commit/__init__.py', 'pre_commit/main.py'], 'ipython': ['IPython/__init__.py']}
BLOCKING = ('link-orfao', 'divergente', 'conflito')


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def read_lock(path):
    """Lê um lock de `uv pip compile --generate-hashes`; marcadores são guardados, não avaliados."""
    # O lock é fonte do checkout, confiado como o resto do código (SECURITY.md).
    if not path.is_file():
        raise ValueError(f'lock da ferramenta ausente: {path}')
    text = path.read_text()
    header = re.search(r'^#.*--python-version (\d+\.\d+)', text, re.M)
    logical, current = [], ''
    for raw in text.splitlines():
        line = raw.split(' #', 1)[0].rstrip() if not raw.lstrip().startswith('#') else ''
        if not line.strip() and not current:
            continue
        current += ' ' + line.strip().removesuffix('\\')
        if not line.endswith('\\'):
            logical.append(current.strip())
            current = ''
    if current.strip():
        logical.append(current.strip())
    requirements = {}
    for line in logical:
        spec = line.split('--hash', 1)[0].strip()
        requirement, _, marker = (part.strip() for part in spec.partition(';'))
        match = REQUIREMENT.fullmatch(requirement)
        hashes = HASH.findall(line)
        if not match or not hashes or line.count('--hash') != len(hashes):
            raise ValueError(f'lock inválido em {path.name}: requisito sem == ou sem hash sha256: {requirement or line}')
        name = normalize(match.group(1))
        # shortcut: um nome por lock; se o uv emitir versões por marcador, aceitar marcadores disjuntos.
        if name in requirements:
            raise ValueError(f'lock inválido em {path.name}: requisito duplicado: {name}')
        requirements[name] = {'version': match.group(2), 'marker': marker or None}
    return {'python_version': header.group(1) if header else None, 'requirements': requirements}


def locks(spec):
    """Valida o lock de cada ferramenta contra manifests/python.json (R-020)."""
    minor = '.'.join(spec['tool_python'].split('.')[:2])
    result = {}
    for tool in spec['tools']:
        name, version = tool['name'], tool['version']
        lock = read_lock(LOCKS / f'{name}.txt')
        if lock['python_version'] != minor:
            raise ValueError(f'lock de {name} gerado para Python {lock["python_version"]}; esperado {minor}')
        root = lock['requirements'].get(normalize(name))
        if not root or root['version'] != version or root['marker']:
            raise ValueError(f'lock de {name} não fixa {name}=={version}')
        result[name] = lock
    return result


def paths(name, dirs):
    venv = fs.xdg('XDG_DATA_HOME', fs.HOME / '.local/share') / 'devshell/tools' / name
    return venv, Path(dirs['UV_TOOL_BIN_DIR']) / name


def record_hash(content):
    return 'sha256=' + base64.urlsafe_b64encode(bytes.fromhex(fs.digest(content))).decode().rstrip('=')


def venv_issues(name, venv, lock, tool_python, python_dir):
    """Conferência da venv sem executar a ferramenta nem chamar o uv (R-023)."""
    fs.safe_path(venv)
    if not venv.is_dir():
        return ['venv não é diretório']
    config = venv / 'pyvenv.cfg'
    fs.safe_path(config)
    if not config.is_file() or config.is_symlink():
        return ['pyvenv.cfg ausente']
    values = dict(line.split('=', 1) for line in config.read_text().splitlines() if '=' in line)
    values = {key.strip(): value.strip() for key, value in values.items()}
    if values.get('version_info') != tool_python:
        return [f"Python da venv {values.get('version_info')}; esperado {tool_python}"]
    minor = '.'.join(tool_python.split('.')[:2])
    interpreter = (venv / 'bin/python').resolve(strict=True)
    fs.safe_path(interpreter)
    if not python_dir or not interpreter.is_relative_to(Path(python_dir).resolve()):
        return ['interpretador da venv fora do CPython gerenciado (UV_PYTHON_INSTALL_DIR)']
    header = interpreter.parent.parent / 'include' / f'python{minor}' / 'patchlevel.h'
    fs.safe_path(header)
    match = re.search(r'^#define\s+PY_VERSION\s+"([^"]+)"', header.read_text(), re.M) if header.is_file() else None
    if not match or match.group(1) != tool_python:
        return ['interpretador da venv não é o CPython gerenciado de tool_python']
    site = venv / 'lib' / f'python{minor}' / 'site-packages'
    fs.safe_path(site)
    issues, installed = [], {}
    for metadata in sorted(site.glob('*.dist-info/METADATA')):
        fs.safe_path(metadata)
        text = metadata.read_text()
        dist = re.search(r'^Name:\s*(\S+)', text, re.M)
        version = re.search(r'^Version:\s*(\S+)', text, re.M)
        if not dist or not version:
            issues.append(f'metadados ilegíveis: {metadata.parent.name}')
            continue
        installed[normalize(dist.group(1))] = (version.group(1), metadata.parent)
    for dist, (version, _) in installed.items():
        expected = lock['requirements'].get(dist)
        if not expected:
            issues.append(f'{dist} {version} fora do lock')
        elif expected['version'] != version:
            issues.append(f"{dist} {version}, lock {expected['version']}")
    for dist, expected in lock['requirements'].items():
        if not expected['marker'] and dist not in installed:
            issues.append(f"{dist} {expected['version']} do lock não instalado")
    if normalize(name) not in installed:
        return issues
    info = installed[normalize(name)][1]
    record = info / 'RECORD'
    fs.safe_path(record)
    with record.open(newline='') as stream:
        rows = [row for row in csv.reader(stream) if len(row) >= 2]
    executable = venv / 'bin' / name
    fs.safe_path(executable)
    content = executable.read_bytes() if executable.is_file() else b''
    if [row[1] for row in rows if row[0] == f'../../../bin/{name}'] != [record_hash(content)]:
        issues.append('executável diverge do RECORD')
    elif content.startswith(b'#!'):
        shebang = content.split(b'\n', 1)[0][2:].strip().split(maxsplit=1)
        launcher = Path(os.fsdecode(shebang[0])) if shebang else None
        if not launcher or not launcher.is_absolute() or not os.access(launcher, os.X_OK):
            issues.append('interpretador do launcher ausente ou não executável')
    for relative in ESSENTIAL.get(name, []):
        module = site / relative
        fs.safe_path(module)
        hashes = [row[1] for row in rows if row[0] == relative]
        if not module.is_file() or hashes != [record_hash(module.read_bytes())]:
            issues.append(f'módulo essencial divergente: {relative}')
    return issues


def tool_state(name, lock, dirs, tool_python):
    """Classifica a ferramenta conforme a tabela de T-204 do plano."""
    venv, link = paths(name, dirs)
    fs.safe_path(link.parent)
    try:
        fs.safe_path(venv)
    except ValueError as exc:
        return {'name': name, 'state': 'divergente', 'venv': str(venv), 'link': str(link),
                'detail': [f'{venv}: {exc}; revise o caminho antes de instalar']}
    expected = str(venv / 'bin' / name)
    if not os.path.lexists(link):
        link_state = 'ausente'
    elif link.is_symlink() and os.readlink(link) == expected:
        link_state = 'nosso'
    else:
        link_state = 'outro'
    detail = []
    if os.path.lexists(venv):
        try:
            detail = venv_issues(name, venv, lock, tool_python, dirs.get('UV_PYTHON_INSTALL_DIR'))
        except (OSError, ValueError, RuntimeError, csv.Error) as exc:
            detail = [str(exc)]
        venv_state = 'divergente' if detail else 'conforme'
    else:
        venv_state = 'ausente'
    if link_state == 'outro':
        target = os.readlink(link) if link.is_symlink() else 'arquivo'
        state = 'conflito'
        detail = [f'{link} já existe ({target}); se for do uv tool, rode `uv tool uninstall {name}` e planeje de novo']
    elif venv_state == 'divergente':
        state = 'divergente'
        detail = [f'{venv}: ' + '; '.join(detail) + '; revise e mova a venv para fora de devshell/tools']
    elif venv_state == 'ausente':
        state = 'link-orfao' if link_state == 'nosso' else 'ausente'
        if state == 'link-orfao':
            detail = [f'{link} aponta para venv ausente; revise e remova o link']
    else:
        state = 'conforme' if link_state == 'nosso' else 'sem-link'
        if state == 'sem-link':
            detail = [f'venv conforme sem link em {link}; aprove install --component python']
    return {'name': name, 'state': state, 'venv': str(venv), 'link': str(link), 'detail': detail}


def plan_tools(spec, dirs):
    states = []
    for name, lock in locks(spec).items():
        states.append(tool_state(name, lock, dirs, spec['tool_python']) | {'lock': str(LOCKS / f'{name}.txt')})
    return states


def blockers(spec, dirs):
    return [f"ferramenta uv {row['state']}: {row['name']}: {row['detail'][0]}"
            for row in plan_tools(spec, dirs) if row['state'] in BLOCKING]


def link_conflicts(spec, dirs):
    """Antes do reparo de permissões: só lê os links, sem seguir nem conferir ancestrais."""
    messages = []
    for tool in spec['tools']:
        venv, link = paths(tool['name'], dirs)
        if os.path.lexists(link) and not (link.is_symlink() and os.readlink(link) == str(venv / 'bin' / tool['name'])):
            messages.append(f"ferramenta uv conflito: {tool['name']}: {link} já existe; se for do uv tool, "
                            f"rode `uv tool uninstall {tool['name']}` e planeje de novo")
    return messages


def commands(row, spec, offline):
    venv = row['venv']
    online = ['--offline'] if offline else []
    return [['uv', '--no-config', '--no-progress', 'venv', '--managed-python', '--no-python-downloads', *online,
             '--python', spec['tool_python'], venv],
            ['uv', '--no-config', '--no-progress', 'pip', 'install', *online, '--python', f'{venv}/bin/python',
             '--require-hashes', '--no-build', '--link-mode', 'copy', '-r', row['lock']]]


def uv_environment(dirs):
    """Sem venv ativa nem configuração UV_* do usuário além dos diretórios aprovados."""
    removed = ('VIRTUAL_ENV', 'CONDA_PREFIX', 'PYTHONHOME', 'PYTHONPATH')
    env = {key: value for key, value in os.environ.items() if not key.startswith('UV_') and key not in removed}
    return env | {key: dirs[key] for key in ('UV_PYTHON_INSTALL_DIR', 'UV_CACHE_DIR')}


def apply(plan, dirs):
    """Instala as ferramentas aprovadas sob o lock; falha remove só a venv criada nesta execução (D-012)."""
    executable = shutil.which('uv')
    if not executable:
        raise RuntimeError('uv ausente')
    done = []
    with fs.locked():
        current = plan_tools(plan['spec'], dirs)
        if [{k: row[k] for k in ('name', 'state')} for row in current] != [{k: row[k] for k in ('name', 'state')} for row in plan['tools']]:
            raise RuntimeError('estado das ferramentas mudou depois do plano; planeje novamente')
        for row in current:
            if row['state'] in BLOCKING:
                raise RuntimeError(f"ferramenta {row['name']} bloqueada: {row['detail'][0]}")
            venv, link = Path(row['venv']), Path(row['link'])
            if row['state'] == 'ausente':
                fs.safe_path(venv)
                venv.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                fs.safe_path(venv.parent)
                os.mkdir(venv, 0o700)
                try:
                    for command in commands(row, plan['spec'], os.environ['DEVSHELL_OFFLINE'] == '1'):
                        subprocess.run([executable, *command[1:]], check=True, env=uv_environment(dirs),
                                       stdout=sys.stderr)
                    if not (venv / 'bin' / row['name']).is_file():
                        raise RuntimeError(f"executável {row['name']} não criado na venv")
                except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
                    shutil.rmtree(venv)
                    raise RuntimeError(f"instalação de {row['name']} falhou e a venv foi removida; "
                                       f"concluídas: {', '.join(done) or 'nenhuma'}: {exc}") from exc
            if row['state'] in ('ausente', 'sem-link'):
                link.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                os.symlink(venv / 'bin' / row['name'], link)
                done.append(row['name'])
    return done


def health_issues(spec, dirs):
    issues = []
    for row in plan_tools(spec, dirs):
        if row['state'] == 'conforme':
            continue
        detail = row['detail'][0] if row['detail'] else 'não instalada; use install --component python'
        issues.append(f"ferramenta uv {row['state']}: {row['name']}: {detail}")
    return issues
