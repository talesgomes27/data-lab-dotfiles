#!/usr/bin/env python3
"""Inspeção do setup e ajuste restrito das permissões explicitamente revisadas."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

# -I exclui o diretório do script; somente a lib da CLI é adicionada.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifacts
import state as fs


def target_paths():
    paths = {Path(path) for path in fs.desired_files()}
    if 'zsh' in fs.COMPONENTS:
        paths.add(fs.CONFIG / 'zsh/.zshenv.local')
    paths.update(fs.STATE / name for name in ('current.json', 'latest', 'lock', 'transactions'))
    paths.update(artifacts.BIN / tool for tool in ('uv', 'chezmoi', 'nu', 'pyinit') if tool in fs.COMPONENTS)
    if 'uv' in fs.COMPONENTS:
        paths.add(artifacts.BIN / 'uvx')
    if any(component in fs.COMPONENTS for component in ('plugins', 'firacode', 'pyinit')) or any(not shutil.which(tool) for tool in ('uv', 'chezmoi', 'nu') if tool in fs.COMPONENTS):
        paths.add(artifacts.CACHE / 'artifact')
    if 'python-tools' in fs.COMPONENTS:
        paths.update(Path(path) for path in artifacts.python_dirs(validate=False).values())
    for component, relative in (('plugins', 'devshell/plugins'), ('firacode', 'fonts/FiraCodeNerdFont')):
        if component not in fs.COMPONENTS:
            continue
        directory = artifacts.DATA / relative
        paths.add(directory)
        # Não atravessar uma raiz redirecionada para enumerar fontes existentes.
        if not any(issue['kind'] == 'symlink' for issue in fs.path_issues(directory)) and directory.is_dir():
            paths.update(directory.rglob('*'))
    return paths


def identity(path):
    info = path.lstat()
    return {'device': info.st_dev, 'inode': info.st_ino, 'mode': info.st_mode,
            'uid': info.st_uid, 'gid': info.st_gid, 'links': info.st_nlink}


def permission_review():
    paths = target_paths()
    issues = {}
    for path in sorted(paths):
        for issue in fs.path_issues(path):
            issues[(issue['path'], issue['kind'])] = issue
        if any(issue['kind'] == 'symlink' for issue in fs.path_issues(path)):
            continue
        if path.exists() and path.is_file():
            if path.stat().st_nlink != 1:
                issues[(str(path), 'hardlink')] = {'path': str(path), 'kind': 'hardlink', 'message': f'hardlink recusado: {path}'}
            if path.stat().st_uid != os.getuid():
                issues[(str(path), 'owner')] = {'path': str(path), 'kind': 'owner', 'message': f'alvo não pertence ao usuário: {path}'}
    roots = [fs.HOME, fs.CONFIG, artifacts.DATA, artifacts.CACHE.parent.parent, fs.STATE.parent]
    if 'python-tools' in fs.COMPONENTS:
        roots.extend(Path(path) for path in artifacts.python_dirs(validate=False).values())
    for issue in issues.values():
        path = Path(issue['path'])
        info = identity(path) if path.exists() or path.is_symlink() else None
        issue['identity'] = info
        issue['repairable'] = bool(
            issue['kind'] == 'permissions' and info and info['uid'] == os.getuid()
            and (stat.S_ISDIR(info['mode']) or (stat.S_ISREG(info['mode']) and info['links'] == 1))
            and any(path.is_relative_to(root) for root in roots if root.is_absolute())
        )
    return sorted(issues.values(), key=lambda issue: (len(Path(issue['path']).parts), issue['path'], issue['kind']))


def repair_permissions(review):
    if any(not issue['repairable'] for issue in review):
        raise ValueError('há caminhos que exigem correção manual; nenhum modo foi alterado')
    if permission_review() != review:
        raise ValueError('o ambiente mudou após a revisão das permissões; execute setup novamente')
    for issue in review:
        repair_permission(issue)


def repair_permission(issue):
    if not issue['repairable']:
        raise ValueError('caminho exige correção manual')
    path = Path(issue['path'])
    fs.safe_path(path.parent)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    if stat.S_ISDIR(issue['identity']['mode']):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        current = {'device': info.st_dev, 'inode': info.st_ino, 'mode': info.st_mode,
                   'uid': info.st_uid, 'gid': info.st_gid, 'links': info.st_nlink}
        if current != issue['identity']:
            raise ValueError(f'caminho mudou após revisão: {path}')
        os.fchmod(fd, stat.S_IMODE(info.st_mode) & ~0o022)
    finally:
        os.close(fd)


def inspect():
    permissions = permission_review()
    deps = fs.dependencies(exclude=('uv', 'chezmoi', 'nu'))
    versions, blockers, user_components = {}, fs.zsh_compiled_issues(), []
    if not permissions:
        for tool, floor in fs.VERSION_FLOORS.items():
            if tool not in fs.COMPONENTS or not shutil.which(tool):
                continue
            try:
                fs.safe_path(Path(shutil.which(tool)).resolve())
                version = fs.command_version(tool)
                versions[tool] = '.'.join(map(str, version))
                if version < floor:
                    blockers.append(f'{tool} incompatível; requer >= ' + '.'.join(map(str, floor)) + '; atualize manualmente')
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                blockers.append(f'não foi possível reutilizar {tool}: {exc}')
    for tool in ('uv', 'chezmoi', 'nu'):
        if tool in fs.COMPONENTS and not shutil.which(tool):
            user_components.append(tool)
    if 'plugins' in fs.COMPONENTS:
        user_components.append('plugins')
    if 'firacode' in fs.COMPONENTS:
        user_components.append('firacode')
    if 'python-tools' in fs.COMPONENTS:
        user_components.append('python')
    if 'pyinit' in fs.COMPONENTS:
        user_components.append('pyinit')
    if deps['manual_only']:
        blockers.append('componentes nativos ausentes sem pacote/adaptador definido: ' + ', '.join(deps['manual_only']))
    return {'operation': 'setup', 'profiles': os.environ['DEVSHELL_PROFILES'].split(','),
            'components': fs.COMPONENTS, 'permissions': permissions, 'versions': versions,
            'native_command': deps['manual_system_command'], 'dependencies': deps,
            'user_components': user_components, 'blockers': blockers}


def show(plan):
    if plan['operation'].startswith('install-'):
        artifacts.report_plan(plan)
        return
    fs.report(plan)
    if plan['operation'] != 'setup':
        return
    for issue in plan['permissions']:
        info = issue['identity']
        change = f"{stat.S_IMODE(info['mode']):04o} -> {stat.S_IMODE(info['mode']) & ~0o022:04o}" if issue['repairable'] else 'correção manual necessária'
        print(f"  {issue['message']} [{change}]")
    for tool, version in plan['versions'].items():
        print(f'Manter {tool} {version}: compatível')
    if plan['user_components']:
        print('Instalar/verificar em espaço de usuário:', ', '.join(plan['user_components']))
    for blocker in plan['blockers']:
        print('Bloqueio:', blocker)


def main():
    command = sys.argv[1]
    if command == 'inspect':
        print(json.dumps(inspect(), ensure_ascii=False))
    elif command == 'repair':
        repair_permissions(json.load(sys.stdin)['permissions'])
    elif command == 'show':
        show(json.load(sys.stdin))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
