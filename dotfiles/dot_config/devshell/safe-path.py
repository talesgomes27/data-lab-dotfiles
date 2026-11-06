"""Inspeção somente leitura de diretórios PATH e ambientes virtuais."""
import os
from pathlib import Path
import stat
import sys


def directory_issues(path):
    issues = []
    if not path.is_absolute() or ':' in str(path) or any(ord(c) < 32 or ord(c) == 127 for c in str(path)):
        return [{'path': str(path), 'kind': 'path', 'message': f'caminho incompatível com PATH: {path!s}'}]
    try:
        if not path.is_dir():
            issues.append({'path': str(path), 'kind': 'missing', 'message': f'diretório ausente ou irregular: {path}'})
        elif path.stat().st_uid != os.getuid():
            issues.append({'path': str(path), 'kind': 'owner', 'message': f'diretório não pertence ao usuário: {path}'})
        system_uid = Path('/').stat().st_uid
        for parent in [path, *path.parents]:
            try:
                info = parent.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode):
                issues.append({'path': str(parent), 'kind': 'symlink', 'message': f'symlink de diretório recusado: {parent}'})
                continue
            if info.st_uid not in (0, system_uid, os.getuid()):
                issues.append({'path': str(parent), 'kind': 'owner', 'message': f'proprietário inesperado: {parent}'})
            if info.st_mode & 0o022 and not (stat.S_ISDIR(info.st_mode) and info.st_uid in (0, system_uid) and info.st_mode & stat.S_ISVTX):
                issues.append({'path': str(parent), 'kind': 'permissions', 'message': f'permissões inseguras {stat.S_IMODE(info.st_mode):04o} (escrita por grupo/outros): {parent}'})
    except OSError as exc:
        issues.append({'path': str(path), 'kind': 'access', 'message': f'não foi possível inspecionar {path}: {exc}'})
    return issues


def inspect_venv(path):
    issues = directory_issues(path)
    config = path.parent / 'pyvenv.cfg'
    try:
        if config.is_symlink() or not config.is_file():
            issues.append({'path': str(config), 'kind': 'config', 'message': f'pyvenv.cfg ausente ou irregular: {config}; prepare a .venv explicitamente se necessário'})
        for name in ('python', 'python3'):
            executable = path / name
            if not executable.is_file() or not os.access(executable, os.X_OK):
                issues.append({'path': str(executable), 'kind': 'python', 'message': f'interpretador ausente ou não executável: {executable}'})
    except OSError as exc:
        issues.append({'path': str(path), 'kind': 'access', 'message': f'não foi possível inspecionar a .venv: {exc}'})
    return {'bin': str(path), 'venv': str(path.parent), 'issues': issues}


def main():
    arguments = sys.argv[1:]
    venv = arguments[:1] == ['--venv']
    if venv:
        arguments = arguments[1:]
    explain = '--explain' in arguments
    for argument in arguments:
        if argument == '--explain':
            continue
        path = Path(os.path.normpath(argument))
        issues = inspect_venv(path)['issues'] if venv else directory_issues(path)
        if not issues:
            print(path)
        elif explain:
            for issue in issues:
                print('devshell: ' + issue['message'], file=sys.stderr)


if __name__ == '__main__':
    main()
