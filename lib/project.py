#!/usr/bin/env python3
"""Diagnóstico de .venv e reparo explícito, não recursivo, de permissões."""
import json
import os
from pathlib import Path
import runpy
import stat
import sys
import uuid

# -I exclui diretório atual/PYTHONPATH; somente a lib da CLI é adicionada.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup as guided
import state as fs

VALIDATOR = fs.ROOT / 'dotfiles/dot_config/devshell/safe-path.py'
inspect_venv = runpy.run_path(str(VALIDATOR))['inspect_venv']


def inspect_project(raw_path):
    project = Path(raw_path)
    if '..' in project.parts or any(ord(c) < 32 or ord(c) == 127 for c in str(project)):
        raise ValueError('use um caminho sem componentes .. ou caracteres de controle')
    project = Path(os.path.abspath(project))
    report = inspect_venv(project / '.venv/bin')
    permissions, blockers = [], []
    for issue in report['issues']:
        path = Path(issue['path'])
        if issue['kind'] != 'permissions':
            blockers.append(issue['message'])
            continue
        identity = guided.identity(path)
        repairable = bool(path.is_relative_to(fs.HOME) and stat.S_ISDIR(identity['mode']) and identity['uid'] == os.getuid())
        permissions.append({'path': str(path), 'identity': identity, 'repairable': repairable,
                            'from_mode': f"{stat.S_IMODE(identity['mode']):04o}",
                            'to_mode': f"{stat.S_IMODE(identity['mode']) & ~0o022:04o}"})
        if not repairable:
            blockers.append(f'correção manual necessária (somente diretórios do usuário dentro da HOME são reparáveis): {path}')
    permissions.sort(key=lambda item: (len(Path(item['path']).parts), item['path']))
    if permissions:
        record_issues = list(fs.path_issues(fs.STATE / 'permission-repairs'))
        for issue in record_issues:
            blockers.append(f"registro de permissões inseguro; corrija manualmente ou pelo setup antes do reparo: {issue['message']}")
            for permission in permissions:
                if permission['path'] == issue['path']:
                    permission['repairable'] = False
    plan = {'operation': 'project-permissions', 'project': str(project), 'venv': report['venv'],
            'issues': report['issues'], 'permissions': permissions, 'blockers': blockers,
            'source_sha256': fs.source_sha256(), 'validator_sha256': fs.digest(VALIDATOR.read_bytes())}
    plan['approval'] = fs.digest(fs.encode(plan))
    return plan


def repair(plan):
    if inspect_project(plan['project'])['approval'] != plan['approval']:
        raise ValueError('o ambiente mudou após a revisão; revise o plano novamente')
    if plan['blockers']:
        raise ValueError('há problemas que exigem correção manual; nenhum modo foi alterado')
    if not plan['permissions']:
        return {'operation': 'project-permissions', 'changed': 0, 'message': 'Nenhuma permissão precisa de reparo.'}
    record = fs.STATE / 'permission-repairs' / (uuid.uuid4().hex + '.json')
    fs.safe_path(record)
    with fs.locked():
        if inspect_project(plan['project'])['approval'] != plan['approval']:
            raise ValueError('o ambiente mudou após a revisão; revise o plano novamente')
        audit = {'status': 'pending', 'plan': plan, 'completed': []}
        fs.atomic(record, fs.encode(audit))
        print(f'Registro de permissões: {record}', file=sys.stderr)
        try:
            for issue in plan['permissions']:
                guided.repair_permission(issue)
                audit['completed'].append(issue['path'])
                fs.atomic(record, fs.encode(audit))
            audit['status'] = 'complete'
            fs.atomic(record, fs.encode(audit))
        except (OSError, ValueError, RuntimeError) as exc:
            audit['status'] = 'partial'
            try:
                fs.atomic(record, fs.encode(audit))
            except OSError:
                pass
            raise RuntimeError(f'reparo incompleto; confira o registro {record}: {exc}') from exc
    return {'operation': 'project-permissions', 'changed': len(audit['completed']), 'record': str(record),
            'message': 'Permissões revisadas; execute direnv reload no projeto. Nenhum ambiente foi criado ou sincronizado.'}


def show(plan):
    if os.environ['DEVSHELL_JSON'] == '1':
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if 'issues' not in plan:
        fs.report(plan)
        if 'record' in plan:
            print('Registro:', plan['record'])
        return
    print('Projeto:', plan['project'])
    print('Ambiente:', plan['venv'])
    for issue in plan['issues']:
        print('Diagnóstico:', issue['message'])
    for issue in plan['permissions']:
        print(f"  {issue['from_mode']} -> {issue['to_mode']}: {issue['path']}" + ('' if issue['repairable'] else ' [manual]'))
    for blocker in plan['blockers']:
        print('Bloqueio:', blocker)
    print('Aprovação:', plan['approval'])
    if not plan['issues']:
        print('.venv válida; nenhuma correção necessária.')


def main():
    command = sys.argv[1]
    plan = inspect_project(os.environ['DEVSHELL_PROJECT_PATH'])
    if command == 'doctor':
        show(plan)
        return 3 if plan['issues'] else 0
    if os.environ['DEVSHELL_DRY_RUN'] == '1':
        show(plan)
        return 0
    approval = os.environ['DEVSHELL_APPROVAL']
    if approval:
        if approval != plan['approval']:
            raise ValueError('aprovação inválida: revise project fix-permissions --dry-run')
    else:
        if os.environ['DEVSHELL_JSON'] == '1':
            raise ValueError('--json requer --dry-run ou --approve em fix-permissions')
        show(plan)
        if plan['blockers']:
            raise ValueError('resolva os bloqueios apresentados; nenhum modo foi alterado')
        if plan['permissions']:
            print('Retirar escrita de grupo/outros somente destes diretórios, incluindo os pais apresentados? [s/N] ', end='', file=sys.stderr, flush=True)
            if sys.stdin.readline().strip().lower() not in ('s', 'sim'):
                print('Reparo cancelado; nenhum modo foi alterado.', file=sys.stderr)
                return 1
    show(repair(plan))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
