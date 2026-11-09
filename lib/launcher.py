#!/usr/bin/env python3
"""Instalação local, aprovada e auditável do lançador para o checkout."""
import os
from pathlib import Path
import shlex
import sys
import uuid

# -I exclui o diretório do script; somente a lib da CLI é adicionada.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import state as fs

TARGET = fs.HOME / '.local/bin/devshell'
RECEIPT = fs.STATE / 'launcher.json'
BACKUPS = fs.STATE / 'launcher-backups'


def contents():
    cli = str(fs.ROOT / 'bin/devshell')
    if any(ord(char) < 32 or ord(char) == 127 for char in cli):
        raise ValueError('checkout com caracteres de controle recusado')
    launcher = ('#!/bin/sh\n'
                f'devshell_cli={shlex.quote(cli)}\n'
                'if [ ! -f "$devshell_cli" ]; then\n'
                '    printf "%s\\n" "devshell: checkout ausente; reinstale o lancador a partir da nova copia." >&2\n'
                '    exit 3\n'
                'fi\n'
                'exec /bin/bash "$devshell_cli" "$@"\n').encode()
    receipt = fs.encode({'checkout': str(fs.ROOT), 'path': str(TARGET),
                         'sha256': fs.digest(launcher), 'mode': 0o755})
    return {TARGET: (launcher, 0o755), RECEIPT: (receipt, 0o600)}


def build_plan():
    fs.safe_path(BACKUPS / 'manifest.json')
    files = []
    for path, (content, mode) in contents().items():
        before = fs.snapshot(path)
        after = fs.digest(content)
        unchanged = bool(before and before['sha256'] == after and before['mode'] == mode)
        files.append({'path': str(path), 'before': before, 'after': after,
                      'after_mode': mode, 'action': 'unchanged' if unchanged else 'write',
                      'conflict': bool(before and before['sha256'] != after)})
    plan = {'operation': 'install-devshell', 'checkout': str(fs.ROOT), 'files': files,
            'launcher_content': contents()[TARGET][0].decode(), 'backup_root': str(BACKUPS),
            'source_sha256': fs.source_sha256()}
    plan['approval'] = fs.digest(fs.encode(plan))
    return plan


def apply(plan):
    if os.environ['DEVSHELL_APPROVAL'] != plan['approval']:
        raise ValueError('aprovação inválida: revise install --component devshell novamente')
    if any(entry['conflict'] for entry in plan['files']) and os.environ['DEVSHELL_REPLACE'] != '1':
        raise ValueError('lançador/registro preexistente diferente: revise e use --replace-existing para substituir com backup')
    changed = [entry for entry in plan['files'] if entry['action'] == 'write']
    if not changed:
        return {'operation': plan['operation'], 'changed': 0}
    with fs.locked():
        if build_plan()['approval'] != plan['approval']:
            raise ValueError('o ambiente mudou após a revisão; revise a instalação novamente')
        directory = BACKUPS / uuid.uuid4().hex
        record = directory / 'manifest.json'
        audit = {'status': 'pending', 'plan': plan, 'completed': []}
        for index, entry in enumerate(changed):
            entry['backup'] = str(index)
            if entry['before']:
                fs.atomic(directory / str(index), Path(entry['path']).read_bytes())
        fs.atomic(record, fs.encode(audit))
        try:
            for entry in changed:
                path = Path(entry['path'])
                if fs.snapshot(path) != entry['before']:
                    raise ValueError(f'alvo alterado após revisão: {path}')
                content, mode = contents()[path]
                fs.atomic(path, content, mode=mode)
                audit['completed'].append(str(path))
                fs.atomic(record, fs.encode(audit))
            audit['status'] = 'complete'
            fs.atomic(record, fs.encode(audit))
        except BaseException:
            audit['status'] = 'partial'
            try:
                fs.atomic(record, fs.encode(audit))
            except OSError:
                pass
            print(f'Instalação incompleta; confira os backups e o registro: {record}', file=sys.stderr)
            raise
    return {'operation': plan['operation'], 'changed': len(changed), 'record': str(record),
            'message': 'Lançador instalado. Mantenha o checkout neste caminho; rollback de dotfiles o preserva.'}


def health_issues():
    try:
        installed = fs.snapshot(RECEIPT)
        if installed is None:
            return []
        for path, (content, mode) in contents().items():
            current = fs.snapshot(path)
            if not current or current['sha256'] != fs.digest(content) or current['mode'] != mode:
                return [f'lançador devshell ou registro ausente/divergente: {path}; revise install --component devshell']
    except (ValueError, OSError) as exc:
        return [f'lançador devshell inseguro: {exc}']
    return []


def show(plan):
    fs.report(plan)
    if os.environ['DEVSHELL_JSON'] != '1':
        if 'launcher_content' in plan:
            print('Checkout:', plan['checkout'])
            for entry in plan['files']:
                print(f"Modo proposto {entry['after_mode']:04o}: {entry['path']}")
            print('Conteúdo do lançador:\n' + plan['launcher_content'], end='')
            print('Backups privados:', plan['backup_root'])
        if 'record' in plan:
            print('Registro:', plan['record'])


if __name__ == '__main__':
    try:
        plan = build_plan()
        show(apply(plan) if sys.argv[1] == 'apply' else plan)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
