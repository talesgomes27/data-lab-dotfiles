#!/usr/bin/env python3
"""Relatórios e fronteira de escrita de arquivos; somente biblioteca padrão."""
import contextlib
from datetime import UTC, datetime
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

# -I exclui o diretório do script; doctor importa artifacts desta mesma lib.
sys.path.insert(0, str(Path(__file__).resolve().parent))
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
COMPONENTS = os.environ.get('DEVSHELL_COMPONENTS', '').split()
PROFILE_LIST = re.compile(r'[a-z]+(,[a-z]+)*')


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
            if info.st_mode & 0o022 and not (stat.S_ISDIR(info.st_mode) and info.st_uid in (0, system_uid) and info.st_mode & stat.S_ISVTX):
                yield {'path': str(part), 'kind': 'permissions', 'message': f'permissões inseguras: {part}'}


def safe_path(path):
    for issue in path_issues(path):
        raise ValueError(issue['message'])


def drop_group_write_tree(root):
    """Tira escrita de grupo/outros por descritor, conferindo a identidade, sem seguir symlinks (D-018)."""
    def fix(name, dir_fd, directory):
        info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        if not info.st_mode & 0o022 or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            return
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_DIRECTORY if directory else 0)
        descriptor = os.open(name, flags, dir_fd=dir_fd)
        try:
            current = os.fstat(descriptor)
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError(f'item trocado durante o ajuste de modo: {name}')
            os.fchmod(descriptor, stat.S_IMODE(current.st_mode) & ~0o022)
        finally:
            os.close(descriptor)

    for _, directories, files, dir_fd in os.fwalk(root, follow_symlinks=False):
        for name in directories:
            fix(name, dir_fd, True)
        for name in files:
            fix(name, dir_fd, False)


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


def canonical_profiles(text):
    """Sem duplicatas e sem o minimal implícito, na ordem informada (D-014)."""
    names = []
    for name in text.split(','):
        if name != 'minimal' and name not in names:
            names.append(name)
    return ','.join(names) or 'minimal'


def valid_profiles(text):
    return bool(PROFILE_LIST.fullmatch(text)) and all((ROOT / 'profiles' / f'{name}.profile').is_file() for name in text.split(','))


def profiles_record():
    return STATE / 'profiles'


def read_profiles_record():
    safe_path(profiles_record())
    return profiles_record().read_text().strip() if profiles_record().exists() else None


def read_own_regular(path):
    """Leitura para escolher perfis: o próprio arquivo é conferido, sem exigir ancestrais seguros."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError(f'arquivo irregular recusado: {path}') from exc
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise ValueError(f'arquivo irregular, de outro dono ou com hardlink recusado: {path}')
        return stream.read().decode()


def restore_profiles(previous):
    safe_path(profiles_record())
    if previous is None:
        profiles_record().unlink(missing_ok=True)
    else:
        atomic(profiles_record(), (previous + '\n').encode())


def profiles_source(informed):
    """Origem e perfis para bin/devshell, sem gravar nada (D-015)."""
    hint = 'rode ./bin/devshell setup --profile PERFIS uma vez, com os perfis que você aplicou'
    if informed is not None:
        # Caminho inseguro é assunto da revisão de permissões; aqui só um registro ilegível avisa.
        try:
            text = read_profiles_record()
        except (OSError, ValueError):
            text = None
        if text is not None and not valid_profiles(text):
            print(f'devshell: aviso: registro de perfis inválido em {profiles_record()}; o próximo apply o substitui', file=sys.stderr)
        return 'informados', canonical_profiles(informed)
    # A escrita continua exigindo safe_path; aqui só se escolhem nomes validados contra profiles/.
    text = read_own_regular(profiles_record())
    text = text.strip() if text is not None else None
    if text is None:
        components = read_own_regular(CONFIG / 'devshell/components')
        if components is not None:
            minimal = {line.strip() for line in (ROOT / 'profiles/minimal.profile').read_text().splitlines()
                       if line.strip() and not line.startswith('#')}
            if set(components.split()) - minimal:
                raise ValueError(f'nenhum perfil lembrado e a HOME já tem componentes além de minimal; {hint}')
        return 'padrão', 'minimal'
    if not valid_profiles(text):
        raise ValueError(f'registro de perfis inválido em {profiles_record()}; {hint}')
    return 'lembrados', canonical_profiles(text)


def remembered_profiles_check():
    """R-046: perfis lembrados que tirariam componentes já aplicados param antes de qualquer plano."""
    try:
        applied = read_own_regular(CONFIG / 'devshell/components')
    except ValueError:
        return  # Arquivo irregular é assunto do plano, que o recusa com mensagem própria.
    removed = [name for name in (applied or '').split() if name not in COMPONENTS]
    if removed:
        raise ValueError(f"os perfis lembrados ({os.environ['DEVSHELL_PROFILES']}) tirariam componentes já aplicados: "
                         f"{', '.join(removed)}; rode ./bin/devshell setup --profile PERFIS uma vez, com os perfis que você aplicou")


def universe_pairs():
    """D-029: cada alvo possível como (raiz, caminho relativo), pela origem em dotfiles/, sem ler o conteúdo."""
    pairs = [(CONFIG, 'devshell/components')]
    for source in sorted((ROOT / 'dotfiles').rglob('*')):
        if not source.is_file():
            continue
        rel = source.relative_to(ROOT / 'dotfiles')
        parts = ['.' + p[4:] if p.startswith('dot_') else p for p in rel.parts]
        pairs.append((CONFIG, '/'.join(parts[1:])) if rel.parts[0] == 'dot_config' else (HOME, parts[0]))
    return pairs


def foreign_roots(recorded):
    """Raízes de outra HOME ou de outro XDG_CONFIG_HOME no registro, pelo texto exato das chaves, sem stat."""
    pairs = universe_pairs()
    universe = {str(root / relative) for root, relative in pairs}
    roots = set()
    for key in recorded:
        if key in universe:
            continue
        for root, relative in pairs:
            prefix = key[:-len(relative) - 1] if key.endswith('/' + relative) else None
            if prefix is None or prefix == str(root):
                continue
            # Dentro da configuração atual é um arquivo antigo com nome de alvo, não outra raiz.
            inside = [CONFIG] if root == CONFIG else [HOME, CONFIG]
            if any(Path(prefix).is_relative_to(current) for current in inside):
                continue
            roots.add(prefix or '/')
    return sorted(roots)


def state_check():
    """R-047: o estado não pode ser usado por outra HOME ou outro XDG_CONFIG_HOME; nada é gravado."""
    for path in (HOME, CONFIG, STATE):
        if '..' in path.parts:
            raise ValueError(f'caminho inseguro: {path}')
    # Só o próprio arquivo: ancestrais com escrita de grupo são assunto da revisão de permissões (D-015).
    text = read_own_regular(STATE / 'current.json')
    try:
        recorded = json.loads(text) if text is not None else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f'registro inválido: {STATE / "current.json"}') from exc
    if not isinstance(recorded, dict) or not all(isinstance(key, str) for key in recorded):
        raise ValueError(f'registro inválido: {STATE / "current.json"}')
    roots = foreign_roots(recorded)
    if roots:
        raise ValueError(f'o estado em {STATE} pertence a outra configuração (registra arquivos em {", ".join(roots)}); '
                         'rode com a mesma HOME e o mesmo XDG_CONFIG_HOME desse estado, ou use um XDG_STATE_HOME próprio')


SHA256 = re.compile(r'[0-9a-f]{64}')


def valid_registry(data):
    """R-055: objeto com caminhos absolutos em texto e SHA-256 em hexadecimal minúsculo."""
    return isinstance(data, dict) and all(
        isinstance(key, str) and key.startswith('/') and isinstance(value, str) and SHA256.fullmatch(value)
        for key, value in data.items())


def registry():
    safe_path(STATE / 'current.json')
    path = STATE / 'current.json'
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f'registro inválido: {path}') from exc
    if not valid_registry(data):
        raise ValueError(f'registro inválido: {path}; esperado objeto com caminhos absolutos e SHA-256')
    return data


def classify_orphan(target, recorded, universe):
    """R-050: uma ação por órfão, na ordem outside → unsafe → missing → edited → remove, sem lançar exceção."""
    row = {'path': target, 'recorded': recorded}
    # O texto exato da chave decide antes de qualquer acesso ao disco (D-024).
    if target not in universe:
        return row | {'action': 'forget-outside', 'reason': 'fora dos alvos deste checkout; remova manualmente se quiser'}
    path = Path(target)
    issues = list(path_issues(path))
    if issues:
        return row | {'action': 'forget-unsafe', 'reason': issues[0]['message']}
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return row | {'action': 'forget-missing', 'reason': 'arquivo já não existe'}
    except OSError as exc:
        return row | {'action': 'forget-unsafe', 'reason': str(exc)}
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
        return row | {'action': 'forget-unsafe', 'reason': f'não é arquivo regular independente do usuário: {target}'}
    try:
        content = path.read_bytes()
    except OSError as exc:
        return row | {'action': 'forget-unsafe', 'reason': str(exc)}
    if digest(content) != recorded:
        return row | {'action': 'forget-edited', 'reason': 'editado depois do apply; fica intacto'}
    before = {'sha256': digest(content), 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid}
    return row | {'action': 'remove', 'reason': 'fora dos perfis atuais', 'before': before}


def retire_plan(managed, desired):
    """Órfãos: entradas do registro fora dos perfis atuais (Bloco E)."""
    universe = set(desired_files(all_components=True))
    return [classify_orphan(target, managed[target], universe) for target in sorted(managed) if target not in desired]


def zsh_compiled_issues():
    if 'zsh' not in COMPONENTS:
        return []
    sources = [HOME / '.zshenv', *(CONFIG / 'zsh' / name for name in ('.zprofile', '.zshrc', '.zshenv.local'))]
    compiled = [Path(str(path) + '.zwc') for path in sources]
    return [f'arquivo Zsh compilado não permitido: {path}' for path in compiled if path.exists() or path.is_symlink()]


def dependencies(exclude=()):
    columns = {'apt': 2, 'dnf': 3, 'pacman': 4, 'zypper': 5}
    adapter = os.environ['DEVSHELL_ADAPTER']
    packages, missing, manual_only, outside_path = [], [], [], []
    for line in (ROOT / 'manifests/packages.tsv').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        row = line.split()
        if row[0] not in COMPONENTS or row[0] in exclude:
            continue
        commands = {'fd': ['fd', 'fdfind'], 'bat': ['bat', 'batcat']}.get(row[0], [row[1]])
        if not any(shutil.which(cmd) for cmd in commands):
            # R-044: instalado em ~/.local/bin por um setup anterior, mas fora do PATH desta sessão.
            if any(os.access(HOME / '.local/bin' / cmd, os.X_OK) and (HOME / '.local/bin' / cmd).is_file() for cmd in commands):
                outside_path.append(row[0])
                continue
            missing.append(row[0])
            package = row[columns[adapter]] if adapter in columns else '-'
            if package != '-':
                packages.append(package)
            else:
                manual_only.append(row[0])
    prefix = {'apt': ['apt-get', 'install', '--'], 'dnf': ['dnf', 'install', '--'],
              'pacman': ['pacman', '-S', '--needed', '--'], 'zypper': ['zypper', 'install', '--']}
    optional_missing = ['duckdb'] if 'duckdb' in COMPONENTS and not shutil.which('duckdb') else []
    return {'missing': missing, 'manual_only': manual_only, 'optional_missing': optional_missing, 'outside_path': outside_path,
            'manual_system_command': prefix.get(adapter, []) + sorted(set(packages)) if packages else [],
            'note': 'Comando administrativo para revisão; setup só executa após confirmação separada. Disponibilidade varia por versão.'}


def source_sha256():
    sources = [p for folder in ('bin', 'lib', 'profiles', 'manifests') for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return digest(b''.join(str(p.relative_to(ROOT)).encode() + p.read_bytes() for p in sorted(sources)))


def build_plan():
    managed = registry()
    entries = []
    desired = desired_files()
    for target, content in desired.items():
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
              'dependencies': dependencies(),
              # Caminho, ação, motivo e, nos remove, o snapshot: tudo entra na aprovação (R-050).
              'retire': retire_plan(managed, desired)}
    # Inclui a implementação e os manifestos: uma edição invalida a aprovação.
    result['source_sha256'] = source_sha256()
    result['approval'] = digest(encode(result))
    # Fora do hash: o mesmo plano vale com perfis lembrados ou informados (D-015).
    result['profile_source'] = os.environ.get('DEVSHELL_PROFILE_SOURCE', 'informados')
    try:
        recorded = read_own_regular(profiles_record())
    except (OSError, ValueError):
        recorded = None
    result['profiles_recorded'] = recorded is not None and canonical_profiles(recorded.strip()) == canonical_profiles(os.environ['DEVSHELL_PROFILES'])
    return result


def report(data):
    if os.environ['DEVSHELL_JSON'] == '1':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print('Data Lab Dotfiles —', data.get('operation', 'relatório'))
    if 'approval' in data:
        print('Aprovação:', data['approval'])
    if 'profiles' in data and 'profile_source' in data:
        print(f"Perfis: {','.join(data['profiles'])} ({data['profile_source']})")
    if 'profiles_restore' in data:
        print('Perfis lembrados voltam a:', data['profiles_restore'] or '(nenhum registro)')
    if 'platform' in data:
        print('Plataforma:', ', '.join(f'{k}={v}' for k, v in data['platform'].items()))
    if 'components' in data:
        print('Componentes:', ', '.join(data['components']))
    for entry in data.get('files', []):
        print(f"  {entry['action']}: {entry['path']}" + (' [conflito]' if entry.get('conflict') else ''))
    for entry in data.get('retire', []):
        if entry['action'] == 'remove':
            print(f"  remove: {entry['path']}")
        else:
            print(f"  forget: {entry['path']} ({entry['reason']})")
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
    for row in data.get('transactions', []):
        details = [row.get('status'), f"cadeia {row['chain']}" if row.get('chain') is not None else 'fora da cadeia']
        if row.get('action'):
            details.insert(0, row['action'])
        if row.get('files') is not None and not isinstance(row.get('files'), list):
            details.append(f"{row['files']} arquivo(s)")
        if row.get('created'):
            details.append(row['created'])
        if row.get('reason'):
            details.append(row['reason'])
        print(f"  {row['id']}: " + ', '.join(details))
    for row in data.get('cleanup', []):
        print(f"  {row['id']}: resto de poda interrompida em pruning/" + (' (será removido)' if 'items' in row else ''))
    if 'bytes' in data:
        print('Bytes a remover:', data['bytes'])
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


STATIC_NAME = re.compile(r'(dot_)?[A-Za-z0-9][A-Za-z0-9._-]*')
# Prefixos de atributo do Chezmoi; após dot_ o restante do nome é literal.
CHEZMOI_ATTRIBUTE = re.compile(r'(after|before|create|empty|encrypted|exact|executable|external|literal|'
                               r'modify|once|onchange|private|readonly|remove|run|symlink)_')


def static_sources():
    """Lista permitida: nomes literais, opcionalmente dot_; nenhum script, template, atributo ou external."""
    if (ROOT / '.chezmoiroot').read_text().strip() != 'dotfiles':
        raise ValueError('.chezmoiroot deve apontar para dotfiles')
    for source in (ROOT / 'dotfiles').rglob('*'):
        name = source.name
        if (source.is_symlink() or not (source.is_file() or source.is_dir()) or not STATIC_NAME.fullmatch(name)
                or CHEZMOI_ATTRIBUTE.match(name) or name.endswith(('.tmpl', '.literal', '.age', '.asc'))):
            raise ValueError(f'fonte Chezmoi não estática recusada: {source}')


def chezmoi_render():
    executable = shutil.which('chezmoi')
    if not executable:
        raise RuntimeError('Chezmoi ausente: use install --component chezmoi ou instalação manual')
    static_sources()
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


def remove_checked(entry):
    """R-051: remove um órfão pelo descritor do diretório pai, conferindo identidade e conteúdo, sem seguir symlinks."""
    path = Path(entry['path'])
    safe_path(path.parent)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        opened, current = os.fstat(parent), os.lstat(path.parent)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise RuntimeError(f'diretório trocado durante a retirada: {path.parent}')
        info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            raise RuntimeError(f'alvo trocado durante a retirada: {path}')
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, 'rb') as stream:
            seen = os.fstat(stream.fileno())
            if (seen.st_dev, seen.st_ino) != (info.st_dev, info.st_ino) or digest(stream.read()) != entry['before']['sha256']:
                raise RuntimeError(f'alvo alterado durante a retirada: {path}')
        os.unlink(path.name, dir_fd=parent)
    finally:
        os.close(parent)


def apply_configuration():
    plan = build_plan()
    if os.environ['DEVSHELL_APPROVAL'] != plan['approval']:
        raise ValueError('aprovação não corresponde ao plano atual; execute plan novamente')
    if any(e['conflict'] for e in plan['files']) and os.environ['DEVSHELL_REPLACE'] != '1':
        raise ValueError('dotfiles existentes em conflito: revise diff e use --replace-existing explicitamente')
    changed = [entry for entry in plan['files'] if entry['action'] == 'write']
    retired = plan['retire']
    if changed:
        chezmoi_render()
    with locked():
        if build_plan()['approval'] != plan['approval']:
            raise RuntimeError('o ambiente mudou durante a revisão; planeje novamente')
        old_dir, old_tx = latest_transaction()
        if old_tx and old_tx['status'] in ('pending', 'rolling-back'):
            raise RuntimeError('transação interrompida: execute rollback antes de aplicar')
        if not changed and not retired:
            # R-048: decidir e gravar sob o mesmo lock; perfis novos sem arquivos também são uma transação (D-028).
            recorded = read_profiles_record()
            if recorded is not None and canonical_profiles(recorded) == canonical_profiles(os.environ['DEVSHELL_PROFILES']):
                report({'operation': 'apply', 'changed': 0, 'message': 'Configuração já corresponde ao plano; perfis já registrados.'})
                return
        import uuid
        name = uuid.uuid4().hex
        directory = STATE / 'transactions' / name
        # Ler registro e perfis antes do mkdir: recusa aqui não deixa transação vazia.
        # D-026: cada remove entra em files com before, after nulo e backup; os forget-* só no relatório.
        removals = [{'path': row['path'], 'action': 'remove', 'before': row['before'], 'after': None,
                     'conflict': False, 'managed': True} for row in retired if row['action'] == 'remove']
        tx = {'status': 'pending', 'files': changed + removals, 'previous_registry': registry(),
              'previous_latest': old_dir.name if old_dir else None,
              'previous_profiles': read_profiles_record(),
              'forgotten': [row['path'] for row in retired if row['action'] != 'remove'],
              'created': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}
        directory.mkdir(parents=True, mode=0o700)
        contents = desired_files()
        for index, entry in enumerate(tx['files']):
            entry['backup'] = str(index)
        atomic(directory / 'manifest.json', encode(tx))
        atomic(STATE / 'latest', name.encode())
        written = []
        try:
            # Backups dentro do bloco protegido: uma cópia que falha cai no caminho de falha, sem transação vazia.
            for entry in tx['files']:
                if entry['before']:
                    shutil.copy2(entry['path'], directory / entry['backup'])
                    if entry['action'] == 'remove' and digest((directory / entry['backup']).read_bytes()) != entry['before']['sha256']:
                        raise RuntimeError(f"backup divergente de {entry['path']}; nada foi removido")
            for entry in changed:
                if snapshot(Path(entry['path'])) != entry['before']:
                    raise RuntimeError('alvo alterado durante a aplicação')
                atomic(Path(entry['path']), contents[entry['path']], entry['before'])
                written.append(entry)
                entry['applied'] = snapshot(Path(entry['path']))
                atomic(directory / 'manifest.json', encode(tx))
            for entry in removals:
                remove_checked(entry)
                written.append(entry)
                entry['applied'] = None
                atomic(directory / 'manifest.json', encode(tx))
            gone = {row['path'] for row in retired}
            current = {key: value for key, value in tx['previous_registry'].items() if key not in gone} \
                | {entry['path']: entry['after'] for entry in changed}
            atomic(STATE / 'current.json', encode(current))
            restore_profiles(os.environ['DEVSHELL_PROFILES'])
            tx['status'] = 'committed'
            atomic(directory / 'manifest.json', encode(tx))
        except BaseException:
            for entry in reversed(written):
                restore_entry(directory, entry)
            atomic(STATE / 'current.json', encode(tx['previous_registry']))
            restore_profiles(tx['previous_profiles'])
            if tx['previous_latest']:
                atomic(STATE / 'latest', tx['previous_latest'].encode())
            else:
                (STATE / 'latest').unlink()
            tx['status'] = 'failed-restored'
            atomic(directory / 'manifest.json', encode(tx))
            raise
    result = {'operation': 'apply', 'transaction': name, 'changed': len(changed),
              'removed': len(removals), 'forgotten': len(tx['forgotten'])}
    if not changed and not retired:
        result['message'] = f"Configuração já corresponde ao plano; perfis {os.environ['DEVSHELL_PROFILES']} registrados nesta transação."
    report(result)


def rollback_plan():
    directory, tx = latest_transaction()
    if not tx:
        return {'operation': 'rollback', 'files': [], 'message': 'Nenhuma transação para restaurar.'}, directory, tx
    allowed = desired_files(all_components=True)
    entries = []
    for entry in tx['files']:
        if entry['path'] not in allowed or not entry['backup'].isdigit():
            # R-052: um dotfile retirado que saiu do checkout só volta à mão, a partir do backup.
            raise ValueError(f"manifesto de rollback fora do escopo gerenciado: {entry['path']} não é mais alvo deste checkout; "
                             f"o backup está em {directory / str(entry.get('backup', ''))}")
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
    if 'previous_profiles' in tx:
        data['profiles_restore'] = tx['previous_profiles']
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
        restores_profiles = 'previous_profiles' in tx and isinstance(tx['previous_profiles'], (str, type(None)))
        # Falha cedo: um registro de perfis inseguro não pode deixar a transação no meio do caminho.
        # Sem previous_profiles o registro não é tocado, então não precisa bloquear.
        if restores_profiles:
            safe_path(profiles_record())
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
        # D-004: a transação anterior pode ter sido podada; latest nunca aponta para ela.
        previous = tx['previous_latest'] if isinstance(tx['previous_latest'], str) and TRANSACTION_ID.fullmatch(tx['previous_latest']) else None
        warnings = []
        if restores_profiles:
            restore_profiles(tx['previous_profiles'])
        else:
            warnings.append('perfis anteriores desconhecidos; informe --profile no próximo setup')
        if previous and readable_manifest(STATE / 'transactions' / previous):
            atomic(STATE / 'latest', previous.encode())
        else:
            (STATE / 'latest').unlink()
            if tx['previous_latest'] and (STATE / 'transactions' / str(tx['previous_latest'])).exists():
                warnings.append(f"transação anterior {tx['previous_latest']} ilegível: latest removido; veja rollback --list")
        tx['status'] = 'rolled-back'
        atomic(directory / 'manifest.json', encode(tx))
    report({'operation': 'rollback', 'restored': len(tx['files']), 'warnings': warnings})


TRANSACTION_ID = re.compile(r'[0-9a-f]{32}')
TRANSACTION_ITEM = re.compile(r'manifest\.json|[0-9]+')
PRUNABLE = ('committed', 'rolled-back', 'failed-restored')
RECOVERY_HINT = 'consulte "Backups e recuperação" em docs/SECURITY.md'


def readable_manifest(directory):
    try:
        safe_path(directory / 'manifest.json')
        data = json.loads((directory / 'manifest.json').read_text())
    except (OSError, ValueError):
        return None
    optional_text = all(isinstance(data.get(key), (str, type(None))) for key in ('previous_latest', 'created', 'previous_profiles')) if isinstance(data, dict) else False
    return data if optional_text and isinstance(data.get('status'), str) and isinstance(data.get('files'), list) else None


def transaction_entry(directory):
    """Classifica uma entrada de transactions/ sem seguir symlinks e sem lançar exceção."""
    entry = {'id': directory.name, 'status': 'invalida', 'files': None, 'created': None,
             'previous_latest': None, 'reason': None, 'items': [], 'originals': [], 'retired': []}
    try:
        if not TRANSACTION_ID.fullmatch(directory.name):
            entry['reason'] = 'nome fora do padrão de 32 hexadecimais'
        elif directory.is_symlink() or not directory.is_dir():
            entry['reason'] = 'não é diretório regular'
        else:
            safe_path(directory)
            for item in sorted(directory.iterdir()):
                info = item.lstat()
                if not TRANSACTION_ITEM.fullmatch(item.name) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
                    entry['reason'] = f'item inesperado: {item.name}'
                    break
                entry['items'].append([item.name, digest(item.read_bytes()), info.st_size])
            manifest = readable_manifest(directory) if not entry['reason'] else None
            if not entry['reason'] and not manifest:
                entry['reason'] = 'manifest.json ausente ou ilegível'
            elif manifest:
                entry |= {'status': manifest['status'], 'files': len(manifest['files']),
                          'created': manifest.get('created'), 'previous_latest': manifest.get('previous_latest'),
                          # Arquivo preexistente não gerenciado: o original só existe nesta transação.
                          'originals': sorted(item['path'] for item in manifest['files']
                                              if isinstance(item, dict) and item.get('conflict') and item.get('before')),
                          # Arquivo retirado (Bloco E): a transação é a única cópia dele.
                          'retired': sorted(item['path'] for item in manifest['files']
                                            if isinstance(item, dict) and item.get('action') == 'remove')}
    except (OSError, ValueError) as exc:
        entry['reason'] = str(exc)
    return entry


def transaction_entries():
    root = STATE / 'transactions'
    safe_path(root)
    if not root.is_dir():
        return []
    return [transaction_entry(path) for path in sorted(root.iterdir())]


def latest_name():
    pointer = STATE / 'latest'
    safe_path(pointer)
    return pointer.read_text().strip() if pointer.exists() else None


def transaction_chain(entries, latest):
    known = {entry['id']: entry for entry in entries if entry['status'] != 'invalida'}
    chain, name = [], latest
    while name in known and name not in chain:
        chain.append(name)
        name = known[name]['previous_latest']
    return chain


def history():
    entries, latest = transaction_entries(), latest_name()
    chain = transaction_chain(entries, latest)
    rows = [{key: entry[key] for key in ('id', 'status', 'files', 'created', 'reason')}
            | {'chain': chain.index(entry['id']) if entry['id'] in chain else None} for entry in entries]
    rows.sort(key=lambda row: (row['chain'] is None, row['chain'] or 0, row['created'] or '', row['id']))
    leftovers = []
    try:
        safe_path(STATE / 'pruning')
        if (STATE / 'pruning').is_dir():
            leftovers = [{'id': path.name} for path in sorted((STATE / 'pruning').iterdir())]
    except (OSError, ValueError) as exc:
        leftovers = [{'id': 'pruning', 'reason': str(exc)}]
    return {'operation': 'rollback-list', 'latest': latest, 'transactions': rows, 'cleanup': leftovers}


def pruning_leftovers():
    root = STATE / 'pruning'
    safe_path(root)
    if not root.is_dir():
        return []
    leftovers = []
    for path in sorted(root.iterdir()):
        entry = transaction_entry(path)
        # Uma poda interrompida pode ter removido o manifesto antes do diretório.
        if not TRANSACTION_ID.fullmatch(path.name) or path.is_symlink() or not path.is_dir() or (
                entry['reason'] and not entry['reason'].startswith('manifest.json')):
            raise ValueError(f'resto de poda inesperado: {path}; {RECOVERY_HINT}')
        leftovers.append({'id': path.name, 'items': entry['items']})
    return leftovers


def prune_plan(keep):
    entries, latest = transaction_entries(), latest_name()
    for entry in entries:
        if entry['status'] == 'invalida':
            raise ValueError(f"transação inválida {entry['id']}: {entry['reason']}; {RECOVERY_HINT}")
        if entry['status'] in ('pending', 'rolling-back'):
            where = ('é a atual: conclua com rollback' if entry['id'] == latest
                     else 'está na cadeia, mas não é a atual' if entry['id'] in transaction_chain(entries, latest)
                     else 'está fora da cadeia: rollback não a alcança')
            raise ValueError(f"transação {entry['id']} interrompida ({entry['status']}) {where}; {RECOVERY_HINT}")
        if entry['status'] not in PRUNABLE:
            raise ValueError(f"transação {entry['id']} com status desconhecido {entry['status']}; {RECOVERY_HINT}")
    if latest is not None and latest not in {entry['id'] for entry in entries}:
        raise ValueError(f'latest aponta para transação inexistente; {RECOVERY_HINT}')
    chain = transaction_chain(entries, latest)
    kept = chain[:keep]
    rows, warnings = [], []
    if latest is None and entries:
        warnings.append('não há transação atual: todas as transações listadas serão removidas')
    # A primeira transação com arquivos guarda os dotfiles de antes do primeiro apply; as só de perfis (R-048) não.
    first_with_files = next((name for name in reversed(chain)
                             if next((e for e in entries if e['id'] == name), {}).get('files')), None)
    for entry in entries:
        action = 'keep' if entry['id'] in kept else 'delete'
        first = entry['id'] == first_with_files or (entry['id'] not in chain and entry['previous_latest'] is None and entry.get('files'))
        if action == 'delete' and first:
            warnings.append(f"remove a primeira transação ({entry['id']}), que guarda os dotfiles de antes do primeiro apply")
        elif action == 'delete' and entry['originals']:
            warnings.append(f"remove a transação {entry['id']}, única cópia dos originais substituídos: {', '.join(entry['originals'])}")
        if action == 'delete' and entry.get('retired'):
            warnings.append(f"remove a transação {entry['id']}, única cópia dos arquivos retirados: {', '.join(entry['retired'])}")
        rows.append({'id': entry['id'], 'status': entry['status'], 'action': action, 'items': entry['items'],
                     'chain': chain.index(entry['id']) if entry['id'] in chain else None})
    rows.sort(key=lambda row: (row['chain'] is None, row['chain'] or 0, row['id']))
    leftovers = pruning_leftovers()
    total = sum(item[2] for row in rows if row['action'] == 'delete' for item in row['items'])
    total += sum(item[2] for row in leftovers for item in row['items'])
    data = {'operation': 'rollback-prune', 'keep': keep, 'latest': latest, 'transactions': rows,
            'cleanup': leftovers, 'bytes': total, 'warnings': warnings,
            'message': 'Remoção irreversível: os backups removidos não podem ser restaurados.'}
    data['approval'] = digest(encode(data))
    return data


def remove_private_dir(path):
    """Apaga um diretório de arquivos regulares sem seguir symlinks."""
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            for name in os.listdir(descriptor):
                if not stat.S_ISREG(os.stat(name, dir_fd=descriptor, follow_symlinks=False).st_mode):
                    raise ValueError(f'item não regular em {path}: {name}')
                os.unlink(name, dir_fd=descriptor)
        finally:
            os.close(descriptor)
        os.rmdir(path.name, dir_fd=parent)
    finally:
        os.close(parent)


def prune(keep):
    plan = prune_plan(keep)
    if not os.environ['DEVSHELL_APPROVAL']:
        report(plan)
        return
    if os.environ['DEVSHELL_APPROVAL'] != plan['approval']:
        raise ValueError('aprovação de poda inválida; execute rollback --prune --keep N sem aprovação primeiro')
    removed = []
    with locked():
        if prune_plan(keep)['approval'] != plan['approval']:
            raise RuntimeError('estado mudou antes da poda; planeje novamente')
        staging = STATE / 'pruning'
        # Fora da cadeia primeiro; depois a cadeia da mais antiga para a mais nova.
        doomed = [row for row in plan['transactions'] if row['action'] == 'delete']
        doomed.sort(key=lambda row: (row['chain'] is not None, -(row['chain'] or 0)))
        if doomed or plan['cleanup']:
            staging.mkdir(mode=0o700, exist_ok=True)
            safe_path(staging)
        try:
            for row in plan['cleanup']:
                remove_private_dir(staging / row['id'])
            for row in doomed:
                # D-009: a transação sai do journal num passo atômico antes de ser esvaziada.
                os.rename(STATE / 'transactions' / row['id'], staging / row['id'])
                remove_private_dir(staging / row['id'])
                removed.append(row['id'])
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"poda incompleta; removidas: {', '.join(removed) or 'nenhuma'}; restos em {staging}: {exc}") from exc
    report({'operation': 'rollback-prune', 'changed': len(removed), 'message': 'Backups removidos de forma irreversível.'})


VERSION_FLOORS = {'uv': (0, 9, 0), 'chezmoi': (2, 62, 0), 'zsh': (5, 9, 0), 'nu': (0, 116, 1)}


# D-010: o hash obrigatório das ferramentas foi provado a partir do uv 0.13.5.
UV_HASH_FLOOR = (0, 13, 5)


def version_floors():
    return VERSION_FLOORS | ({'uv': UV_HASH_FLOOR} if 'python-tools' in COMPONENTS else {})


def command_version(tool):
    executable = shutil.which(tool)
    if not executable:
        raise ValueError(f'componente ausente: {tool}')
    with tempfile.TemporaryDirectory(prefix='devshell-version-') as temporary:
        env = {key: value for key, value in os.environ.items() if not key.startswith('UV_')}
        env.update({'HOME': temporary, 'XDG_CONFIG_HOME': temporary + '/config', 'XDG_DATA_HOME': temporary + '/data',
                    'XDG_STATE_HOME': temporary + '/state', 'XDG_CACHE_HOME': temporary + '/cache'})
        result = subprocess.run([executable, '--version'], capture_output=True, text=True, timeout=10, env=env, check=False)
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', result.stdout)
    if result.returncode or not match:
        raise ValueError(f'não foi possível identificar versão: {tool}')
    return tuple(int(value or 0) for value in match.groups())


def version_issues():
    versions, issues = {}, []
    for tool, floor in version_floors().items():
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


# D-019: pendências que o setup resolve; o resto é ação manual, inclusive o que não estiver nesta tabela.
SETUP_RESOLVES = ('componente ausente: ', 'arquivo gerenciado fora dos perfis: ', 'arquivo esperado ausente: ', 'arquivo esperado não corresponde ao perfil: ',
                  'arquivo gerenciado divergente: ', 'componente de usuário ausente: ', 'componente não executável: ',
                  'interpretador uv ausente: ', 'ferramenta uv ausente: ', 'ferramenta uv sem-link: ')


def orphan_issues(plan):
    """R-053: cada órfão é uma pendência que o setup resolve na etapa de aplicação."""
    return [f"arquivo gerenciado fora dos perfis: {row['path']} ({row['action']})" for row in plan['retire']]


def next_step(issues, profiles, source):
    """Um próximo passo só: a primeira pendência manual, senão o setup, senão nada."""
    def resolvable(issue):
        return issue.startswith(SETUP_RESOLVES) or 'modos inseguros na venv' in issue
    manual = [issue for issue in issues if not resolvable(issue)]
    if manual:
        return {'kind': 'manual', 'command': None, 'reason': manual[0]}
    if issues:
        # --profile só quando os informados não são os lembrados (R-044); leitura sem gravar nada.
        try:
            remembered = read_own_regular(profiles_record())
        except ValueError:
            remembered = None
        same = remembered is not None and canonical_profiles(remembered.strip()) == canonical_profiles(profiles)
        command = ['./bin/devshell', 'setup'] + (['--profile', profiles] if source == 'informados' and not same else [])
        return {'kind': 'setup', 'command': command, 'reason': issues[0]}
    return None


def main():
    command = sys.argv[1]
    if command == 'profiles-source':
        source, profiles = profiles_source(os.environ.get('DEVSHELL_PROFILE_INFORMED') or None)
        print(source, profiles)
        return 0
    if command == 'state-check':
        state_check()
        return 0
    if command == 'profiles-check':
        remembered_profiles_check()
        return 0
    if command == 'update' and not os.environ['DEVSHELL_APPROVAL']:
        command = 'plan'
    if command in ('plan', 'status', 'diff', 'doctor'):
        plan = build_plan()
        plan['operation'] = command
        if command == 'diff' and os.environ['DEVSHELL_JSON'] != '1':
            print(f"Perfis: {os.environ['DEVSHELL_PROFILES']} ({plan['profile_source']})", file=sys.stderr)
            for target, content in desired_files().items():
                path = Path(target)
                before = path.read_text() if path.exists() else ''
                print(''.join(difflib.unified_diff(before.splitlines(True), content.decode().splitlines(True), fromfile=target, tofile=target + ' (proposto)')), end='')
            for entry in plan['retire']:
                if entry['action'] != 'remove':
                    continue
                try:
                    old = Path(entry['path']).read_bytes().decode()
                except UnicodeDecodeError:
                    print(f"--- {entry['path']}\n+++ {entry['path']} (removido)\n(conteúdo binário)")
                    continue
                print(''.join(difflib.unified_diff(old.splitlines(True), [], fromfile=entry['path'], tofile=entry['path'] + ' (removido)')), end='')
            return
        if command == 'doctor':
            plan['issues'] = [f'componente ausente: {item}' for item in plan['dependencies']['missing']]
            plan['issues'].extend(f'componente fora do PATH: {item} está em {HOME}/.local/bin; abra uma shell nova ou adicione esse diretório ao PATH'
                                  for item in plan['dependencies']['outside_path'])
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
                                  if entry['managed'] and entry['action'] == 'write'
                                  and (not entry['before'] or entry['before']['sha256'] != known[entry['path']]))
            plan['issues'].extend(f'arquivo esperado não corresponde ao perfil: {entry["path"]}' for entry in plan['files']
                                  if entry['before'] and entry['action'] == 'write')
            if 'zsh' in COMPONENTS:
                try:
                    snapshot(CONFIG / 'zsh/.zshenv.local')
                except (ValueError, OSError) as exc:
                    plan['issues'].append(f'extensão Zsh local insegura: {exc}')
            plan['issues'].extend(zsh_compiled_issues())
            plan['issues'].extend(orphan_issues(plan))
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
            plan['next_step'] = next_step(plan['issues'], os.environ['DEVSHELL_PROFILES'], plan['profile_source'])
            report(plan)
            if plan['next_step'] and os.environ['DEVSHELL_JSON'] != '1':
                step = plan['next_step']
                print('Próximo passo: ' + (' '.join(step['command']) if step['command'] else f"resolva manualmente: {step['reason']}"))
            return 3 if plan['issues'] else 0
        report(plan)
    elif command in ('apply', 'update'):
        if not os.environ['DEVSHELL_APPROVAL']:
            raise ValueError('use plan e depois --approve HASH para aplicar')
        apply_configuration()
    elif command == 'rollback':
        mode = os.environ.get('DEVSHELL_ROLLBACK_MODE', '')
        if mode == 'list':
            report(history())
        elif mode == 'prune':
            prune(int(os.environ['DEVSHELL_KEEP']))
        else:
            rollback()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
