#!/usr/bin/env python3
"""Saída completa: resumo das etapas, o que fica e a remoção opcional do estado (Bloco G)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

# -I exclui o diretório do script; somente a lib da CLI é adicionada.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifacts
import state as fs

# D-036: componentes antes da cadeia; o lançador por último entre eles.
COMPONENTS = ('python', 'plugins', 'firacode', 'pyinit', 'devshell')


def cli_json(*arguments):
    """Plano de um comando público da CLI, sem gravar estado."""
    command = [str(fs.ROOT / 'bin/devshell'), *arguments, '--json']
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    return (json.loads(result.stdout) if result.returncode == 0 else None), (result.stderr.strip().splitlines() or [''])[-1]


def summary(purge):
    """R-071: todos os planos antes de qualquer pergunta; qualquer erro é bloqueio, todos listados de uma vez."""
    steps, blockers = [], []
    for component in COMPONENTS:
        plan, error = cli_json('uninstall', '--component', component)
        if plan is None:
            blockers.append(f'uninstall {component}: {error}')
            continue
        removable = sum(item['action'] == 'remove' for item in plan['items'])
        if removable:
            steps.append({'step': f'uninstall {component}', 'component': component, 'count': removable,
                          'detail': f'{removable} item(ns) a remover'})
    chain, error = cli_json('rollback', '--all')
    if chain is None:
        blockers.append(f'rollback --all: {error}')
    elif chain['transactions']:
        count = len(chain['transactions'])
        steps.append({'step': 'rollback --all', 'count': count, 'detail': f'{count} transação(ões) a desfazer'})
    if purge:
        steps.append({'step': 'apagar o estado', 'count': 1,
                      'detail': f'{fs.STATE}, só depois da cadeia inteira desfeita e com a palavra apagar'})
    notes = ['os perfis lembrados voltam ao que eram antes do primeiro apply no rollback --all; '
             'os avisos de reinstalação dos uninstall não valem dentro do leave']
    return {'operation': 'leave', 'steps': steps, 'blockers': blockers, 'notes': notes,
            'nothing_to_do': not steps and not blockers}


def purge_plan():
    """R-074: só depois da cadeia inteira; o plano entra no hash junto com tudo que está no diretório."""
    root = fs.STATE
    result = {'operation': 'leave-purge', 'path': str(root), 'offered': False, 'reason': ''}
    issues = list(fs.path_issues(root))
    if issues:
        return result | {'reason': issues[0]['message']}
    if not root.exists():
        return result | {'reason': 'o diretório de estado não existe'}
    if not root.is_dir():
        return result | {'reason': 'o caminho de estado não é um diretório'}
    if (root / 'latest').exists():
        return result | {'reason': 'ainda há latest: desfaça a cadeia inteira (rollback --all) antes'}
    pending = [entry['id'] for entry in fs.transaction_entries() if entry['status'] in ('pending', 'rolling-back')]
    if pending:
        return result | {'reason': 'há transações interrompidas: ' + ', '.join(pending)}
    listing, total = [], 0
    for current, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(current) / name
            # O arquivo de lock é recriado pelo próprio apagar, sob o lock; fica fora do hash.
            if path == root / 'lock':
                continue
            info = path.lstat()
            listing.append([path.relative_to(root).as_posix(), info.st_mode, info.st_size])
            total += info.st_size if not path.is_dir() else 0
    contents = sorted({row[0].split('/', 1)[0] for row in listing})
    result |= {'offered': True, 'contents': contents, 'bytes': total,
               'message': 'irreversível: as transações e os backups somem; o cache de artefatos fica'}
    result['approval'] = fs.digest(fs.encode(result) + fs.encode(sorted(listing)))
    return result


def purge(planned):
    """Apaga o diretório de estado: renomeia ao lado e só então remove, sem seguir symlinks."""
    if os.environ.get('DEVSHELL_APPROVAL') != planned.get('approval') or not planned.get('offered'):
        raise ValueError('aprovação inválida para apagar o estado; revise o leave de novo')
    with fs.locked():
        current = purge_plan()
        if current.get('approval') != planned['approval']:
            raise RuntimeError('o diretório de estado mudou depois do plano; nada foi apagado')
        if not shutil.rmtree.avoids_symlink_attacks:
            raise RuntimeError('remoção recursiva sem proteção contra symlinks nesta plataforma; apague à mão')
        hidden = fs.STATE.parent / f'.devshell-purge-{uuid.uuid4().hex}'
        os.rename(fs.STATE, hidden)
    shutil.rmtree(hidden)
    return {'operation': 'leave-purge', 'removed': str(fs.STATE)}


def remains():
    """R-072: o que continua na máquina, com o caminho ou o comando para remover à mão."""
    lines = []
    if os.path.lexists(fs.STATE):
        lines.append(f'estado da CLI (transações e backups): {fs.STATE}; para apagar, rode ./bin/devshell leave --purge-state '
                     f'ou remova à mão')
    if os.path.lexists(artifacts.CACHE):
        lines.append(f'cache de artefatos: {artifacts.CACHE}; pode ser removido à mão')
    for component in ('python', 'plugins', 'firacode', 'pyinit', 'devshell'):
        plan, _ = cli_json('uninstall', '--component', component)
        for item in (plan or {}).get('items', []):
            if item['action'] == 'manual':
                lines.append(f"{component}: {item['path']} ({item.get('reason', 'sem prova')})")
    local = fs.CONFIG / 'zsh/.zshenv.local'
    if os.path.lexists(local):
        lines.append(f'extensão pessoal do Zsh: {local}')
    for tool in ('uv', 'chezmoi', 'nu'):
        found = shutil.which(tool)
        if found:
            lines.append(f'{tool}: {found} (a CLI não o remove)')
    lines.append(f"CPython do uv: {artifacts.python_dirs(validate=False)['UV_PYTHON_INSTALL_DIR']} (remova com uv python uninstall)")
    lines.append('pacotes do sistema instalados pelo setup: remova com o gerenciador da distribuição')
    lines.append('diretórios criados pela CLI que ficaram vazios podem ser removidos à mão')
    lines.append('para voltar ao Data Lab: ./bin/devshell setup --profile PERFIS')
    return lines


def main():
    command = sys.argv[1]
    purge_requested = os.environ.get('DEVSHELL_PURGE') == '1'
    if command == 'summary':
        print(json.dumps(summary(purge_requested), ensure_ascii=False))
    elif command == 'show':
        data = json.load(sys.stdin)
        print('Resumo da saída (cada etapa pede a própria confirmação):')
        for step in data['steps']:
            print(f"  {step['step']}: {step['detail']}")
        for note in data.get('notes', []):
            print('  nota:', note)
        for blocker in data['blockers']:
            print('  bloqueio:', blocker)
        if data['nothing_to_do']:
            print('Nada a fazer: o Data Lab já não está aplicado nesta HOME.')
    elif command == 'purge-plan':
        print(json.dumps(purge_plan(), ensure_ascii=False))
    elif command == 'purge':
        planned = json.load(sys.stdin)
        purge(planned)
        print(f'Estado apagado: {fs.STATE}')
    elif command == 'remains':
        print('O que continua na máquina:')
        for line in remains():
            print('  -', line)
    else:
        raise ValueError('comando interno do leave desconhecido')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f'devshell: {exc}', file=sys.stderr)
        sys.exit(2)
