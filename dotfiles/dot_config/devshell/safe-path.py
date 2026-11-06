"""Emite apenas diretórios PATH seguros, incluindo seus ancestrais."""
import os
from pathlib import Path
import stat
import sys

arguments = sys.argv[1:]
venv = arguments[:1] == ['--venv']
if venv:
    arguments = arguments[1:]
for argument in arguments:
    path = Path(argument)
    if not path.is_absolute() or ':' in argument or '\n' in argument or '\r' in argument:
        continue
    path = Path(os.path.normpath(path))
    try:
        valid = path.is_dir() and path.stat().st_uid == os.getuid()
        for parent in [path, *path.parents]:
            info = parent.lstat()
            system_owner = info.st_uid in (0, Path('/').stat().st_uid)
            if parent.is_symlink() or info.st_uid not in (0, Path('/').stat().st_uid, os.getuid()):
                valid = False
            if info.st_mode & 0o022 and not (system_owner and info.st_mode & stat.S_ISVTX):
                valid = False
        if venv:
            config = path.parent / 'pyvenv.cfg'
            valid = valid and config.is_file() and not config.is_symlink()
            valid = valid and all((path / name).is_file() and os.access(path / name, os.X_OK) for name in ('python', 'python3'))
        if valid:
            print(path)
    except OSError:
        continue
