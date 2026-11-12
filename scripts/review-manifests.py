#!/usr/bin/env python3
"""Revisão assistida de manifestos (Bloco H), ferramenta de mantenedor.

Consulta as fontes oficiais e gera um relatório e um patch em --out. Nunca grava no
checkout nem na HOME, nunca executa nada baixado e não faz parte da CLI dos usuários
(N-007, D-039 a D-042). Uso: python3 -I -B scripts/review-manifests.py [--only GRUPO] [--json]
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ('github', 'plugins', 'python-tools', 'cpython')
GITHUB_COMPONENTS = ('uv', 'chezmoi', 'nu', 'firacode')
ALLOWED_HOSTS = {'github.com', 'api.github.com', 'objects.githubusercontent.com',
                 'release-assets.githubusercontent.com', 'codeload.github.com', 'pypi.org'}
LIMIT = 256 * 1024**2
STABLE = re.compile(r'^v?(\d+(?:\.\d+)+)$')
CHECKSUM_FILE = re.compile(r'(\.sha256|checksums.*\.txt|SHA256SUMS|SHA-256\.txt)$', re.I)
ELF_MACHINE = {'x86_64': 62, 'aarch64': 183}
PLATFORMS = ('x86_64-unknown-linux-gnu', 'aarch64-unknown-linux-gnu', 'x86_64-unknown-linux-musl', 'aarch64-unknown-linux-musl')
RATE_LIMIT = ('limite da API pública do GitHub esgotado; tente mais tarde (o script não usa token, N-024)')


class Blocked(Exception):
    """Saída 2: divergência, artefato inválido, host fora da lista, 404 ou downgrade."""


class Unavailable(Exception):
    """Saída 3: sem rede, limite da API ou sem o uv exigido."""


def check_hop(url):
    """Cada salto, e não só o destino: HTTPS, sem credenciais, host da lista (R-081)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.username or parts.password or parts.hostname not in ALLOWED_HOSTS:
        raise Blocked(f'origem ou redirecionamento não autorizado: {url}')


def http_error(error, url):
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 403 and (error.headers or {}).get('X-RateLimit-Remaining') == '0':
            return Unavailable(RATE_LIMIT)
        if error.code == 403:
            return Blocked(f'HTTP 403 em {url}: acesso negado pelo GitHub ou por um proxy (não é o limite da API)')
        return Blocked(f'HTTP {error.code} em {url}')
    return Unavailable(f'sem rede ao acessar {url}: {error}')


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        check_hop(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class Http:
    def __init__(self):
        self.opener = urllib.request.build_opener(Redirects())

    def open(self, url):
        check_hop(url)
        request = urllib.request.Request(url, headers={'User-Agent': 'data-lab-dotfiles-review', 'Accept': '*/*'})
        try:
            response = self.opener.open(request, timeout=60)
        except (urllib.error.URLError, OSError) as exc:
            raise http_error(exc, url) from exc
        check_hop(response.geturl())
        return response

    def get_bytes(self, url):
        with self.open(url) as response:
            content = response.read(LIMIT + 1)
        if len(content) > LIMIT:
            raise Blocked(f'artefato excede 256 MiB: {url}')
        return content

    def get_json(self, url):
        return json.loads(self.get_bytes(url))


def build_http():
    return Http()


def core(version):
    match = STABLE.match(version)
    if not match:
        raise Blocked(f'versão fora do formato estável: {version}')
    return match.group(1)


def vtuple(version):
    return tuple(int(part) for part in core(version).split('.'))


def version_field(old_field, new_core):
    """Preserva o formato de cada entrada: com ou sem o prefixo v."""
    return ('v' if old_field.startswith('v') else '') + new_core


def swap_version(url, old, new):
    """Troca a versão só nos segmentos do caminho, por regex, sem tocar o host."""
    old_core, new_core = core(old), core(new)
    parts = urllib.parse.urlsplit(url)
    pattern = re.compile(rf'(?<![0-9.]){re.escape(old_core)}(?![0-9])')
    segments = [pattern.sub(new_core, segment) for segment in parts.path.split('/')]
    swapped = urllib.parse.urlunsplit(parts._replace(path='/'.join(segments)))
    if swapped == url:
        raise Blocked(f'a versão {old} não aparece no URL: {url}')
    if urllib.parse.urlsplit(swapped).hostname not in ('github.com', 'api.github.com'):
        raise Blocked(f'host inesperado no URL novo: {swapped}')
    return swapped


def repository(url):
    path = urllib.parse.urlsplit(url).path.strip('/').split('/')
    if urllib.parse.urlsplit(url).hostname == 'api.github.com':
        return f'{path[1]}/{path[2]}'
    return f'{path[0]}/{path[1]}'


def lib():
    sys.path.insert(0, str(ROOT / 'lib'))
    import artifacts
    import python_tools
    return artifacts, python_tools


def check_elf(content, arch, where):
    if content[:4] != b'\x7fELF' or int.from_bytes(content[18:20], 'little') != ELF_MACHINE[arch]:
        raise Blocked(f'binário não é ELF da arquitetura {arch}: {where}')


def published_checksums(http, release):
    """Checksums publicados pela release, por nome de arquivo; arquivos sem formato reconhecido são ignorados."""
    found = {}
    for asset in release.get('assets', []):
        if not CHECKSUM_FILE.search(asset['name']):
            continue
        text = http.get_bytes(asset['browser_download_url']).decode(errors='replace')
        for line in text.splitlines():
            fields = line.split()
            if fields and re.fullmatch(r'[0-9a-fA-F]{64}', fields[0]):
                name = fields[1].lstrip('*') if len(fields) > 1 else asset['name'][:-len('.sha256')]
                found[PurePosixPath(name).name] = fields[0].lower()
    return found


def age_days(published, now):
    when = datetime.datetime.strptime(published, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
    return (now - when).days


def review_artifact_group(component, entries, http, now, min_age, latest):
    """Uma release nova vale para todas as combinações do componente, ou nenhuma (R-080)."""
    artifacts, _ = lib()
    old = entries[0]['version']
    release = latest(entries[0])
    new = release['tag_name']
    row = {'component': component, 'from': old, 'to': new, 'notes': release.get('html_url'), 'files': []}
    if vtuple(new) < vtuple(old):
        raise Blocked(f'{component}: a release mais nova ({new}) é anterior à fixada ({old}); downgrade recusado')
    if vtuple(new) == vtuple(old):
        return row | {'status': 'em dia'}, None
    if release.get('published_at') and age_days(release['published_at'], now) < min_age:
        return row | {'status': 'aguardar', 'reason': f'release com menos de {min_age} dias'}, None
    published = published_checksums(http, release) if release.get('assets') else {}
    proposed = []
    for entry in entries:
        url = swap_version(entry['url'], old, new)
        content = http.get_bytes(url)
        digest = hashlib.sha256(content).hexdigest()
        name = PurePosixPath(urllib.parse.urlsplit(url).path).name
        if name in published and published[name] != digest:
            raise Blocked(f'{component}: SHA-256 de {name} diverge do checksum publicado')
        candidate = dict(entry, version=version_field(entry['version'], core(new)), url=url, sha256=digest)
        try:
            files = artifacts.members(candidate, content) if component != 'firacode' else artifacts.font_members(content)
        except ValueError as exc:
            raise Blocked(f'{component}: artefato novo inválido ({name}): {exc}') from exc
        for binary in entry.get('binaries', [entry['binary']] if 'binary' in entry else []):
            check_elf(files[binary], entry['arch'], f'{name}:{binary}')
        if 'health' in entry:
            missing = [key for key in entry['health'] if key not in files]
            if missing:
                raise Blocked(f'{component}: arquivos de health ausentes no artefato novo: {", ".join(missing)}')
            candidate['health'] = {key: hashlib.sha256(files[key]).hexdigest() for key in entry['health']}
        row['files'].append({'url': url, 'sha256': digest, 'bytes': len(content),
                             'published': 'confere' if name in published else 'sem checksum publicado'})
        proposed.append(candidate)
    return row | {'status': 'nova versão',
                  'reminder': 'checksum que bate prova só o transporte; leia as notas da release'}, proposed


def review_github(manifest, http, now, min_age, components):
    def latest(entry):
        release = http.get_json(f'https://api.github.com/repos/{repository(entry["url"])}/releases/latest')
        if release.get('draft') or release.get('prerelease'):
            raise Blocked(f'a release mais recente de {repository(entry["url"])} é pre-release ou draft')
        core(release['tag_name'])
        return release
    return review_components(manifest, http, now, min_age, components, latest)


def review_plugins(manifest, http, now, min_age):
    def latest(entry):
        tags = http.get_json(f'https://api.github.com/repos/{repository(entry["url"])}/tags?per_page=100')
        stable = [tag['name'] for tag in tags if STABLE.match(tag['name'])]
        if not stable:
            raise Blocked(f'sem tag estável em {repository(entry["url"])}')
        # Tags dos plugins não têm data de publicação nem checksum; os tarballs gerados não têm bytes garantidos.
        return {'tag_name': max(stable, key=vtuple), 'html_url': f'https://github.com/{repository(entry["url"])}/tags'}
    rows, changes = [], {}
    for entry in [e for e in manifest['artifacts'] if e['component'] == 'plugins']:
        row, proposed = review_artifact_group('plugins', [entry], http, now, min_age, latest)
        row['name'] = entry['name']
        rows.append(row)
        if proposed:
            changes[id(entry)] = proposed[0]
    return rows, changes


def review_components(manifest, http, now, min_age, components, latest):
    rows, changes = [], {}
    for component in components:
        entries = [e for e in manifest['artifacts'] if e['component'] == component]
        if not entries:
            continue
        row, proposed = review_artifact_group(component, entries, http, now, min_age, latest)
        rows.append(row)
        if proposed:
            # Todas as combinações ou nenhuma: as listas têm o mesmo tamanho por construção.
            for entry, candidate in zip(entries, proposed, strict=True):
                changes[id(entry)] = candidate
    return rows, changes


def uv_env(out):
    home = out / 'uv-home'
    env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(home), 'XDG_CACHE_HOME': str(home / 'cache'),
           'XDG_DATA_HOME': str(home / 'data'), 'XDG_CONFIG_HOME': str(home / 'config'),
           'UV_CACHE_DIR': str(out / 'uv-cache'), 'UV_PYTHON_INSTALL_DIR': str(out / 'uv-python')}
    for value in env.values():
        if value.startswith(str(out)):
            Path(value).mkdir(parents=True, exist_ok=True)
    # Só rede e certificados passam adiante; nenhuma configuração do uv do usuário (UV_*, uv.toml).
    for name in ('HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY', 'https_proxy', 'http_proxy', 'no_proxy',
                 'SSL_CERT_FILE', 'SSL_CERT_DIR'):
        if os.environ.get(name):
            env[name] = os.environ[name]
    return env


def review_python_tools(root, out, python, http, run):
    _, python_tools = lib()
    minor = '.'.join(python['tool_python'].split('.')[:2])
    rows, locks = [], {}
    for tool in python['tools']:
        name, old = tool['name'], tool['version']
        new = http.get_json(f'https://pypi.org/pypi/{name}/json')['info']['version']
        row = {'component': f'python-tools:{name}', 'from': old, 'to': new}
        if not STABLE.match(new):
            rows.append(row | {'status': 'aguardar', 'reason': 'versão do PyPI não é estável'})
            continue
        if vtuple(new) <= vtuple(old):
            if vtuple(new) < vtuple(old):
                raise Blocked(f'{name}: o PyPI publica {new}, anterior a {old}; downgrade recusado')
            rows.append(row | {'status': 'em dia'})
            continue
        if shutil.which('uv') is None:
            raise Unavailable('uv ausente: necessário para regenerar e conferir os locks')
        # Mesma estrutura do repositório: o cabeçalho do lock sai com -o manifests/python-tools/NOME.txt.
        work = out / 'locks'
        if not (work / 'manifests/python-tools').exists():
            shutil.copytree(root / 'manifests/python-tools', work / 'manifests/python-tools')
        env = uv_env(out)
        # D-042: --no-build também na resolução; nada baixado do PyPI é executado.
        compile_argv = ['uv', '--no-config', 'pip', 'compile', '--universal', '--python-version', minor,
                        '--generate-hashes', '--no-build', '--index-url', 'https://pypi.org/simple',
                        '--no-python-downloads', '-o', f'manifests/python-tools/{name}.txt', '-']
        result = run(compile_argv, cwd=str(work), env=env, input=f'{name}=={new}\n', capture_output=True, text=True, check=False)
        if result.returncode != 0:
            rows.append(row | {'status': 'bloqueado', 'reason': f'uv pip compile falhou: {result.stderr.strip()[-300:]}'})
            continue
        lock_path = work / 'manifests/python-tools' / f'{name}.txt'
        try:
            lock = python_tools.read_lock(lock_path)
        except ValueError as exc:
            rows.append(row | {'status': 'bloqueado', 'reason': str(exc)})
            continue
        root_pin = lock['requirements'].get(python_tools.normalize(name))
        if not root_pin or root_pin['version'] != new:
            rows.append(row | {'status': 'bloqueado', 'reason': f'o lock novo não fixa {name}=={new}'})
            continue
        failed = []
        for platform in PLATFORMS:
            target = tempfile.mkdtemp(dir=out)
            result = run(['uv', '--no-config', 'pip', 'install', '--dry-run', '--no-build', '--require-hashes',
                          '--index-url', 'https://pypi.org/simple', '--no-python-downloads', '--python-platform', platform,
                          '--python-version', minor, '--target', target, '-r', str(lock_path)],
                         env=env, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                failed.append(platform)
        if failed:
            rows.append(row | {'status': 'bloqueado', 'reason': 'o lock não instala sem compilar em ' + ', '.join(failed)})
            continue
        rows.append(row | {'status': 'nova versão'})
        locks[name] = (new, lock_path.read_text())
    return rows, locks


def review_cpython(out, manifest, python, run, proposed_uv=None):
    uv = shutil.which('uv')
    pinned = next(e['version'] for e in manifest['artifacts'] if e['component'] == 'uv')
    accepted = {pinned} | ({proposed_uv} if proposed_uv else set())
    if uv is None:
        raise Unavailable(f'uv ausente; o CPython é listado com o uv fixado ({pinned})')
    env = uv_env(out)
    result = run(['uv', '--version'], env=env, capture_output=True, text=True, check=False)
    found = (result.stdout.split() or ['', ''])[1] if result.returncode == 0 else ''
    if found not in accepted:
        raise Unavailable(f'o uv no PATH é {found or "desconhecido"}; use o uv fixado ({" ou ".join(sorted(accepted))}), '
                          'porque a lista de CPython vem embutida no binário')
    listed = run(['uv', 'python', 'list', '--all-versions', '--only-downloads', '--all-platforms', '--output-format', 'json'],
                 env=env, capture_output=True, text=True, check=False)
    if listed.returncode != 0:
        raise Unavailable(f'uv python list falhou: {listed.stderr.strip()[-300:]}')
    combos = {}
    for row in json.loads(listed.stdout):
        if row.get('implementation') != 'cpython' or row.get('variant', 'default') != 'default' \
                or row.get('os') != 'linux' or not re.fullmatch(r'3\.\d+\.\d+', str(row.get('version', ''))):
            continue
        if row.get('arch') in ELF_MACHINE and row.get('libc') in ('gnu', 'musl'):
            combos.setdefault(row['version'], set()).add((row['arch'], row['libc']))
    complete = [version for version, seen in combos.items() if len(seen) == 4]
    rows, mapping = [], {}
    for current in python['interpreters']:
        minor = current.rsplit('.', 1)[0]
        options = [v for v in complete if v.rsplit('.', 1)[0] == minor]
        best = max(options, key=vtuple, default=current)
        status = 'nova versão' if vtuple(best) > vtuple(current) else 'em dia'
        rows.append({'component': f'cpython:{minor}', 'from': current, 'to': best, 'status': status, 'uv': found})
        if status == 'nova versão':
            mapping[current] = best
    if python['tool_python'] in mapping:
        rows.append({'component': 'cpython:tool_python', 'from': python['tool_python'], 'to': mapping[python['tool_python']],
                     'status': 'nova versão',
                     'reminder': 'todas as venvs instaladas passam a divergente (bloqueante); escreva uma nota de migração '
                                 'no CHANGELOG e confira UV_HASH_FLOOR e o piso do uv'})
    return rows, mapping


def unified(path, old, new):
    return ''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f'a/{path}', f'b/{path}'))


def references(root, old_versions):
    """Arquivos do checkout que ainda citam as versões antigas, fora dos manifestos."""
    found = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink() or relative.parts[0] in ('.git', 'manifests') or path.stat().st_size > 2 * 1024**2:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for version in old_versions:
            if re.search(rf'(?<![0-9.]){re.escape(version)}(?![0-9])', text):
                found.append(f'{relative}: {version}')
    return found


def prepare(out):
    """lib/ lê HOME e DEVSHELL_* ao ser importada: tudo aponta para dentro de out (R-080)."""
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    home = out / 'home'
    os.environ.update({'HOME': str(home), 'DEVSHELL_ROOT': str(ROOT), 'DEVSHELL_COMPONENT': 'uv',
                       'XDG_CACHE_HOME': str(home / '.cache'), 'XDG_DATA_HOME': str(home / '.local/share'),
                       'XDG_STATE_HOME': str(home / '.local/state'), 'XDG_CONFIG_HOME': str(home / '.config')})
    home.mkdir(exist_ok=True, mode=0o700)


def review(root, out, groups, http, run, now, min_age):
    """Relatório, texto do patch e código de saída; só escreve em out (D-040)."""
    prepare(out)
    manifest_text = (root / 'manifests/artifacts.json').read_text()
    python_text = (root / 'manifests/python.json').read_text()
    manifest, python = json.loads(manifest_text), json.loads(python_text)
    report = {'groups': list(groups), 'items': [], 'errors': [], 'references': []}
    changes, locks, cpython = {}, {}, {}
    code = 0
    steps = []
    if 'github' in groups:
        steps.append(lambda: review_github(manifest, http, now, min_age, GITHUB_COMPONENTS))
    if 'plugins' in groups:
        steps.append(lambda: review_plugins(manifest, http, now, min_age))
    for step in steps:
        try:
            rows, found = step()
            report['items'] += rows
            changes |= found
        except Blocked as exc:
            report['errors'].append(str(exc))
            code = max(code, 2)
        except Unavailable as exc:
            report['errors'].append(str(exc))
            code = 3
    if 'python-tools' in groups:
        try:
            rows, locks = review_python_tools(root, out, python, http, run)
            report['items'] += rows
        except (Blocked, Unavailable) as exc:
            report['errors'].append(str(exc))
            code = 3 if isinstance(exc, Unavailable) else max(code, 2)
    if 'cpython' in groups:
        proposed_uv = next((c['version'] for c in changes.values() if c['component'] == 'uv'), None)
        try:
            rows, cpython = review_cpython(out, manifest, python, run, proposed_uv)
            report['items'] += rows
        except (Blocked, Unavailable) as exc:
            report['errors'].append(str(exc))
            code = 3 if isinstance(exc, Unavailable) else max(code, 2)
    if code == 2:
        # Um erro bloqueia sem patch parcial com versões misturadas.
        changes, locks, cpython = {}, {}, {}
    new_manifest = dict(manifest, artifacts=[changes.get(id(entry), entry) for entry in manifest['artifacts']])
    new_python = json.loads(python_text)
    for tool in new_python['tools']:
        if tool['name'] in locks:
            tool['version'] = locks[tool['name']][0]
    new_python['interpreters'] = [cpython.get(v, v) for v in new_python['interpreters']]
    new_python['tool_python'] = cpython.get(new_python['tool_python'], new_python['tool_python'])
    patch_text = ''
    if new_manifest != manifest:
        patch_text += unified('manifests/artifacts.json', manifest_text, json.dumps(new_manifest, indent=2, ensure_ascii=False) + '\n')
    if new_python != python:
        patch_text += unified('manifests/python.json', python_text, json.dumps(new_python, indent=2, ensure_ascii=False) + '\n')
    for name, (_, text) in sorted(locks.items()):
        path = f'manifests/python-tools/{name}.txt'
        patch_text += unified(path, (root / path).read_text(), text)
    old_versions = {row['from'] for row in report['items'] if row.get('status') == 'nova versão' and row.get('from')}
    old_versions = {core(v) if STABLE.match(v) else v for v in old_versions}
    report['references'] = references(root, sorted(old_versions)) if patch_text else []
    (out / 'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    if patch_text:
        (out / 'manifests.patch').write_text(patch_text)
    return report, patch_text, code


def show(report, out, patch_text):
    for row in report['items']:
        line = f"  {row['component']}{':' + row['name'] if row.get('name') else ''}: {row['status']} ({row['from']} -> {row['to']})"
        print(line + (f" — {row['reason']}" if row.get('reason') else ''))
        for item in row.get('files', []):
            print(f"      {item['url']} ({item['bytes']} bytes, {item['published']})")
        if row.get('notes') and row['status'] == 'nova versão':
            print(f"      notas: {row['notes']}")
        if row.get('reminder'):
            print(f"      lembrete: {row['reminder']}")
    for error in report['errors']:
        print('  erro:', error)
    if report['references']:
        print('Referências às versões antigas fora dos manifestos (revise junto):')
        for ref in report['references']:
            print('  ', ref)
    print(f"Proposta: {out / 'manifests.patch'} (revise e aplique com git apply)" if patch_text else 'Sem proposta de mudança.')
    print(f"Relatório: {out / 'report.json'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Revisão assistida de manifestos (ferramenta de mantenedor).')
    parser.add_argument('--only', choices=GROUPS, action='append')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--min-age-days', type=int, default=7)
    parser.add_argument('--root', type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    out = args.out or Path(tempfile.mkdtemp(prefix='review-manifests-'))
    groups = args.only or list(GROUPS)
    report, patch_text, code = review(args.root, out, groups, build_http(), subprocess.run,
                                      datetime.datetime.now(datetime.timezone.utc), args.min_age_days)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        show(report, out, patch_text)
    return code


if __name__ == '__main__':
    sys.exit(main())
