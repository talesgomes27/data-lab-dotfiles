"""Bloco H: revisão assistida de manifestos, offline, com HTTP e uv simulados."""
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('review_manifests', ROOT / 'scripts/review-manifests.py')
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)
NOW = datetime.datetime(2026, 11, 12, tzinfo=datetime.timezone.utc)
OLD = (NOW - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')


def elf(machine):
    # e_ident tem 16 bytes; e_type em 16 e e_machine em 18, como no ELF real.
    return b'\x7fELF' + b'\x02\x01\x01' + b'\x00' * 9 + b'\x02\x00' + machine.to_bytes(2, 'little') + b'\x00' * 40


def tarball(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


class FakeHttp:
    def __init__(self):
        self.json, self.bytes, self.calls = {}, {}, []

    def get_json(self, url):
        self.calls.append(url)
        value = self.json.get(url)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise review.Blocked(f'404: {url}')
        return value

    def get_bytes(self, url):
        self.calls.append(url)
        value = self.bytes.get(url)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise review.Blocked(f'404: {url}')
        return value


class ReviewTest(unittest.TestCase):
    def setUp(self):
        # prepare() muda os.environ para apontar lib/ ao --out; não pode vazar para o resto da suíte.
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        self.runs = 0
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / 'repo'
        (self.root / 'manifests/python-tools').mkdir(parents=True)
        (self.root / 'lib').symlink_to(ROOT / 'lib')
        self.out = self.base / 'out'
        self.http = FakeHttp()
        self.uv_old = {'x86_64': elf(62), 'aarch64': elf(183)}
        self.artifacts = {'schema': 1, 'artifacts': []}
        for arch, triple in (('x86_64', 'x86_64'), ('aarch64', 'aarch64')):
            for libc in ('gnu', 'musl'):
                content = tarball({f'uv-{triple}-unknown-linux-{libc}/uv': self.uv_old[arch],
                                   f'uv-{triple}-unknown-linux-{libc}/uvx': self.uv_old[arch]})
                self.artifacts['artifacts'].append({
                    'component': 'uv', 'version': '0.13.7', 'arch': arch, 'libc': libc, 'format': 'tar.gz',
                    'binary': 'uv', 'binaries': ['uv', 'uvx'], 'sha256': sha(content),
                    'url': f'https://github.com/astral-sh/uv/releases/download/0.13.7/uv-{triple}-unknown-linux-{libc}.tar.gz'})
        self.python = {'interpreters': ['3.12.12', '3.13.11'], 'tool_python': '3.13.11',
                       'tools': [{'name': 'ruff', 'version': '0.17.3'}]}
        self.write_manifests()
        (self.root / 'manifests/python-tools/ruff.txt').write_text(
            '#    uv --no-config pip compile --universal --python-version 3.13 --generate-hashes -o ruff.txt -\n'
            'ruff==0.17.3 \\\n    --hash=sha256:' + 'a' * 64 + '\n')
        (self.root / 'docs').mkdir()
        (self.root / 'docs/USO.md').write_text('use uv 0.13.7\n')

    def write_manifests(self):
        (self.root / 'manifests/artifacts.json').write_text(json.dumps(self.artifacts, indent=2, ensure_ascii=False) + '\n')
        (self.root / 'manifests/python.json').write_text(json.dumps(self.python, indent=2, ensure_ascii=False) + '\n')

    def release(self, repo, tag, published=OLD, assets=(), prerelease=False):
        self.http.json[f'https://api.github.com/repos/{repo}/releases/latest'] = {
            'tag_name': tag, 'draft': False, 'prerelease': prerelease, 'published_at': published,
            'html_url': f'https://github.com/{repo}/releases/tag/{tag}',
            'assets': [{'name': name, 'browser_download_url': url, 'size': 1} for name, url in assets]}

    def new_uv(self, version='0.14.0', machine_override=None):
        files = {}
        for arch, triple in (('x86_64', 'x86_64'), ('aarch64', 'aarch64')):
            for libc in ('gnu', 'musl'):
                binary = elf(machine_override or (62 if arch == 'x86_64' else 183))
                content = tarball({f'uv-{triple}-unknown-linux-{libc}/uv': binary, f'uv-{triple}-unknown-linux-{libc}/uvx': binary})
                url = f'https://github.com/astral-sh/uv/releases/download/{version}/uv-{triple}-unknown-linux-{libc}.tar.gz'
                self.http.bytes[url] = content
                files[url] = content
        return files

    def run_review(self, groups=('github',), run=None, min_age=7):
        # Cada execução num --out novo e vazio (R-080).
        self.runs += 1
        self.out = self.base / f'out-{self.runs}'
        return review.review(self.root, self.out, list(groups), self.http, run or self.no_run, NOW, min_age)

    @staticmethod
    def no_run(argv, **kwargs):
        raise AssertionError(f'uv não deveria rodar: {argv}')

    def tree(self, root):
        return sorted((str(p.relative_to(root)), p.read_bytes() if p.is_file() else b'')
                      for p in root.rglob('*') if not p.is_symlink())

    # T-701

    def test_r081_new_uv_release_proposes_four_urls_and_checksums(self):
        files = self.new_uv()
        self.release('astral-sh/uv', '0.14.0')
        before = self.tree(self.root)
        report, patch_text, code = self.run_review()
        self.assertEqual(code, 0)
        self.assertEqual(self.tree(self.root), before)
        item = next(row for row in report['items'] if row['component'] == 'uv')
        self.assertEqual(item['status'], 'nova versão')
        for url, content in files.items():
            self.assertIn(url, patch_text)
            self.assertIn(sha(content), patch_text)
        self.assertTrue((self.out / 'manifests.patch').is_file())
        self.assertIn('sem checksum publicado', json.dumps(report, ensure_ascii=False))
        self.assertTrue(any('USO.md' in ref for ref in report['references']))
        copy = self.base / 'copy'
        shutil.copytree(self.root, copy, symlinks=True)
        subprocess.run(['git', 'init', '-q', str(copy)], check=True)
        subprocess.run(['git', '-C', str(copy), 'apply', '--check', str(self.out / 'manifests.patch')], check=True)

    def test_r081_no_new_release_means_no_patch(self):
        self.release('astral-sh/uv', '0.13.7')
        report, patch_text, code = self.run_review()
        self.assertEqual(code, 0)
        self.assertEqual(patch_text, '')
        self.assertFalse((self.out / 'manifests.patch').exists())

    def test_r081_downgrade_and_prerelease_and_young_release(self):
        self.release('astral-sh/uv', '0.12.0')
        self.assertEqual(self.run_review()[2], 2)
        self.new_uv('0.14.0')
        self.release('astral-sh/uv', '0.14.0', published=NOW.strftime('%Y-%m-%dT%H:%M:%SZ'))
        report, patch_text, code = self.run_review()
        self.assertEqual(code, 0)
        self.assertEqual(report['items'][0]['status'], 'aguardar')
        self.assertEqual(patch_text, '')
        self.assertNotEqual(self.run_review(min_age=0)[1], '')

    def test_r081_published_checksum_must_match(self):
        files = self.new_uv()
        url = next(iter(files))
        name = url.rsplit('/', 1)[1]
        self.release('astral-sh/uv', '0.14.0', assets=[(name + '.sha256', url + '.sha256')])
        self.http.bytes[url + '.sha256'] = f'{"b" * 64}  {name}\n'.encode()
        self.assertEqual(self.run_review()[2], 2)
        self.http.bytes[url + '.sha256'] = f'{sha(files[url])}  {name}\n'.encode()
        report, _, code = self.run_review()
        self.assertEqual(code, 0)
        self.assertIn('confere', json.dumps(report, ensure_ascii=False))

    def test_r081_missing_combination_blocks_the_whole_component(self):
        files = self.new_uv()
        del self.http.bytes[next(iter(files))]
        self.release('astral-sh/uv', '0.14.0')
        report, patch_text, code = self.run_review()
        self.assertEqual(code, 2)
        self.assertEqual(patch_text, '')

    def test_r081_wrong_architecture_or_missing_binary_is_refused(self):
        self.new_uv(machine_override=3)
        self.release('astral-sh/uv', '0.14.0')
        self.assertEqual(self.run_review()[2], 2)

    def test_r081_redirect_hop_rules(self):
        for url in ('http://github.com/x', 'https://evil.example/x', 'https://user:pw@github.com/x'):
            with self.subTest(url), self.assertRaises(review.Blocked):
                review.check_hop(url)
        for url in ('https://release-assets.githubusercontent.com/x', 'https://objects.githubusercontent.com/x',
                    'https://codeload.github.com/x', 'https://api.github.com/x'):
            review.check_hop(url)

    def test_r080_rate_limit_is_exit_3(self):
        error = urllib.error.HTTPError('https://api.github.com', 403, 'rate', {'X-RateLimit-Remaining': '0'}, None)
        self.http.json['https://api.github.com/repos/astral-sh/uv/releases/latest'] = review.http_error(error, 'x')
        self.assertEqual(self.run_review()[2], 3)

    def test_r081_version_swap_keeps_each_format(self):
        cases = [('https://github.com/twpayne/chezmoi/releases/download/v2.74.0/chezmoi_2.74.0_linux_arm64.tar.gz',
                  '2.74.0', '2.75.1',
                  'https://github.com/twpayne/chezmoi/releases/download/v2.75.1/chezmoi_2.75.1_linux_arm64.tar.gz'),
                 ('https://github.com/nushell/nushell/releases/download/0.116.1/nu-0.116.1-x86_64-unknown-linux-gnu.tar.gz',
                  '0.116.1', '0.117.0',
                  'https://github.com/nushell/nushell/releases/download/0.117.0/nu-0.117.0-x86_64-unknown-linux-gnu.tar.gz'),
                 ('https://api.github.com/repos/zsh-users/zsh-autosuggestions/tarball/v0.7.1', 'v0.7.1', '0.7.2',
                  'https://api.github.com/repos/zsh-users/zsh-autosuggestions/tarball/v0.7.2'),
                 ('https://github.com/twpayne/chezmoi/releases/download/v2.74.0/chezmoi-linux-amd64-musl', '2.74.0', '2.75.1',
                  'https://github.com/twpayne/chezmoi/releases/download/v2.75.1/chezmoi-linux-amd64-musl')]
        for url, old, new, expected in cases:
            with self.subTest(url):
                self.assertEqual(review.swap_version(url, old, new), expected)
        self.assertEqual(review.version_field('v0.7.1', '0.7.2'), 'v0.7.2')
        self.assertEqual(review.version_field('0.8.0', '0.9.0'), '0.9.0')

    def test_r081_plugins_use_the_highest_stable_tag(self):
        old = tarball({'repo-0.8.0/hl.zsh': b'# hl\n'})
        self.artifacts['artifacts'] = [{'component': 'plugins', 'name': 'highlighting', 'version': '0.8.0', 'arch': 'any',
                                        'libc': 'any', 'format': 'tar.gz', 'sha256': sha(old),
                                        'health': {'hl.zsh': sha(b'# hl\n')},
                                        'url': 'https://api.github.com/repos/zsh-users/zsh-syntax-highlighting/tarball/0.8.0'}]
        self.write_manifests()
        self.http.json['https://api.github.com/repos/zsh-users/zsh-syntax-highlighting/tags?per_page=100'] = [
            {'name': '0.10.0-alpha1-pre'}, {'name': '0.9.1'}, {'name': '0.10.0'}, {'name': '0.8.0'}]
        new = tarball({'repo-0.10.0/hl.zsh': b'# hl novo\n'})
        self.http.bytes['https://api.github.com/repos/zsh-users/zsh-syntax-highlighting/tarball/0.10.0'] = new
        report, patch_text, code = self.run_review(groups=('plugins',))
        self.assertEqual(code, 0)
        self.assertIn('/tarball/0.10.0', patch_text)
        self.assertIn(sha(b'# hl novo\n'), patch_text)
        self.assertIn('sem checksum publicado', json.dumps(report, ensure_ascii=False))

    def test_r080_only_and_json_and_isolation(self):
        self.out = self.base / 'out-main'
        self.release('astral-sh/uv', '0.13.7')
        with patch.object(review, 'build_http', return_value=self.http), patch.dict(os.environ, {'HOME': str(self.base / 'home-real')}):
            (self.base / 'home-real').mkdir()
            out = io.StringIO()
            with patch('sys.stdout', out):
                code = review.main(['--root', str(self.root), '--out', str(self.out), '--only', 'github', '--json'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())['groups'], ['github'])
        self.assertEqual(list((self.base / 'home-real').iterdir()), [])

    def test_r080_devshell_does_not_expose_the_script(self):
        text = (ROOT / 'bin/devshell').read_text()
        self.assertNotIn('review-manifests', text)

    # T-703

    def fake_uv(self, version='0.13.7', fail_platform=None, pythons=None):
        calls = []

        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            if argv[1:] == ['--version']:
                return subprocess.CompletedProcess(argv, 0, f'uv {version} (abc)\n', '')
            if 'compile' in argv:
                target = Path(kwargs['cwd']) / argv[argv.index('-o') + 1]
                package = kwargs['input'].strip()
                target.write_text('#    uv --no-config pip compile --universal --python-version 3.13 --generate-hashes -o '
                                  + argv[argv.index('-o') + 1] + ' -\n' + package + ' \\\n    --hash=sha256:' + 'c' * 64 + '\n')
                return subprocess.CompletedProcess(argv, 0, '', '')
            if 'install' in argv:
                platform = argv[argv.index('--python-platform') + 1]
                return subprocess.CompletedProcess(argv, 1 if platform == fail_platform else 0, '', 'falhou')
            if argv[1:3] == ['python', 'list']:
                return subprocess.CompletedProcess(argv, 0, json.dumps(pythons or []), '')
            raise AssertionError(argv)
        return run, calls

    def test_r082_new_tool_version_regenerates_and_checks_the_lock(self):
        self.http.json['https://pypi.org/pypi/ruff/json'] = {'info': {'version': '0.18.0'}}
        run, calls = self.fake_uv()
        report, patch_text, code = self.run_review(groups=('python-tools',), run=run)
        self.assertEqual(code, 0)
        self.assertIn('ruff==0.18.0', patch_text)
        self.assertIn('"version": "0.18.0"', patch_text)
        compile_argv, compile_kwargs = next((a, k) for a, k in calls if 'compile' in a)
        for flag in ('--no-build', '--no-python-downloads', '--generate-hashes', '--universal'):
            self.assertIn(flag, compile_argv)
        self.assertEqual(compile_argv[compile_argv.index('-o') + 1], 'manifests/python-tools/ruff.txt')
        env = compile_kwargs['env']
        for key in ('HOME', 'UV_CACHE_DIR', 'UV_PYTHON_INSTALL_DIR', 'XDG_CACHE_HOME'):
            self.assertTrue(env[key].startswith(str(self.out)), key)
        self.assertEqual(len([a for a, _ in calls if 'install' in a]), 4)
        self.assertIn('-o manifests/python-tools/ruff.txt -', patch_text)

    def test_r082_platform_failure_blocks_the_tool(self):
        self.http.json['https://pypi.org/pypi/ruff/json'] = {'info': {'version': '0.18.0'}}
        run, _ = self.fake_uv(fail_platform='aarch64-unknown-linux-musl')
        report, patch_text, code = self.run_review(groups=('python-tools',), run=run)
        self.assertEqual(report['items'][0]['status'], 'bloqueado')
        self.assertEqual(patch_text, '')

    def test_r083_cpython_needs_the_pinned_uv(self):
        run, _ = self.fake_uv(version='0.15.0')
        with patch.object(review.shutil, 'which', return_value='/usr/bin/uv'):
            self.assertEqual(self.run_review(groups=('cpython',), run=run)[2], 3)
        with patch.object(review.shutil, 'which', return_value=None):
            self.assertEqual(self.run_review(groups=('cpython',), run=run)[2], 3)

    def test_r083_cpython_picks_newest_stable_patch_on_all_platforms(self):
        def entries(version, variant='default', implementation='cpython', skip=()):
            rows = []
            for arch in ('x86_64', 'aarch64'):
                for libc in ('gnu', 'musl'):
                    if (arch, libc) in skip:
                        continue
                    rows.append({'implementation': implementation, 'version': version, 'variant': variant,
                                 'os': 'linux', 'arch': arch, 'libc': libc})
            return rows
        pythons = (entries('3.13.14') + entries('3.13.15', skip=[('aarch64', 'musl')]) + entries('3.13.16', variant='freethreaded')
                   + entries('3.15.0b4') + entries('3.12.13') + entries('3.13.17', implementation='pypy'))
        run, calls = self.fake_uv(pythons=pythons)
        with patch.object(review.shutil, 'which', return_value='/usr/bin/uv'):
            report, patch_text, code = self.run_review(groups=('cpython',), run=run)
        self.assertEqual(code, 0)
        self.assertIn('"3.13.14"', patch_text)
        self.assertIn('"3.12.13"', patch_text)
        self.assertIn('"tool_python": "3.13.14"', patch_text)
        argv = next(a for a, _ in calls if a[1:3] == ['python', 'list'])
        self.assertIn('--all-platforms', argv)
        self.assertIn('divergente', json.dumps(report, ensure_ascii=False))

    # Achados da revisão do código

    def test_r080_unavailable_never_masks_a_blocked_and_drops_the_patch(self):
        files = self.new_uv()
        url = next(iter(files))
        name = url.rsplit('/', 1)[1]
        self.release('astral-sh/uv', '0.14.0', assets=[(name + '.sha256', url + '.sha256')])
        self.http.bytes[url + '.sha256'] = f'{"b" * 64}  {name}\n'.encode()
        old = tarball({'repo-0.8.0/hl.zsh': b'# hl\n'})
        self.artifacts['artifacts'].append({'component': 'plugins', 'name': 'hl', 'version': '0.8.0', 'arch': 'any', 'libc': 'any',
                                            'format': 'tar.gz', 'sha256': sha(old), 'health': {'hl.zsh': sha(b'# hl\n')},
                                            'url': 'https://api.github.com/repos/x/hl/tarball/0.8.0'})
        self.write_manifests()
        self.http.json['https://api.github.com/repos/x/hl/tags?per_page=100'] = [{'name': '0.9.0'}]
        self.http.bytes['https://api.github.com/repos/x/hl/tarball/0.9.0'] = tarball({'repo-0.9.0/hl.zsh': b'# novo\n'})
        with patch.object(review.shutil, 'which', return_value=None):
            report, patch_text, code = self.run_review(groups=('github', 'plugins', 'cpython'))
        self.assertEqual(code, 2)
        self.assertEqual(patch_text, '')
        self.assertFalse((self.out / 'manifests.patch').exists())

    def test_r080_non_empty_out_is_refused(self):
        self.release('astral-sh/uv', '0.13.7')
        self.out = self.base / 'usado'
        self.out.mkdir()
        (self.out / 'manifests.patch').write_text('antigo')
        with self.assertRaises(review.Blocked):
            review.review(self.root, self.out, ['github'], self.http, self.no_run, NOW, 7)

    def test_r080_script_never_writes_bytecode(self):
        self.assertTrue(review.sys.dont_write_bytecode)

    def test_r080_http_errors_map_to_the_right_exit(self):
        for code, kind in ((404, review.Blocked), (500, review.Unavailable), (503, review.Unavailable), (429, review.Unavailable)):
            with self.subTest(code):
                error = urllib.error.HTTPError('https://api.github.com', code, 'x', {}, None)
                self.assertIsInstance(review.http_error(error, 'u'), kind)
        self.assertIsInstance(review.http_error(urllib.error.URLError('timeout'), 'u'), review.Unavailable)

    def test_r081_redirect_handler_validates_every_hop(self):
        handler = review.Redirects()
        with self.assertRaises(review.Blocked):
            handler.redirect_request(None, None, 302, 'Found', {}, 'http://github.com/x')
        opener = review.build_http().opener
        self.assertTrue(any(isinstance(h, review.Redirects) for h in opener.handlers))

    def test_r081_interrupted_download_and_bad_json_are_reported(self):
        class Broken:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *args):
                raise TimeoutError('tempo esgotado')

            def geturl(self):
                return 'https://github.com/x'
        http = review.Http()
        with patch.object(http, 'open', return_value=Broken()), self.assertRaises(review.Unavailable):
            http.get_bytes('https://github.com/x')
        with patch.object(http, 'get_bytes', return_value=b'nao json'), self.assertRaises(review.Blocked):
            http.get_json('https://api.github.com/x')

    def test_r081_prerelease_and_missing_binary(self):
        self.new_uv()
        self.release('astral-sh/uv', '0.14.0', prerelease=True)
        self.assertEqual(self.run_review()[2], 2)
        for url in list(self.http.bytes):
            if url.endswith('.tar.gz'):
                triple = url.rsplit('/', 1)[1][3:-7]
                self.http.bytes[url] = tarball({f'uv-{triple}/uv': elf(62)})
        self.release('astral-sh/uv', '0.14.0')
        self.assertEqual(self.run_review()[2], 2)

    def test_r081_size_delta_against_the_old_release(self):
        files = self.new_uv()
        names = [url.rsplit('/', 1)[1] for url in files]
        self.release('astral-sh/uv', '0.14.0')
        self.http.json['https://api.github.com/repos/astral-sh/uv/releases/tags/0.13.7'] = {
            'assets': [{'name': name, 'size': 10} for name in names]}
        report, _, _ = self.run_review()
        item = next(row for row in report['items'] if row['component'] == 'uv')
        self.assertTrue(all('delta' in row for row in item['files']), item['files'])

    def test_r082_uv_env_is_exactly_isolated(self):
        with patch.dict(os.environ, {'UV_INDEX_URL': 'https://evil.example', 'HTTPS_PROXY': 'http://proxy:1'}):
            env = review.uv_env(self.base / 'out-env')
        self.assertNotIn('UV_INDEX_URL', env)
        self.assertEqual(env['HTTPS_PROXY'], 'http://proxy:1')
        allowed = {'PATH', 'HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'UV_CACHE_DIR',
                   'UV_PYTHON_INSTALL_DIR', 'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY', 'https_proxy', 'http_proxy',
                   'no_proxy', 'SSL_CERT_FILE', 'SSL_CERT_DIR'}
        self.assertLessEqual(set(env), allowed)

    def test_r083_report_names_the_uv_floors(self):
        pythons = [{'implementation': 'cpython', 'version': '3.13.14', 'variant': 'default', 'os': 'linux',
                    'arch': arch, 'libc': libc} for arch in ('x86_64', 'aarch64') for libc in ('gnu', 'musl')]
        run, _ = self.fake_uv(pythons=pythons)
        with patch.object(review.shutil, 'which', return_value='/usr/bin/uv'):
            report, _, _ = self.run_review(groups=('cpython',), run=run)
        text = json.dumps(report, ensure_ascii=False)
        self.assertIn('UV_HASH_FLOOR', text)
        self.assertIn('0.13.5', text)


if __name__ == '__main__':
    unittest.main()
