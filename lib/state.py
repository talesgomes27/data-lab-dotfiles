#!/usr/bin/env python3
"""Relatórios e fronteira de escrita de arquivos; somente biblioteca padrão."""
import contextlib
import difflib
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

os.umask(0o077)
ROOT = Path(os.environ['DEVSHELL_ROOT'])
HOME = Path(os.environ['HOME'])
if not HOME.is_absolute() or HOME == Path('/'):
    sys.exit('devshell: HOME deve ser um diretório absoluto de usuário.')


def xdg(name, default):
    value = Path(os.environ.get(name) or default)
    return value if value.is_absolute() else Path(default)


CONFIG = xdg('XDG_CONFIG_HOME', HOME / '.config')
STATE = xdg('XDG_STATE_HOME', HOME / '.local/state') / 'devshell'
COMPONENTS = os.environ['DEVSHELL_COMPONENTS'].split()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True).encode()


def path_issues(path):
    """Enumera riscos sem seguir symlinks; safe_path continua recusando o primeiro."""
    if not path.is_absolute() or '..' in path.parts:
        yield {'path': str(path), 'kind': 'path', 'message': f'caminho inseguro: {path}'}
        return
    system_uid = Path('/').stat().st_uid
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            yield {'path': str(part), 'kind': 'symlink', 'message': f'symlink recusado: {part}'}
            return
        if part.exists():
            info = part.stat()
            if info.st_uid not in (0, system_uid, os.getuid()):
                yield {'path': str(part), 'kind': 'owner', 'message': f'proprietário inesperado: {part}'}
            if info.st_mode & 0o022 and not (info.st_uid in (0, system_uid) and info.st_mode & stat.S_ISVTX):
                yield {'path': str(part), 'kind': 'permissions', 'message': f'permissões inseguras: {part}'}


def safe_path(path):
    for issue in path_issues(path):
        raise ValueError(issue['message'])


def snapshot(path):
    safe_path(path)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f'alvo não é arquivo regular independente: {path}')
    info = path.stat()
    if info.st_uid != os.getuid():
        raise ValueError(f'alvo não pertence ao usuário: {path}')
    return {'sha256': digest(path.read_bytes()), 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'gid': info.st_gid}


def desired_files(all_components=False):
    files = {}
    for source in sorted((ROOT / 'dotfiles').rglob('*')):
        if not source.is_file():
            continue
        rel = source.relative_to(ROOT / 'dotfiles')
        parts = ['.' + p[4:] if p.startswith('dot_') else p for p in rel.parts]
        if rel.parts[0] == 'dot_config':
            target = CONFIG.joinpath(*parts[1:])
            feature = {'nushell': 'nu', 'starship.toml': 'starship', 'uv': 'uv', 'direnv': 'direnv'}.get(parts[1])
        else:
            target = HOME / parts[0]
            feature = 'bash' if rel.parts[0] == 'dot_bash_aliases' else 'zsh'
        if all_components or not feature or feature in COMPONENTS:
            files[str(target)] = source.read_bytes()
    files[str(CONFIG / 'devshell/components')] = (' '.join(COMPONENTS) + '\n').encode()
    return files


def registry():
    safe_path(STATE / 'current.json')
    path = STATE / 'current.json'
    return json.loads(path.read_text()) if path.exists() else {}


def dependencies(exclude=()):
    columns = {'apt': 2, 'dnf': 3, 'pacman': 4, 'zypper': 5}
    adapter = os.environ['DEVSHELL_ADAPTER']
    packages, missing, manual_only = [], [], []
    for line in (ROOT / 'manifests/packages.tsv').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        row = line.split()
        if row[0] not in COMPONENTS or row[0] in exclude:
            continue
        commands = {'fd': ['fd', 'fdfind'], 'bat': ['bat', 'batcat']}.get(row[0], [row[1]])
        if not any(shutil.which(cmd) for cmd in commands):
            missing.append(row[0])
            package = row[columns[adapter]] if adapter in columns else '-'
            if package != '-':
                packages.append(package)
            else:
                manual_only.append(row[0])
    prefix = {'apt': ['apt-get', 'install', '--'], 'dnf': ['dnf', 'install', '--'],
              'pacman': ['pacman', '-S', '--needed', '--'], 'zypper': ['zypper', 'install', '--']}
    optional_missing = ['duckdb'] if 'duckdb' in COMPONENTS and not shutil.which('duckdb') else []
    return {'missing': missing, 'manual_only': manual_only, 'optional_missing': optional_missing,
            'manual_system_command': prefix.get(adapter, []) + sorted(set(packages)) if packages else [],
            'note': 'Comando administrativo para revisão; setup só executa após confirmação separada. Disponibilidade varia por versão.'}


def build_plan():
    managed = registry()
    entries = []
    for target, content in desired_files().items():
        before = snapshot(Path(target))
        after = digest(content)
        action = 'unchanged' if before and before['sha256'] == after else 'write'
        conflict = bool(before and action == 'write' and managed.get(target) != before['sha256'])
        entries.append({'path': target, 'before': before, 'after': after, 'action': action, 'conflict': conflict, 'managed': target in managed})
    result = {'operation': 'configuration', 'profiles': os.environ['DEVSHELL_PROFILES'].split(','),
              'components': COMPONENTS, 'files': entries,
              'platform': {'distro': os.environ['DEVSHELL_DISTRO'], 'adapter': os.environ['DEVSHELL_ADAPTER'],
                           'arch': os.environ['DEVSHELL_MACHINE'], 'libc': os.environ['DEVSHELL_LIBC'],
                           'supported_arch': os.environ['DEVSHELL_MACHINE'] in ('x86_64', 'aarch64')},
              'dependencies': dependencies()}
    # Inclui a implementação e os manifestos: uma edição invalida a aprovação.
    sources = [p for folder in ('bin', 'lib', 'profiles', 'manifests') for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    result['source_sha256'] = digest(b''.join(str(p.relative_to(ROOT)).encode() + p.read_bytes() for p in sorted(sources)))
    result['approval'] = digest(encode(result))
    return result


def report(data):
    if os.environ['DEVSHELL_JSON'] == '1':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print('Data Lab Dotfiles —', data.get('operation', 'relatório'))
    if 'approval' in data:
        print('Aprovação:', data['approval'])
    if 'platform' in data:
        print('Plataforma:', ', '.join(f'{k}={v}' for k, v in data['platform'].items()))
    if 'components' in data:
        print('Componentes:', ', '.join(data['components']))
    for entry in data.get('files', []):
        print(f"  {entry['action']}: {entry['path']}" + (' [conflito]' if entry.get('conflict') else ''))
    deps = data.get('dependencies', {})
    if deps.get('missing'):
        print('Ausentes:', ', '.join(deps['missing']))
    if deps.get('optional_missing'):
        print('Opcionais ausentes:', ', '.join(deps['optional_missing']))
    if deps.get('manual_system_command'):
        import shlex
        print('Revisão administrativa (manual):', shlex.join(deps['manual_system_command']))
    for issue in data.get('issues', []):
        print('Diagnóstico:', issue)
    for warning in data.get('warnings', []):
        print('Aviso:', warning)
    for key in ('transaction', 'changed', 'restored', 'message'):
        if key in data:
            print(f'{key}: {data[key]}')


def atomic(path, content, metadata=None, restore_stat=None, mode=0o600):
    safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    safe_path(path.parent)
    fd, name = tempfile.mkstemp(prefix='.devshell-', dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if restore_stat:
            shutil.copystat(restore_stat, temp)
        if metadata:
            os.chown(temp, metadata['uid'], metadata['gid'])
        os.chmod(temp, metadata['mode'] if metadata else mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


@contextlib.contextmanager
def locked():
    safe_path(STATE / 'lock')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE / 'lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('outra operação está em andamento') from exc
        yield


def chezmoi_render():
    executable = shutil.which('chezmoi')
    if not executable:
        raise RuntimeError('Chezmoi ausente: use install --component chezmoi ou instalação manual')
    # Fonte exclusivamente estática: nenhum script, template ou external é aceito.
    if (ROOT / '.chezmoiroot').read_text().strip() != 'dotfiles':
        raise ValueError('.chezmoiroot deve apontar para dotfiles')
    for source in (ROOT / 'dotfiles').rglob('*'):
        if source.is_symlink() or (source.is_file() and (source.name.startswith('.') or source.name.startswith('run_') or source.suffix == '.tmpl')):
            raise ValueError(f'fonte Chezmoi não estática recusada: {source}')
    with tempfile.TemporaryDirectory(prefix='devshell-render-') as temp:
        sandbox = Path(temp)
        destination = sandbox / 'home'
        destination.mkdir()
        env = os.environ | {'HOME': str(destination), 'XDG_CONFIG_HOME': str(destination / '.config'),
                           'XDG_CACHE_HOME': str(sandbox / 'cache'), 'XDG_DATA_HOME': str(sandbox / 'data'),
                           'XDG_STATE_HOME': str(sandbox / 'state')}
        subprocess.run([executable, '--source', str(ROOT), '--destination', str(destination),
                        '--config', '/dev/null', '--config-format', 'toml',
                        '--persistent-state', str(sandbox / 'state.db'), '--cache', str(sandbox / 'cache'),
                        '--no-tty', '--force', 'apply'], env=env, check=True, stdout=subprocess.DEVNULL)
        for target, content in desired_files().items():
            path = Path(target)
            if path == CONFIG / 'devshell/components':
                continue
            relative = Path('.config') / path.relative_to(CONFIG) if path.is_relative_to(CONFIG) else path.relative_to(HOME)
            rendered = destination / relative
            if rendered.is_symlink() or rendered.read_bytes() != content:
                raise RuntimeError(f'renderização Chezmoi divergiu: {target}')


def latest_transaction():
    safe_path(STATE / 'latest')
    pointer = STATE / 'latest'
    if not pointer.exists():
        return None, None
    name = pointer.read_text().strip()
    if not name or any(c not in '0123456789abcdef' for c in name) or len(name) != 32:
        raise ValueError('identificador de transação inválido')
    directory = STATE / 'transactions' / name
    safe_path(directory / 'manifest.json')
    return directory, json.loads((directory / 'manifest.json').read_text())


def restore_entry(directory, entry):
    path = Path(entry['path'])
    if entry['before'] is None:
        safe_path(path)
        path.unlink(missing_ok=True)
    else:
        backup = directory / entry['backup']
        safe_path(backup)
        saved = snapshot(backup)
        if not saved or saved['sha256'] != entry['before']['sha256']:
            raise RuntimeError(f'backup corrompido: {path}')
        atomic(path, backup.read_bytes(), entry['before'], backup)


def apply_configuration():
    plan = build_plan()
    if os.environ['DEVSHELL_APPROVAL'] != plan['approval']:
        raise ValueError('aprovação não corresponde ao plano atual; execute plan novamente')
    if any(e['conflict'] for e in plan['files']) and os.environ['DEVSHELL_REPLACE'] != '1':
        raise ValueError('dotfiles existentes em conflito: revise diff e use --replace-existing explicitamente')
    changed = [entry for entry in plan['files'] if entry['action'] == 'write']
    if not changed:
        _, transaction = latest_transaction()
        if transaction and transaction['status'] in ('pending', 'rolling-back'):
            raise RuntimeError('transação interrompida: execute rollback antes de aplicar')
        report({'operation': 'apply', 'changed': 0, 'message': 'Configuração já corresponde ao plano.'})
        return
    chezmoi_render()
    with locked():
        if build_plan()['approval'] != plan['approval']:
            raise RuntimeError('o ambiente mudou durante a revisão; planeje novamente')
        old_dir, old_tx = latest_transaction()
        if old_tx and old_tx['status'] in ('pending', 'rolling-back'):
            raise RuntimeError('transação interrompida: execute rollback antes de aplicar')
        import uuid
        name = uuid.uuid4().hex
        directory = STATE / 'transactions' / name
        directory.mkdir(parents=True, mode=0o700)
        tx = {'status': 'pending', 'files': changed, 'previous_registry': registry(),
              'previous_latest': old_dir.name if old_dir else None}
        contents = desired_files()
        for index, entry in enumerate(changed):
            entry['backup'] = str(index)
            if entry['before']:
                shutil.copy2(entry['path'], directory / str(index))
        atomic(directory / 'manifest.json', encode(tx))
        atomic(STATE / 'latest', name.encode())
        written = []
        try:
            for entry in changed:
                if snapshot(Path(entry['path'])) != entry['before']:
                    raise RuntimeError('alvo alterado durante a aplicação')
                atomic(Path(entry['path']), contents[entry['path']], entry['before'])
                written.append(entry)
                entry['applied'] = snapshot(Path(entry['path']))
                atomic(directory / 'manifest.json', encode(tx))
            current = tx['previous_registry'] | {entry['path']: entry['after'] for entry in changed}
            atomic(STATE / 'current.json', encode(current))
            tx['status'] = 'committed'
            atomic(directory / 'manifest.json', encode(tx))
        except BaseException:
            for entry in reversed(written):
                restore_entry(directory, entry)
            atomic(STATE / 'current.json', encode(tx['previous_registry']))
            if tx['previous_latest']:
                atomic(STATE / 'latest', tx['previous_latest'].encode())
            else:
                (STATE / 'latest').unlink()
            tx['status'] = 'failed-restored'
            atomic(directory / 'manifest.json', encode(tx))
            raise
    report({'operation': 'apply', 'transaction': name, 'changed': len(changed)})


def rollback_plan():
    directory, tx = latest_transaction()
    if not tx:
        return {'operation': 'rollback', 'files': [], 'message': 'Nenhuma transação para restaurar.'}, directory, tx
    allowed = desired_files(all_components=True)
    entries = []
    for entry in tx['files']:
        if entry['path'] not in allowed or not entry['backup'].isdigit():
            raise ValueError('manifesto de rollback fora do escopo gerenciado')
        before = snapshot(Path(entry['path']))
        after_hash = before['sha256'] if before else None
        matches_applied = before == entry['applied'] if 'applied' in entry else after_hash == entry['after']
        if not matches_applied and not (tx['status'] in ('pending', 'rolling-back') and before == entry['before']):
            raise RuntimeError(f"arquivo editado após aplicação: {entry['path']}; preserve/mescle manualmente")
        if entry['before']:
            backup = directory / entry['backup']
            saved = snapshot(backup)
            if not saved or saved['sha256'] != entry['before']['sha256']:
                raise RuntimeError('backup ausente ou corrompido')
        entries.append({'path': entry['path'], 'before': before, 'action': 'restore',
                        'after': entry['before']['sha256'] if entry['before'] else None})
    data = {'operation': 'rollback', 'transaction': directory.name, 'files': entries}
    data['approval'] = digest(encode(data) + encode(tx))
    return data, directory, tx


def rollback():
    plan, directory, tx = rollback_plan()
    if not os.environ['DEVSHELL_APPROVAL']:
        report(plan)
        return
    if not tx or os.environ['DEVSHELL_APPROVAL'] != plan['approval']:
        raise ValueError('aprovação de rollback inválida; execute rollback sem aprovação primeiro')
    with locked():
        if rollback_plan()[0]['approval'] != plan['approval']:
            raise RuntimeError('estado mudou antes do rollback')
        tx['status'] = 'rolling-back'
        atomic(directory / 'manifest.json', encode(tx))
        reviewed = {entry['path']: entry['before'] for entry in plan['files']}
        for entry in reversed(tx['files']):
            current = snapshot(Path(entry['path']))
            if current != reviewed[entry['path']]:
                raise RuntimeError(f"alvo alterado durante rollback: {entry['path']}")
            if current != entry['before']:
                restore_entry(directory, entry)
        atomic(STATE / 'current.json', encode(tx['previous_registry']))
        if tx['previous_latest']:
            atomic(STATE / 'latest', tx['previous_latest'].encode())
        else:
            (STATE / 'latest').unlink()
        tx['status'] = 'rolled-back'
        atomic(directory / 'manifest.json', encode(tx))
    report({'operation': 'rollback', 'restored': len(tx['files'])})


VERSION_FLOORS = {'uv': (0, 9, 0), 'chezmoi': (2, 62, 0), 'zsh': (5, 9, 0), 'nu': (0, 116, 1)}


def command_version(tool):
    executable = shutil.which(tool)
    if not executable:
        raise ValueError(f'componente ausente: {tool}')
    with tempfile.TemporaryDirectory(prefix='devshell-version-') as temporary:
        env = {key: value for key, value in os.environ.items() if not key.startswith('UV_')}
        env.update({'HOME': temporary, 'XDG_CONFIG_HOME': temporary + '/config', 'XDG_DATA_HOME': temporary + '/data',
                    'XDG_STATE_HOME': temporary + '/state', 'XDG_CACHE_HOME': temporary + '/cache'})
        result = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=10, env=env)
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', result.stdout)
    if result.returncode or not match:
        raise ValueError(f'não foi possível identificar versão: {tool}')
    return tuple(int(value or 0) for value in match.groups())


def version_issues():
    versions, issues = {}, []
    for tool, floor in VERSION_FLOORS.items():
        if tool not in COMPONENTS or not shutil.which(tool):
            continue
        try:
            version = command_version(tool)
            versions[tool] = '.'.join(map(str, version))
            if version < floor:
                issues.append(f'versão incompatível: {tool}; requer >= ' + '.'.join(map(str, floor)))
        except ValueError as exc:
            issues.append(str(exc))
        except (OSError, subprocess.TimeoutExpired):
            issues.append(f'falha ao consultar versão: {tool}')
    return versions, issues


def main():
    command = sys.argv[1]
    if command == 'update' and not os.environ['DEVSHELL_APPROVAL']:
        command = 'plan'
    if command in ('plan', 'status', 'diff', 'doctor'):
        plan = build_plan()
        plan['operation'] = command
        if command == 'diff' and os.environ['DEVSHELL_JSON'] != '1':
            for target, content in desired_files().items():
                path = Path(target)
                before = path.read_text() if path.exists() else ''
                print(''.join(difflib.unified_diff(before.splitlines(True), content.decode().splitlines(True), fromfile=target, tofile=target + ' (proposto)')), end='')
            return
        if command == 'doctor':
            plan['issues'] = [f'componente ausente: {item}' for item in plan['dependencies']['missing']]
            known = registry()
            plan['warnings'] = [f'arquivo idêntico não registrado: {entry["path"]}' for entry in plan['files']
                                if entry['before'] and not entry['managed'] and entry['action'] == 'unchanged']
            if 'duckdb' in plan['dependencies']['optional_missing']:
                plan['warnings'].append('DuckDB opcional ausente: instale a CLI separadamente se desejar')
            elif 'duckdb' in COMPONENTS:
                try:
                    executable = Path(shutil.which('duckdb'))
                    safe_path(executable.parent)
                    safe_path(executable.resolve(strict=True))
                except (ValueError, OSError) as exc:
                    plan['warnings'].append(f'DuckDB detectado em caminho inseguro: {exc}')
            plan['issues'].extend(f'arquivo esperado ausente: {entry["path"]}' for entry in plan['files'] if not entry['before'])
            plan['issues'].extend(f'arquivo gerenciado divergente: {entry["path"]}' for entry in plan['files']
                                  if entry['managed'] and (not entry['before'] or entry['before']['sha256'] != known[entry['path']]))
            plan['issues'].extend(f'arquivo esperado não corresponde ao perfil: {entry["path"]}' for entry in plan['files']
                                  if entry['before'] and entry['action'] == 'write')
            import artifacts
            plan['issues'].extend(artifacts.health_issues())
            if not plan['platform']['supported_arch']:
                plan['issues'].append('arquitetura sem artefatos controlados')
            if plan['platform']['adapter'] == 'manual':
                plan['issues'].append('distribuição sem adaptador: instalar pré-requisitos manualmente')
            if os.environ.get('UV_PROJECT_ENVIRONMENT'):
                plan['issues'].append('UV_PROJECT_ENVIRONMENT global detectado: revise para preservar .venv por projeto')
            plan['versions'], issues = version_issues()
            plan['issues'].extend(issues)
            _, transaction = latest_transaction()
            if transaction and transaction['status'] in ('pending', 'rolling-back'):
                plan['issues'].append('transação interrompida: revise rollback')
            report(plan)
            return 3 if plan['issues'] else 0
        report(plan)
    elif command in ('apply', 'update'):
        if not os.environ['DEVSHELL_APPROVAL']:
            raise ValueError('use plan e depois --approve HASH para aplicar')
        apply_configuration()
    elif command == 'rollback':
        rollback()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
