#!/usr/bin/env python3
"""Instalação explícita de artefatos oficiais fixados; sem instaladores shell."""
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile

# -I exclui o diretório do script; somente a lib da CLI é adicionada.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import python_tools
import state as fs

DATA = fs.xdg('XDG_DATA_HOME', fs.HOME / '.local/share')
CACHE = fs.xdg('XDG_CACHE_HOME', fs.HOME / '.cache') / 'devshell/artifacts'
BIN = fs.HOME / '.local/bin'
COMPONENT = os.environ['DEVSHELL_COMPONENT']


def health_issues():
    import launcher
    issues = launcher.health_issues()
    manifest = json.loads((fs.ROOT / 'manifests/artifacts.json').read_text())['artifacts']
    for artifact in manifest:
        component = artifact['component']
        if component not in ('plugins', 'firacode', 'pyinit') or component not in fs.COMPONENTS:
            continue
        root = DATA / 'devshell/plugins' / artifact['name'] if component == 'plugins' else DATA / 'fonts/FiraCodeNerdFont'
        checks = artifact.get('health', {})
        if component == 'pyinit':
            root, checks = BIN, {'pyinit': artifact['sha256']}
        if not checks:
            issues.append(f'checksums de diagnóstico ausentes: {component}')
        for name, checksum in checks.items():
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name or not re.fullmatch(r'[a-f0-9]{64}', checksum):
                issues.append(f'checksum de diagnóstico inválido: {component}')
                continue
            path = root / name
            try:
                current = fs.snapshot(path)
                if not current:
                    issues.append(f'componente de usuário ausente: {path}')
                elif current['sha256'] != checksum:
                    issues.append(f'integridade do componente divergente: {path}')
                elif component == 'pyinit' and not current['mode'] & 0o100:
                    issues.append(f'componente não executável: {path}')
            except (ValueError, OSError) as exc:
                issues.append(str(exc))
    if 'python-tools' not in fs.COMPONENTS:
        return issues
    try:
        spec, dirs = python_spec(), python_dirs()
        python_dir = Path(dirs['UV_PYTHON_INSTALL_DIR'])
        for version in spec['interpreters']:
            candidates = [path for path in python_dir.glob(f'cpython-{version}-*') if os.access(path / 'bin/python3', os.X_OK)]
            if not candidates:
                issues.append(f'interpretador uv ausente: {version}')
                continue
            found = False
            for candidate in candidates:
                try:
                    fs.safe_path((candidate / 'bin/python3').resolve())
                    header = candidate / 'include' / ('python' + '.'.join(version.split('.')[:2])) / 'patchlevel.h'
                    fs.safe_path(header)
                    match = re.search(r'^#define\s+PY_VERSION\s+"([^"]+)"', header.read_text(), re.M)
                    if match and match.group(1) == version:
                        found = True
                        break
                except (OSError, ValueError):
                    continue
            if not found:
                issues.append(f'interpretador uv divergente: {version}')
        issues.extend(python_tools.health_issues(spec, dirs))
    except (ValueError, OSError, KeyError) as exc:
        issues.append(f'não foi possível verificar componentes uv: {exc}')
    return issues


def python_spec():
    spec = json.loads((fs.ROOT / 'manifests/python.json').read_text())
    for version in [*spec['interpreters'], spec['tool_python']]:
        if not re.fullmatch(r'3\.\d+\.\d+', version):
            raise ValueError('versão Python deve ser CPython estável fixado em patch')
    if spec['tool_python'] not in spec['interpreters']:
        raise ValueError('interpretador das ferramentas ausente da lista')
    for tool in spec['tools']:
        if not re.fullmatch(r'[a-z][a-z0-9-]*', tool['name']) or not re.fullmatch(r'\d+(\.\d+)+', tool['version']):
            raise ValueError('ferramenta Python deve ter nome e versão exatos')
    if 'python-tools' not in fs.COMPONENTS:
        spec['tools'] = []
    python_tools.locks(spec)
    return spec


def python_dirs(validate=True):
    defaults = {'UV_PYTHON_INSTALL_DIR': DATA / 'uv/python', 'UV_TOOL_DIR': DATA / 'uv/tools',
                'UV_TOOL_BIN_DIR': fs.xdg('XDG_BIN_HOME', (fs.xdg('XDG_DATA_HOME', fs.HOME / '.local/share').parent / 'bin')), 'UV_CACHE_DIR': fs.xdg('XDG_CACHE_HOME', fs.HOME / '.cache') / 'uv'}
    result = {}
    for key, default in defaults.items():
        path = Path(os.environ.get(key) or default)
        if validate:
            if key == 'UV_TOOL_BIN_DIR' and ':' in str(path):
                raise ValueError('UV_TOOL_BIN_DIR contém dois-pontos, incompatível com PATH')
            fs.safe_path(path)
        result[key] = str(path)
    return result


def install_plan():
    if COMPONENT not in ('uv', 'chezmoi', 'nu', 'plugins', 'python', 'firacode', 'pyinit'):
        raise ValueError('componente de instalação desconhecido')
    plan = {'operation': 'install-' + COMPONENT}
    if COMPONENT == 'python':
        spec = python_spec()
        commands = [['uv', '--no-config', '--no-progress', 'python', 'install', '--no-bin', v] for v in spec['interpreters']]
        dirs = python_dirs()
        tools = python_tools.plan_tools(spec, dirs)
        blocked = [f"{row['name']} ({row['state']}): {row['detail'][0]}" for row in tools if row['state'] in python_tools.BLOCKING]
        if blocked:
            raise ValueError('ferramentas Python exigem ação manual antes da instalação: ' + ' | '.join(blocked))
        offline = os.environ['DEVSHELL_OFFLINE'] == '1'
        for row in tools:
            if row['state'] == 'ausente':
                commands += python_tools.commands(row, spec, offline)
        plan |= {'commands': commands, 'directories': dirs, 'spec': spec, 'tools': tools}
    else:
        artifacts = json.loads((fs.ROOT / 'manifests/artifacts.json').read_text())['artifacts']
        selected = [a for a in artifacts if a['component'] == COMPONENT and a['arch'] in ('any', os.environ['DEVSHELL_MACHINE']) and a['libc'] in ('any', os.environ['DEVSHELL_LIBC'])]
        if not selected:
            raise ValueError('sem artefato controlado para esta arquitetura/libc; instalação manual necessária')
        for artifact in selected:
            if not re.fullmatch(r'[a-f0-9]{64}', artifact['sha256']):
                raise ValueError('checksum inválido no manifesto')
            url = urllib.parse.urlparse(artifact['url'])
            if url.scheme != 'https' or url.hostname not in ('github.com', 'api.github.com') or url.username:
                raise ValueError('origem de download não autorizada')
        destination = DATA / 'fonts/FiraCodeNerdFont' if COMPONENT == 'firacode' else DATA / 'devshell/plugins' if COMPONENT == 'plugins' else BIN
        fs.safe_path(destination)
        plan |= {'artifacts': selected, 'destination': str(destination)}
        if COMPONENT == 'firacode':
            plan['commands'] = [['fc-cache', '-f', str(destination)]]
    plan['source_sha256'] = fs.build_plan()['source_sha256']
    plan['approval'] = fs.digest(fs.encode(plan))
    return plan


def check(plan):
    if os.environ['DEVSHELL_APPROVAL'] != plan['approval']:
        raise ValueError('aprovação inválida: revise install sem --approve primeiro')
    if COMPONENT == 'firacode' and not shutil.which('fc-cache'):
        raise RuntimeError('fc-cache ausente; instale fontconfig pela distribuição')
    if COMPONENT == 'python':
        executable = shutil.which('uv')
        if not executable:
            raise RuntimeError('uv ausente')
        result = subprocess.run([executable, '--version'], capture_output=True, text=True, check=True)
        match = re.search(r'uv (\d+)\.(\d+)\.(\d+)', result.stdout)
        floor = python_tools.UV_FLOOR if plan['spec']['tools'] else (0, 9, 0)
        if not match or tuple(map(int, match.groups())) < floor:
            raise ValueError(f"requer uv >={'.'.join(map(str, floor))} para este plano; instale a versão fixada")


def members(artifact, content):
    if fs.digest(content) != artifact['sha256']:
        raise ValueError('SHA-256 divergente: artefato recusado')
    if artifact['format'] == 'raw':
        return {artifact['binary']: content}
    if artifact['format'] == 'zip' and artifact['component'] == 'firacode':
        return font_members(content)
    result = {}
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:gz') as archive:
        items = archive.getmembers()
        if sum(item.size for item in items) > 1024**3:
            raise ValueError('arquivo compactado excede limite de 1 GiB')
        for item in items:
            path = PurePosixPath(item.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('entrada insegura em arquivo compactado')
            # Os links README oficiais não são necessários em runtime; nunca extraí-los.
            if artifact['component'] == 'plugins' and item.issym() and path.name == 'README.md':
                continue
            if not (item.isdir() or item.isfile()):
                raise ValueError('entrada insegura em arquivo compactado')
            if not item.isfile():
                continue
            if artifact['component'] == 'plugins':
                path = PurePosixPath(*path.parts[1:])
                if not path.parts or '.git' in path.parts:
                    raise ValueError('fonte de plugin inválida')
                name = str(path)
            else:
                if path.name not in artifact.get('binaries', [artifact['binary']]):
                    continue
                name = path.name
            if name in result:
                raise ValueError('membro duplicado no arquivo compactado')
            result[name] = archive.extractfile(item).read()
    if not result or (artifact['component'] != 'plugins' and set(result) != set(artifact.get('binaries', [artifact['binary']]))):
        raise ValueError('artefato não contém arquivos esperados')
    return result


def font_members(content):
    result = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        items = archive.infolist()
        if sum(item.file_size for item in items) > 1024**3:
            raise ValueError('arquivo compactado excede limite de 1 GiB')
        for item in items:
            path = PurePosixPath(item.filename)
            kind = stat.S_IFMT(item.external_attr >> 16)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename or kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('entrada insegura em arquivo compactado')
            if item.is_dir():
                continue
            if path.suffix != '.ttf' and path.name != 'LICENSE':
                continue
            if path.name in result:
                raise ValueError('membro duplicado no arquivo compactado')
            result[path.name] = archive.read(item)
    if not {'FiraCodeNerdFontMono-Regular.ttf', 'LICENSE'} <= result.keys():
        raise ValueError('artefato não contém arquivos esperados da FiraCode')
    return result


def download(artifact):
    cached = CACHE / artifact['sha256']
    fs.safe_path(cached)
    if cached.exists():
        content = cached.read_bytes()
        if fs.digest(content) != artifact['sha256']:
            raise ValueError(f'cache corrompido: {cached}; revise e remova somente esse arquivo antes de tentar novamente')
        return content
    if os.environ['DEVSHELL_OFFLINE'] == '1':
        raise RuntimeError('offline: artefato ausente do cache verificado')
    with urllib.request.urlopen(artifact['url'], timeout=60) as response:
        if not response.url.startswith('https://'):
            raise ValueError('redirecionamento sem TLS recusado')
        content = response.read(256 * 1024**2 + 1)
    if len(content) > 256 * 1024**2 or fs.digest(content) != artifact['sha256']:
        raise ValueError('artefato excede limite ou checksum divergiu')
    fs.atomic(cached, content)
    return content


def apply(plan):
    check(plan)
    files = {}
    for artifact in plan['artifacts']:
        content = download(artifact)
        for relative, data in members(artifact, content).items():
            target = Path(plan['destination'])
            if COMPONENT == 'plugins':
                target /= artifact['name']
            target /= relative
            before = fs.snapshot(target)
            if before and before['sha256'] != fs.digest(data):
                raise ValueError(f'instalação preexistente diferente: {target}; atualize manualmente')
            files[target] = data
    changed = 0
    with fs.locked():
        for path, data in files.items():
            before = fs.snapshot(path)
            if before and before['sha256'] != fs.digest(data):
                raise ValueError(f'alvo mudou durante instalação: {path}')
        for path, data in files.items():
            before = fs.snapshot(path)
            if not before:
                fs.atomic(path, data, mode=0o644 if COMPONENT in ('plugins', 'firacode') else 0o755)
                changed += 1
            elif COMPONENT not in ('plugins', 'firacode') and not before['mode'] & 0o100:
                fs.atomic(path, data, metadata=before | {'mode': before['mode'] | 0o100})
                changed += 1
        if COMPONENT == 'firacode':
            # Repetir também após falha anterior na atualização do cache.
            subprocess.run(plan['commands'][0], check=True, capture_output=True)
    fs.report({'operation': plan['operation'], 'changed': changed,
               'message': 'Instalações não são removidas por rollback de dotfiles; consulte SECURITY.md.'})


def report_plan(plan):
    fs.report(plan)
    if os.environ['DEVSHELL_JSON'] != '1':
        for command in plan.get('commands', []):
            import shlex
            print('  ', shlex.join(command))
        for row in plan.get('tools', []):
            print(f"   ferramenta {row['name']}: {row['state']}; venv {row['venv']}; link {row['link']} -> {row['venv']}/bin/{row['name']}")
        for artifact in plan.get('artifacts', []):
            print('  ', artifact.get('name', plan['operation'].removeprefix('install-')), artifact['version'], artifact['url'], artifact['sha256'])


def main():
    command = sys.argv[1]
    if command == 'python-done':
        # Depois da instalação o estado mudou; o resumo não depende do plano.
        fs.report({'operation': 'install-python', 'message': 'Interpretadores e ferramentas uv processados; projetos externos preservados.'})
        return
    plan = install_plan()
    if command == 'plan':
        report_plan(plan)
    elif command == 'check':
        check(plan)
    elif command == 'apply':
        apply(plan)
    elif command == 'python-dirs':
        check(plan)
        for key, value in python_dirs().items():
            if '\n' in value or '\r' in value:
                raise ValueError('diretório uv contém quebra de linha')
            print(key + '=' + value)
    elif command == 'python-spec':
        check(plan)
        print(json.dumps(python_spec()))
    elif command == 'python-tools':
        check(plan)
        done = python_tools.apply(plan, python_dirs())
        # stdout fica para o relatório único de python-done (contrato do --json).
        print(f"Ferramentas instaladas com hash obrigatório: {', '.join(done) or 'nenhuma alteração'}", file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, tarfile.TarError, zipfile.BadZipFile, urllib.error.URLError, subprocess.CalledProcessError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
