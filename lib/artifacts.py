#!/usr/bin/env python3
"""Instalação explícita de artefatos oficiais fixados; sem instaladores shell."""
import base64
import csv
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
import tomllib
import urllib.error
import urllib.request
import zipfile

import state as fs

DATA = fs.xdg('XDG_DATA_HOME', fs.HOME / '.local/share')
CACHE = fs.xdg('XDG_CACHE_HOME', fs.HOME / '.cache') / 'devshell/artifacts'
BIN = fs.HOME / '.local/bin'
COMPONENT = os.environ['DEVSHELL_COMPONENT']


def health_issues():
    issues = []
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
        for tool in spec['tools']:
            name, version = tool['name'], tool['version']
            receipt = Path(dirs['UV_TOOL_DIR']) / name / 'uv-receipt.toml'
            executable = Path(dirs['UV_TOOL_BIN_DIR']) / name
            if not receipt.is_file() or not os.access(executable, os.X_OK):
                issues.append(f'ferramenta uv ausente: {name}=={version}')
                continue
            fs.safe_path(receipt)
            try:
                data = tomllib.loads(receipt.read_text()).get('tool', {})
                requirements = data.get('requirements') if isinstance(data, dict) else None
                if not isinstance(requirements, list) or any(not isinstance(item, dict) for item in requirements):
                    raise ValueError('formato inválido')
            except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
                issues.append(f'recibo uv inválido: {name}: {exc}')
                continue
            if not any(item.get('name') == name and item.get('specifier') == '==' + version for item in requirements):
                issues.append(f'versão da ferramenta uv divergente: {name}=={version}')
            try:
                tool_root = Path(dirs['UV_TOOL_DIR']) / name
                target = (tool_root / 'bin' / name).resolve(strict=True)
                fs.safe_path(target)
                if executable.resolve(strict=True) != target:
                    raise ValueError('executável aponta para outro destino')
                metadata = list((tool_root / 'lib').glob('python*/site-packages/' + name.replace('-', '_') + '-*.dist-info/METADATA'))
                if len(metadata) != 1:
                    raise ValueError('metadados da distribuição ausentes ou ambíguos')
                fs.safe_path(metadata[0])
                match = re.search(r'^Version:\s*(\S+)', metadata[0].read_text(), re.M)
                if not match or match.group(1) != version:
                    raise ValueError('versão dos metadados divergente')
                record = metadata[0].with_name('RECORD')
                fs.safe_path(record)
                with record.open(newline='') as stream:
                    rows = [row for row in csv.reader(stream) if len(row) >= 2]
                hashes = [row[1] for row in rows if row[0] == '../../../bin/' + name]
                content = target.read_bytes()
                checksum = base64.urlsafe_b64encode(bytes.fromhex(fs.digest(content))).decode().rstrip('=')
                if hashes != ['sha256=' + checksum]:
                    raise ValueError('hash do executável diverge do RECORD')
                if content.startswith(b'#!'):
                    shebang = content.split(b'\n', 1)[0][2:].strip().split(maxsplit=1)
                    if not shebang:
                        raise ValueError('interpretador do launcher ausente')
                    interpreter = Path(os.fsdecode(shebang[0]))
                    if not interpreter.is_absolute() or not os.access(interpreter, os.X_OK):
                        raise ValueError('interpretador do launcher ausente ou não executável')
                    fs.safe_path(interpreter.resolve())
                required = {'pre-commit': ['pre_commit/__init__.py', 'pre_commit/main.py'],
                            'ipython': ['IPython/__init__.py']}.get(name, [])
                for relative in required:
                    module = metadata[0].parent.parent / relative
                    fs.safe_path(module)
                    hashes = [row[1] for row in rows if row[0] == relative]
                    if not module.is_file():
                        raise ValueError(f'módulo essencial ausente: {relative}')
                    checksum = base64.urlsafe_b64encode(bytes.fromhex(fs.digest(module.read_bytes()))).decode().rstrip('=')
                    if hashes != ['sha256=' + checksum]:
                        raise ValueError(f'módulo essencial divergente: {relative}')
            except (OSError, ValueError) as exc:
                issues.append(f'executável uv divergente: {name}; esperado {version}: {exc}')
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
        commands += [['uv', '--no-config', '--no-progress', 'tool', 'install', '--managed-python', '--no-python-downloads', '--python', spec['tool_python'], t['name'] + '==' + t['version']] for t in spec['tools']]
        plan |= {'commands': commands, 'directories': python_dirs(), 'spec': spec}
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
        if not match or tuple(map(int, match.groups())) < (0, 9, 0):
            raise ValueError('requer uv >=0.9.0 para --no-bin; instale a versão fixada')


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
        for artifact in plan.get('artifacts', []):
            print('  ', artifact.get('name', plan['operation'].removeprefix('install-')), artifact['version'], artifact['url'], artifact['sha256'])


def main():
    command = sys.argv[1]
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
    elif command == 'python-done':
        fs.report({'operation': 'install-python', 'message': 'Interpretadores e ferramentas uv processados; projetos externos preservados.'})


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, tarfile.TarError, zipfile.BadZipFile, urllib.error.URLError, subprocess.CalledProcessError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
