#!/usr/bin/env python3
"""Inspeção do setup e ajuste restrito das permissões explicitamente revisadas."""
import json
import re
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
    paths.update(fs.STATE / name for name in ('current.json', 'latest', 'lock', 'transactions', 'pruning', 'profiles'))
    # D-027: órfãos do universo entram na revisão, para que um ancestral inseguro seja reparado antes da retirada.
    try:
        managed = fs.registry()
    except (OSError, ValueError):
        managed = {}
    universe, desired = fs.desired_files(all_components=True), fs.desired_files()
    for key in managed:
        if key not in universe or key in desired:
            continue
        # Só entra o que o reparo de modos resolve; symlink, dono ou hardlink viram forget-unsafe sem bloquear.
        try:
            kinds = {issue['kind'] for issue in fs.path_issues(Path(key))}
        except OSError:
            continue
        if kinds <= {'permissions'}:
            paths.add(Path(key))
    paths.update(artifacts.BIN / tool for tool in ('uv', 'chezmoi', 'nu', 'pyinit') if tool in fs.COMPONENTS)
    if 'uv' in fs.COMPONENTS:
        paths.add(artifacts.BIN / 'uvx')
    if any(component in fs.COMPONENTS for component in ('plugins', 'firacode', 'pyinit')) or any(not shutil.which(tool) for tool in ('uv', 'chezmoi', 'nu') if tool in fs.COMPONENTS):
        paths.add(artifacts.CACHE / 'artifact')
    if 'python-tools' in fs.COMPONENTS:
        dirs = artifacts.python_dirs(validate=False)
        paths.update(Path(path) for path in dirs.values())
        # Só a raiz e cada venv: o conteúdo tem symlinks e hardlinks normais de uma venv.
        tools = artifacts.DATA / 'devshell/tools'
        paths.add(tools)
        paths.update(tools / tool['name'] for tool in json.loads((fs.ROOT / 'manifests/python.json').read_text())['tools']
                     if re.fullmatch(r'[a-z][a-z0-9-]*', tool['name']))
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
    return sorted([*issues.values(), *venv_mode_issues()], key=lambda issue: (len(Path(issue['path']).parts), issue['path'], issue['kind']))


def venv_mode_issues():
    """D-018: escrita de grupo/outros dentro das venvs do Data Lab; symlinks da venv são ignorados."""
    if 'python-tools' not in fs.COMPONENTS:
        return []
    issues, tools = [], artifacts.DATA / 'devshell/tools'
    for tool in json.loads((fs.ROOT / 'manifests/python.json').read_text())['tools']:
        name = tool['name']
        venv, config = tools / name, tools / name / 'pyvenv.cfg'
        if not re.fullmatch(r'[a-z][a-z0-9-]*', name) or venv.is_symlink() or not venv.is_dir() or config.is_symlink() or not config.is_file():
            continue
        for root, directories, files in os.walk(venv, followlinks=False):
            for entry in [*directories, *files]:
                path = Path(root) / entry
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    continue
                if stat.S_ISLNK(info.st_mode) or not info.st_mode & 0o022:
                    continue
                regular = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                issues.append({'path': str(path), 'kind': 'venv-mode', 'tool': name,
                               'message': f'escrita de grupo/outros na venv {name}: {path}', 'identity': identity(path),
                               'repairable': bool(info.st_uid == os.getuid() and (stat.S_ISDIR(info.st_mode) or regular))})
    return issues


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
        for tool, floor in fs.version_floors().items():
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
    if 'python-tools' in fs.COMPONENTS:
        # R-025: a migração manual aparece antes de qualquer comando administrativo. Com reparos
        # pendentes, só os links são lidos; o restante é reavaliado depois do reparo.
        try:
            spec = artifacts.python_spec()
            if permissions:
                blockers.extend(artifacts.python_tools.link_conflicts(spec, artifacts.python_dirs(validate=False)))
            else:
                blockers.extend(artifacts.python_tools.blockers(spec, artifacts.python_dirs()))
        except (ValueError, OSError) as exc:
            blockers.append(f'ferramentas Python: {exc}')
    return {'operation': 'setup', 'profiles': os.environ['DEVSHELL_PROFILES'].split(','),
            'profile_source': os.environ.get('DEVSHELL_PROFILE_SOURCE', 'informados'),
            'components': fs.COMPONENTS, 'permissions': permissions, 'versions': versions,
            'native_command': deps['manual_system_command'], 'dependencies': deps,
            'user_components': user_components, 'blockers': blockers}


def cli_json(*arguments):
    """Plano de um comando público da CLI, sem gravar estado."""
    command = [str(fs.ROOT / 'bin/devshell'), *arguments, '--profile', os.environ['DEVSHELL_PROFILES'], '--json']
    if os.environ['DEVSHELL_OFFLINE'] == '1':
        command.append('--offline')
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    return (json.loads(result.stdout) if result.returncode == 0 else None), (result.stderr.strip().splitlines() or [''])[-1]


def summary(inspection):
    """D-016: previsão das etapas; cada uma recalcula o próprio plano antes de perguntar."""
    permissions, steps = inspection['permissions'], []

    def unavailable(error):
        return ('reavaliado depois do reparo de permissões', '') if permissions else ('bloqueado', error)

    steps.append({'step': 'permissões', 'status': 'corrigir' if permissions else 'em dia',
                  'detail': f'{len(permissions)} caminho(s)' if permissions else ''})
    native = inspection['native_command']
    steps.append({'step': 'pacotes do sistema', 'status': 'instalar' if native else 'em dia', 'detail': ' '.join(native)})
    for target in inspection['user_components']:
        plan, error = cli_json('install', '--component', target)
        if plan:
            pending_tools = sum(row['state'] != 'conforme' for row in plan.get('tools', []))
            status = 'instalar ou atualizar' if plan['pending'] else 'em dia'
            detail = f'{pending_tools} ferramenta(s) a instalar ou migrar' if pending_tools else ''
        else:
            status, detail = unavailable(error)
        steps.append({'step': f'componente {target}', 'status': status, 'detail': detail})
    plan, error = cli_json('plan')
    if plan:
        writes = sum(entry['action'] == 'write' for entry in plan['files'])
        conflicts = sum(entry['conflict'] for entry in plan['files'])
        removes = sum(row['action'] == 'remove' for row in plan.get('retire', []))
        forgets = len(plan.get('retire', [])) - removes
        detail = f'{writes} arquivo(s) a atualizar, {conflicts} em conflito'
        if removes or forgets:
            detail += f', {removes} a remover, {forgets} só saem do registro'
        status, detail = ('atualizar', detail) if writes or removes or forgets else ('em dia', '')
    else:
        status, detail = unavailable(error)
    steps.append({'step': 'dotfiles', 'status': status, 'detail': detail})
    try:
        recorded = fs.read_own_regular(fs.profiles_record())
    except (OSError, ValueError):
        recorded = None
    remembered = recorded is not None and fs.canonical_profiles(recorded.strip()) == fs.canonical_profiles(os.environ['DEVSHELL_PROFILES'])
    steps.append({'step': 'perfis', 'status': 'em dia' if remembered else 'registrar', 'detail': '' if remembered else os.environ['DEVSHELL_PROFILES']})
    return {'steps': steps, 'blockers': inspection['blockers'],
            'nothing_to_do': not inspection['blockers'] and all(step['status'] == 'em dia' for step in steps)}


def show_summary(data):
    print('Resumo do setup (cada etapa pede a própria confirmação):')
    for step in data['steps']:
        print(f"  {step['step']}: {step['status']}" + (f" ({step['detail']})" if step['detail'] else ''))
    for blocker in data['blockers']:
        print('  bloqueio:', blocker)
    if data['nothing_to_do']:
        print('Nada a fazer: tudo em dia.')


def show(plan):
    if plan['operation'].startswith('install-'):
        artifacts.report_plan(plan)
        return
    if 'summary' in plan:
        show_summary(plan['summary'])
    fs.report(plan)
    if plan['operation'] != 'setup':
        return
    grouped = {}
    for issue in plan['permissions']:
        if issue['kind'] == 'venv-mode':
            grouped.setdefault(issue['tool'], []).append(issue)
    for tool, items in grouped.items():
        examples = ', '.join(Path(item['path']).name for item in items[:2])
        print(f"  venv {tool}: {len(items)} itens com escrita de grupo/outros (ex.: {examples}) [retirar escrita de grupo/outros]")
    for issue in plan['permissions']:
        if issue['kind'] == 'venv-mode':
            continue
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
        data = inspect()
        if sys.argv[2:] == ['--summary']:
            data['summary'] = summary(data)
        print(json.dumps(data, ensure_ascii=False))
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
