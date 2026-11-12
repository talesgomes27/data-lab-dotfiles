#!/usr/bin/env python3
"""Desinstalação aprovada, só do que a CLI prova que é dela (Bloco F, D-030 a D-034)."""
import csv
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import uuid

# -I exclui o diretório do script; somente a lib da CLI é adicionada.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifacts
import launcher
import python_tools
import state as fs

COMPONENTS = ('python', 'devshell', 'pyinit', 'plugins', 'firacode')
EXCLUDED = ('uv', 'chezmoi', 'nu')
# Nome do componente de install para o nome do componente nos perfis.
PROFILE_COMPONENT = {'python': 'python-tools', 'pyinit': 'pyinit', 'plugins': 'plugins', 'firacode': 'firacode'}
LEFTOVER = re.compile(r'[0-9a-f]{32}')
FIXED_VENV_FILES = {'pyvenv.cfg', 'CACHEDIR.TAG', '.gitignore'}
VENV_LINK = re.compile(r'bin/python[0-9.]*|lib64')
# Nomes que o uv cria na venv; qualquer outro arquivo em bin/ precisa estar no RECORD.
ACTIVATE = re.compile(r'bin/(activate|activate\.(bat|csh|fish|nu|ps1)|activate_this\.py|deactivate\.bat|pydoc\.bat|python[0-9.]*)')


def raise_error(error):
    raise error


def receipts():
    return fs.STATE / 'install-receipts'


def uninstalling():
    # D-033: irmão de devshell/tools, no mesmo sistema de arquivos das venvs (renomear sem EXDEV).
    return artifacts.DATA / 'devshell/uninstalling'


def load_artifacts():
    return json.loads((fs.ROOT / 'manifests/artifacts.json').read_text())['artifacts']


def selected(component):
    machine, libc = os.environ.get('DEVSHELL_MACHINE', ''), os.environ.get('DEVSHELL_LIBC', '')
    return [a for a in load_artifacts() if a['component'] == component
            and a['arch'] in ('any', machine) and a['libc'] in ('any', libc)]


def destination(component):
    return {'plugins': artifacts.DATA / 'devshell/plugins', 'firacode': artifacts.DATA / 'fonts/FiraCodeNerdFont',
            'pyinit': artifacts.BIN}[component]


def item(path, kind, action, reason, **extra):
    return {'path': str(path), 'kind': kind, 'action': action, 'reason': reason} | extra


def file_item(path, expected, proven):
    """Arquivo com prova: remove se o SHA-256 está entre os esperados; inseguro ou diferente é manual."""
    try:
        snap = fs.snapshot(Path(path))
    except (ValueError, OSError) as exc:
        return item(path, 'file', 'manual', str(exc))
    if snap is None:
        return None
    if snap['sha256'] in expected:
        return item(path, 'file', 'remove', proven, before=snap)
    return item(path, 'file', 'manual', 'conteúdo diferente do que a CLI instalou; remova à mão, se quiser')


def read_receipt(component, root):
    """R-062: recibo válido ou None; caminhos relativos ao destino, sem '..'."""
    try:
        text = fs.read_own_regular(receipts() / f'{component}.json')
        data = json.loads(text) if text is not None else None
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict) or data.get('version') != 1 or data.get('component') != component \
            or data.get('destination') != str(root) or not isinstance(data.get('files'), dict):
        return None
    files = {}
    for relative, sha in data['files'].items():
        path = PurePosixPath(relative) if isinstance(relative, str) else None
        if path is None or path.is_absolute() or not path.parts or '..' in path.parts \
                or not isinstance(sha, str) or not fs.SHA256.fullmatch(sha):
            return None
        files[str(root / path)] = sha
    return files


def cached_members(component, root):
    """Membros dos pacotes em cache, conferidos pelo manifesto; o plano nunca baixa (R-060)."""
    expected, complete = {}, True
    for artifact in selected(component):
        cached = artifacts.CACHE / artifact['sha256']
        try:
            fs.safe_path(cached)
            content = cached.read_bytes() if cached.is_file() and not cached.is_symlink() else None
            files = artifacts.members(artifact, content) if content is not None else None
        except (ValueError, OSError):
            files = None
        if files is None:
            complete = False
            continue
        for relative, data in files.items():
            target = root / artifact['name'] / relative if component == 'plugins' else root / relative
            expected[str(target)] = fs.digest(data)
    return expected, complete


def unproven(roots, known):
    """Arquivos nas pastas do componente sem prova: ficam como manual (fontes do usuário, por exemplo)."""
    rows = []
    for root in roots:
        if os.path.islink(root):
            rows.append(item(root, 'dir', 'manual', 'diretório é symlink; revise à mão'))
            continue
        if not os.path.isdir(root):
            continue
        try:
            for current, directories, files in os.walk(root, followlinks=False, onerror=raise_error):
                names = files + [name for name in directories if os.path.islink(os.path.join(current, name))]
                for name in sorted(names):
                    path = os.path.join(current, name)
                    if path not in known:
                        rows.append(item(path, 'file', 'manual', 'sem prova de que foi instalado pela CLI'))
        except OSError as exc:
            rows.append(item(root, 'dir', 'manual', f'não foi possível ler tudo: {exc}'))
    return rows


def plan_artifact_files(component):
    root = destination(component)
    if component == 'pyinit':
        target = root / 'pyinit'
        expected = {artifact['sha256'] for artifact in selected('pyinit')}
        expected |= set((read_receipt('pyinit', root) or {}).values())
        found = file_item(target, expected, 'igual ao manifesto ou ao recibo do install')
        return [found] if found else []
    receipt = read_receipt(component, root)
    expected = receipt if receipt is not None else cached_members(component, root)[0]
    proof = 'igual ao recibo do install' if receipt is not None else 'igual ao pacote em cache, conferido pelo manifesto'
    rows = [row for path, sha in sorted(expected.items()) if (row := file_item(path, {sha}, proof))]
    roots = [root / artifact['name'] for artifact in selected('plugins')] if component == 'plugins' else [root]
    return rows + unproven(roots, set(expected))


def plan_devshell():
    rows = []
    for path, (content, mode) in launcher.contents().items():
        try:
            snap = fs.snapshot(path)
        except (ValueError, OSError) as exc:
            rows.append(item(path, 'file', 'manual', str(exc)))
            continue
        if snap is None:
            continue
        if snap['sha256'] == fs.digest(content) and snap['mode'] == mode:
            rows.append(item(path, 'file', 'remove', 'igual ao que a CLI gera para este checkout', before=snap))
        else:
            rows.append(item(path, 'file', 'manual', 'diferente do que a CLI gera para este checkout'))
    # O original de um install com --replace-existing não volta sozinho: pode estar desatualizado.
    backups = launcher.BACKUPS
    if os.path.isdir(backups) and not os.path.islink(backups):
        for directory in sorted(Path(backups).iterdir()):
            try:
                audit = json.loads(fs.read_own_regular(directory / 'manifest.json') or '{}')
            except (ValueError, OSError):
                continue
            for entry in (audit.get('plan') or {}).get('files', []):
                if isinstance(entry, dict) and entry.get('path') == str(launcher.TARGET) and entry.get('before') \
                        and str(entry.get('backup', '')).isdigit() and (directory / entry['backup']).is_file():
                    original = directory / entry['backup']
                    rows.append(item(original, 'backup', 'manual',
                                     f'original de {launcher.TARGET} substituído com --replace-existing; '
                                     f'para restaurar: cp {original} {launcher.TARGET}'))
    return rows


def inventory(venv, lock):
    """D-033: cada arquivo da venv está no RECORD de uma distribuição do lock, com hash certo, ou na lista fixa."""
    venv = Path(venv)
    sites = sorted(venv.glob('lib/python3.*/site-packages'))
    if len(sites) != 1 or sites[0].is_symlink():
        return False, 'site-packages ausente ou ambíguo', None
    site = sites[0]
    recorded = {}
    for info in sorted(site.glob('*.dist-info')):
        try:
            metadata = (info / 'METADATA').read_text()
            name = re.search(r'^Name:\s*(\S+)', metadata, re.M)
            with (info / 'RECORD').open(newline='') as stream:
                rows = [row for row in csv.reader(stream) if row]
        except (OSError, UnicodeDecodeError, csv.Error):
            return False, f'metadados ilegíveis: {info.name}', None
        if not name or python_tools.normalize(name.group(1)) not in lock['requirements']:
            return False, f'distribuição fora do lock: {info.name}', None
        for row in rows:
            relative = os.path.normpath(os.path.join(site.relative_to(venv).as_posix(), row[0]))
            if relative.startswith('..') or os.path.isabs(relative):
                return False, f'RECORD aponta para fora da venv: {row[0]}', None
            recorded[relative] = row[1] if len(row) > 1 else ''
    entries = []
    try:
        walked = list(os.walk(venv, followlinks=False, onerror=raise_error))
    except OSError as exc:
        # Um subdiretório ilegível não pode passar como inventário completo.
        return False, f'não foi possível ler toda a venv: {exc}', None
    for current, directories, files in walked:
        names = files + [name for name in directories if os.path.islink(os.path.join(current, name))]
        for name in sorted(names):
            path = Path(current) / name
            relative = path.relative_to(venv).as_posix()
            if path.is_symlink():
                if not VENV_LINK.fullmatch(relative):
                    return False, f'symlink inesperado na venv: {relative}', None
                entries.append((relative, 'link:' + os.readlink(path)))
                continue
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                return False, f'entrada que não é arquivo regular: {relative}', None
            content = path.read_bytes()
            if relative in FIXED_VENV_FILES or ACTIVATE.fullmatch(relative):
                entries.append((relative, fs.digest(content)))
                continue
            if relative in recorded:
                if recorded[relative] and python_tools.record_hash(content) != recorded[relative]:
                    return False, f'arquivo alterado depois da instalação: {relative}', None
                entries.append((relative, fs.digest(content)))
                continue
            if path.parent.name == '__pycache__' and path.suffix == '.pyc':
                source = (path.parent.parent / (path.name.split('.')[0] + '.py')).relative_to(venv).as_posix()
                if source in recorded:
                    entries.append((relative, fs.digest(content)))
                    continue
            return False, f'arquivo fora do lock na venv: {relative}; remova à mão ou mova antes', None
    return True, 'inventário completo contra o lock', fs.digest(fs.encode(sorted(entries)))


def plan_python():
    spec = json.loads((fs.ROOT / 'manifests/python.json').read_text())
    dirs = artifacts.python_dirs()
    rows = []
    locks = python_tools.locks(spec)
    for name, lock in locks.items():
        venv, link = python_tools.paths(name, dirs)
        venv_row = None
        if os.path.lexists(venv):
            if venv.is_symlink():
                venv_row = item(venv, 'venv', 'manual', 'venv é symlink; revise à mão')
            else:
                try:
                    issues = python_tools.venv_issues(name, venv, lock, spec['tool_python'], dirs.get('UV_PYTHON_INSTALL_DIR'))
                except (OSError, ValueError, RuntimeError, csv.Error) as exc:
                    issues = [str(exc)]
                if issues:
                    reason = '; '.join(issues)
                    if any(issue.startswith('permissões inseguras') for issue in issues):
                        reason += '; se for só escrita de grupo, rode ./bin/devshell setup, que corrige os modos'
                    venv_row = item(venv, 'venv', 'manual', reason)
                else:
                    ok, reason, digest = inventory(venv, lock)
                    venv_row = item(venv, 'venv', 'remove' if ok else 'manual', reason, inventory=digest)
            rows.append(venv_row)
        if os.path.lexists(link):
            ours = link.is_symlink() and os.readlink(link) == str(venv / 'bin' / name)
            # O link só sai junto com a venv (ou se ela já não existe): ferramenta de pé nunca fica sem link.
            goes = ours and (venv_row is None or venv_row['action'] == 'remove')
            reason = 'symlink da CLI para a venv' if goes else (
                'a venv fica, então o link também fica' if ours else 'não é o symlink da CLI; revise à mão')
            rows.append(item(link, 'link', 'remove' if goes else 'manual', reason, target=str(venv / 'bin' / name)))
    root = uninstalling()
    if os.path.isdir(root) and not os.path.islink(root):
        for entry in sorted(root.iterdir()):
            good = bool(LEFTOVER.fullmatch(entry.name)) and entry.is_dir() and not entry.is_symlink()
            # Um resto só sai com o mesmo inventário de uma venv: nunca sem prova (venv recusada fica).
            proof = next(((ok, why, digest) for lock in locks.values()
                          for ok, why, digest in [inventory(entry, lock)] if ok), None) if good else None
            if proof:
                rows.append(item(entry, 'leftover', 'remove', 'resto de uma desinstalação interrompida', inventory=proof[2]))
            else:
                rows.append(item(entry, 'leftover', 'manual', 'item em uninstalling/ sem prova; revise à mão'))
    return rows


def warnings(component):
    """R-060: componente que continua nos perfis lembrados volta no próximo setup."""
    found_paths = [name for name in ('XDG_DATA_HOME', 'XDG_BIN_HOME', 'UV_TOOL_BIN_DIR') if os.environ.get(name)]
    notes = []
    if component == 'python' and found_paths:
        notes.append(f"caminhos personalizados ({', '.join(found_paths)}): se mudaram desde o install, "
                     'as venvs e os links antigos não aparecem neste plano')
    return notes + profile_warnings(component)


def profile_warnings(component):
    wanted = PROFILE_COMPONENT.get(component)
    try:
        recorded = (fs.read_own_regular(fs.profiles_record()) or '').strip()
    except (ValueError, OSError):
        recorded = ''
    found = []
    for profile in filter(None, recorded.split(',')):
        source = fs.ROOT / 'profiles' / f'{profile}.profile'
        if wanted and re.fullmatch(r'[a-z]+', profile) and source.is_file() \
                and wanted in source.read_text().split():
            found.append(profile)
    if found:
        return [f"{wanted} está nos perfis lembrados ({', '.join(found)}): o próximo setup o reinstala; "
                'troque de perfil antes, se quiser mantê-lo fora']
    return []


def plan(component):
    if component in EXCLUDED:
        raise ValueError(f'{component} não é desinstalado pela CLI: ela depende dele e ele pode ter vindo de outra fonte (N-014)')
    if component not in COMPONENTS:
        raise ValueError('componente de desinstalação desconhecido; use ' + ', '.join(COMPONENTS))
    if component == 'python':
        rows = plan_python()
    elif component == 'devshell':
        rows = plan_devshell()
    else:
        rows = plan_artifact_files(component)
    result = {'operation': f'uninstall-{component}', 'component': component, 'items': rows,
              'warnings': warnings(component), 'source_sha256': fs.source_sha256()}
    result['approval'] = fs.digest(fs.encode(result))
    return result


def remove_link(row):
    """Remove o symlink da CLI pelo descritor do diretório, conferindo o alvo, sem segui-lo."""
    path = Path(row['path'])
    fs.safe_path(path.parent)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if os.readlink(path.name, dir_fd=parent) != row['target']:
            raise RuntimeError(f'symlink trocado durante a desinstalação: {path}')
        os.unlink(path.name, dir_fd=parent)
    finally:
        os.close(parent)


def remove_tree(path):
    # shutil.rmtree usa descritores e não segue symlinks onde a plataforma permite (D-033).
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError('remoção recursiva sem proteção contra symlinks nesta plataforma; remova à mão')
    if Path(path).is_symlink() or not Path(path).is_dir():
        raise RuntimeError(f'esperado um diretório real: {path}')
    shutil.rmtree(path)


def remove_venv(row, lock):
    """R-063: renomeia para uninstalling/, confere de novo o inventário e só então apaga; se mudou, volta."""
    venv, root = Path(row['path']), uninstalling()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    fs.safe_path(root)
    hidden = root / uuid.uuid4().hex
    os.rename(venv, hidden)
    ok, reason, digest = inventory(hidden, lock)
    if not ok or digest != row['inventory']:
        if not os.path.lexists(venv):
            os.rename(hidden, venv)
            raise RuntimeError(f'venv mudou durante a desinstalação: {venv}; nada foi removido ({reason})')
        rejected = root / f'rejected-{hidden.name}'
        os.rename(hidden, rejected)
        raise RuntimeError(f'venv mudou durante a desinstalação; a versão encontrada ficou em {rejected}')
    remove_tree(hidden)


def prune_directories(component):
    """D-034: de baixo para cima e só dentro das pastas do componente; rmdir nunca apaga conteúdo."""
    if component == 'plugins':
        roots = [destination('plugins') / artifact['name'] for artifact in selected('plugins')]
    elif component == 'firacode':
        roots = [destination('firacode')]
    else:
        return
    for root in roots:
        if any(True for _ in fs.path_issues(root)) or not root.is_dir():
            continue
        for current, _, _ in os.walk(root, topdown=False, followlinks=False):
            try:
                os.rmdir(current)
            except OSError:
                pass


def apply(planned):
    if os.environ.get('DEVSHELL_APPROVAL') != planned['approval']:
        raise ValueError('aprovação inválida: revise uninstall sem --approve primeiro')
    component = planned['component']
    removed = []
    with fs.locked():
        current = plan(component)
        if current['approval'] != planned['approval']:
            raise RuntimeError('o ambiente mudou depois do plano; planeje de novo')
        locks = {}
        if component == 'python':
            locks = python_tools.locks(json.loads((fs.ROOT / 'manifests/python.json').read_text()))
        for row in current['items']:
            if row['action'] != 'remove':
                continue
            if row['kind'] == 'file':
                fs.remove_checked({'path': row['path'], 'before': row['before']})
            elif row['kind'] == 'link':
                remove_link(row)
            elif row['kind'] == 'venv':
                remove_venv(row, locks[Path(row['path']).name])
            elif row['kind'] == 'leftover':
                remove_tree(row['path'])
            removed.append(row['path'])
        prune_directories(component)
        receipt = receipts() / f'{component}.json'
        if component in ('plugins', 'firacode', 'pyinit') and os.path.lexists(receipt):
            fs.safe_path(receipt)
            proven = read_receipt(component, destination(component)) or {}
            kept = {path: sha for path, sha in proven.items() if os.path.lexists(path)}
            if kept:
                # Sobrou algo provado (ficou manual por segurança): o recibo continua valendo só para isso.
                data = json.loads(receipt.read_text())
                root = destination(component)
                data['files'] = {Path(path).relative_to(root).as_posix(): sha for path, sha in sorted(kept.items())}
                fs.atomic(receipt, fs.encode(data), mode=0o600)
            else:
                receipt.unlink()
    if component == 'firacode' and shutil.which('fc-cache'):
        subprocess.run(['fc-cache', '-f', str(destination('firacode'))], check=True, capture_output=True)
    return {'operation': planned['operation'], 'removed': len(removed),
            'items': [row for row in current['items'] if row['action'] == 'manual'],
            'message': f'{len(removed)} item(ns) removido(s). Para desfazer: ./bin/devshell install --component {component}.'}


def report(data):
    if os.environ.get('DEVSHELL_JSON') == '1':
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print('Data Lab Dotfiles —', data['operation'])
    if 'approval' in data:
        print('Aprovação:', data['approval'])
    for row in data.get('items', []):
        print(f"  {row['action']}: {row['path']}" + (f" ({row['reason']})" if row['action'] == 'manual' else ''))
    if not data.get('items') and 'removed' not in data:
        print('  nada instalado pela CLI para este componente')
    for warning in data.get('warnings', []):
        print('Aviso:', warning)
    if data.get('message'):
        print(data['message'])


def main():
    component = os.environ['DEVSHELL_COMPONENT']
    result = plan(component)
    if not os.environ.get('DEVSHELL_APPROVAL'):
        report(result)
        return 0
    report(apply(result))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
