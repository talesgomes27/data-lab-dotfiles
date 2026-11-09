"""Fixtures artificiais; testes offline da fronteira de escrita e de arquivos tar."""
import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
os.environ.setdefault('DEVSHELL_ROOT', str(ROOT))
os.environ.setdefault('DEVSHELL_COMPONENTS', 'bash zsh uv chezmoi')
os.environ.setdefault('DEVSHELL_COMPONENT', 'uv')
import state
import artifacts
import python_tools


class ArtifactBoundary(unittest.TestCase):
    def font_zip(self, extra=None):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('FiraCodeNerdFontMono-Regular.ttf', b'font fixture')
            archive.writestr('LICENSE', b'license fixture')
            archive.writestr('README.md', b'not installed')
            if extra:
                archive.writestr(*extra)
        content = stream.getvalue()
        return {'component': 'firacode', 'format': 'zip', 'sha256': state.digest(content)}, content

    def test_font_zip_selects_fonts_and_license_without_extracting(self):
        artifact, content = self.font_zip()
        self.assertEqual(artifacts.members(artifact, content), {
            'FiraCodeNerdFontMono-Regular.ttf': b'font fixture', 'LICENSE': b'license fixture'})

    def test_font_zip_rejects_traversal_links_and_duplicate_names(self):
        link = zipfile.ZipInfo('link.ttf')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for name in ('../outside.ttf', '/outside.ttf', 'dir\\outside.ttf', link, 'dir/LICENSE'):
            with self.subTest(name=name):
                artifact, content = self.font_zip((name, b'bad'))
                with self.assertRaises(ValueError):
                    artifacts.members(artifact, content)

    def test_font_zip_checks_digest_before_parsing(self):
        artifact, content = self.font_zip()
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            artifacts.members(artifact, content + b'bad')

    def packed(self, name='package/uv', kind=tarfile.REGTYPE):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.linkname = '/etc/passwd' if kind == tarfile.SYMTYPE else ''
            item.size = 3 if kind == tarfile.REGTYPE else 0
            archive.addfile(item, io.BytesIO(b'uv!') if item.size else None)
        content = stream.getvalue()
        return {'component': 'uv', 'binary': 'uv', 'format': 'tar.gz', 'sha256': state.digest(content)}, content

    def test_checksum_failure_has_no_members(self):
        artifact, data = self.packed()
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            artifacts.members(artifact, data + b'corrompido')

    def test_archive_traversal_is_rejected(self):
        for name in ('../uv', '/usr/bin/uv', 'package/../../uv'):
            artifact, data = self.packed(name)
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'insegura'):
                artifacts.members(artifact, data)

    def test_plugin_documentation_symlinks_are_ignored(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            item = tarfile.TarInfo('package/plugin.zsh')
            item.size = 3
            archive.addfile(item, io.BytesIO(b'zsh'))
            item = tarfile.TarInfo('package/README.md')
            item.type = tarfile.SYMTYPE
            item.linkname = '../../outside'
            archive.addfile(item)
        content = stream.getvalue()
        artifact = {'component': 'plugins', 'format': 'tar.gz', 'sha256': state.digest(content)}
        self.assertEqual(artifacts.members(artifact, content), {'plugin.zsh': b'zsh'})

    def test_archive_symlink_is_rejected(self):
        artifact, data = self.packed(kind=tarfile.SYMTYPE)
        with self.assertRaisesRegex(ValueError, 'insegura'):
            artifacts.members(artifact, data)

    def test_archive_binary_is_selected_without_extraction(self):
        artifact, data = self.packed()
        self.assertEqual(artifacts.members(artifact, data), {'uv': b'uv!'})

    def test_missing_uvx_is_rejected_for_uv_bundle(self):
        artifact, content = self.packed()
        artifact['binaries'] = ['uv', 'uvx']
        with self.assertRaisesRegex(ValueError, 'esperados'):
            artifacts.members(artifact, content)

    def test_failed_network_does_not_write_cache(self):
        artifact, _ = self.packed()
        artifact['url'] = 'https://github.com/example/missing'
        with tempfile.TemporaryDirectory() as temp, patch.object(artifacts, 'CACHE', Path(temp)), patch.dict(os.environ, {'DEVSHELL_OFFLINE': '0'}):
            import urllib.error
            with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('offline')):
                with self.assertRaises(urllib.error.URLError):
                    artifacts.download(artifact)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_installer_repairs_owner_execute_for_identical_binary(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / 'bin/chezmoi'
            target.parent.mkdir()
            target.write_bytes(b'fixture')
            target.chmod(0o600)
            plan = {'operation': 'install-chezmoi', 'approval': 'ok', 'destination': str(target.parent), 'artifacts': [{}]}
            with patch.object(artifacts, 'COMPONENT', 'chezmoi'), patch.object(state, 'STATE', base / 'state'), \
                 patch.object(artifacts, 'download', return_value=b'x'), patch.object(artifacts, 'members', return_value={'chezmoi': b'fixture'}), \
                 patch.object(state, 'report'), patch.dict(os.environ, {'DEVSHELL_APPROVAL': 'ok'}):
                artifacts.apply(plan)
            self.assertEqual(target.stat().st_mode & 0o777, 0o700)
            self.assertEqual(target.read_bytes(), b'fixture')

    def test_new_artifact_has_final_mode_when_atomically_published(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            plan = {'operation': 'install-chezmoi', 'approval': 'ok', 'destination': str(base / 'bin'), 'artifacts': [{}]}
            with patch.object(artifacts, 'COMPONENT', 'chezmoi'), patch.object(state, 'STATE', base / 'state'), \
                 patch.object(artifacts, 'download', return_value=b'x'), patch.object(artifacts, 'members', return_value={'chezmoi': b'fixture'}), \
                 patch.object(state, 'report'), patch.object(Path, 'chmod', side_effect=AssertionError('chmod após publicação')), \
                 patch.dict(os.environ, {'DEVSHELL_APPROVAL': 'ok'}):
                artifacts.apply(plan)
            self.assertEqual((base / 'bin/chezmoi').stat().st_mode & 0o777, 0o755)

    def test_corrupt_cache_reports_path_and_preserves_it_offline_or_online(self):
        artifact, _ = self.packed()
        with tempfile.TemporaryDirectory() as temp, patch.object(artifacts, 'CACHE', Path(temp)):
            cache = Path(temp) / artifact['sha256']
            cache.write_bytes(b'corrompido')
            for offline in ('0', '1'):
                with self.subTest(offline=offline), patch.dict(os.environ, {'DEVSHELL_OFFLINE': offline}):
                    with self.assertRaisesRegex(ValueError, 'cache corrompido') as error:
                        artifacts.download(artifact)
                    self.assertIn(str(cache), str(error.exception))
                    self.assertEqual(cache.read_bytes(), b'corrompido')


class TransactionBoundary(unittest.TestCase):
    def test_sticky_exception_allows_only_system_owned_directories(self):
        from types import SimpleNamespace
        directory = self.home / 'system-sticky'
        directory.mkdir()
        directory.chmod(0o1777)
        target = directory / 'regular'
        target.write_text('unsafe\n')
        target.chmod(0o1666)
        real_stat = Path.stat

        def mapped_root(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path == Path('/'):
                return SimpleNamespace(st_uid=os.getuid(), st_mode=info.st_mode)
            return info

        # Simular o UID raiz do filesystem sem exigir chown ou executar como root.
        with patch.object(Path, 'stat', mapped_root):
            issues = list(state.path_issues(target))
        self.assertTrue(any(i['kind'] == 'permissions' and i['path'] == str(target) for i in issues))
        self.assertFalse(any(i['path'] == str(directory) for i in issues))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.home = base / 'home'
        self.home.mkdir(mode=0o700)
        self.root = base / 'repo'
        (self.root / 'dotfiles/dot_config/devshell').mkdir(parents=True)
        (self.root / 'manifests').mkdir()
        (self.root / 'manifests/packages.tsv').write_text('')
        (self.root / 'dotfiles/dot_zshenv').write_text('new\n')
        (self.root / 'dotfiles/dot_config/devshell/env.sh').write_text('env\n')
        for key, value in {'ROOT': self.root, 'HOME': self.home, 'CONFIG': self.home / '.config', 'STATE': self.home / '.state/devshell'}.items():
            mock = patch.object(state, key, value)
            mock.start()
            self.addCleanup(mock.stop)
        env = {'DEVSHELL_PROFILES': 'minimal', 'DEVSHELL_DISTRO': 'ubuntu', 'DEVSHELL_ADAPTER': 'apt',
               'DEVSHELL_MACHINE': 'x86_64', 'DEVSHELL_LIBC': 'gnu', 'DEVSHELL_JSON': '1',
               'DEVSHELL_REPLACE': '1', 'DEVSHELL_APPROVAL': ''}
        output = patch.object(state, 'report')
        output.start()
        self.addCleanup(output.stop)
        mock = patch.dict(os.environ, env)
        mock.start()
        self.addCleanup(mock.stop)

    def apply(self):
        os.environ['DEVSHELL_APPROVAL'] = state.build_plan()['approval']
        with patch.object(state, 'chezmoi_render'):
            state.apply_configuration()

    def test_version_probe_does_not_write_to_real_home(self):
        binary = self.home / 'fake-uv'
        binary.write_text('#!/bin/sh\ntouch "$HOME/version-probe"\nprintf "uv 0.13.5\\n"\n')
        binary.chmod(0o700)
        with patch.object(state.shutil, 'which', return_value=str(binary)), patch.dict(os.environ, {'HOME': str(self.home)}):
            self.assertEqual(state.command_version('uv'), (0, 13, 5))
        self.assertFalse((self.home / 'version-probe').exists())

    def test_partial_write_failure_restores_existing_file(self):
        target = self.home / '.zshenv'
        target.write_text('original\n')
        target.chmod(0o640)
        real = state.atomic
        writes = 0

        def failing_write(path, *args, **kwargs):
            nonlocal writes
            if path.is_relative_to(state.CONFIG):
                writes += 1
                if writes == 2:
                    raise OSError('disk cheio (fixture)')
            return real(path, *args, **kwargs)

        with patch.object(state, 'atomic', side_effect=failing_write):
            with self.assertRaisesRegex(OSError, 'disk cheio'):
                self.apply()
        self.assertEqual(target.read_text(), 'original\n')
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)
        self.assertFalse((state.STATE / 'latest').exists())
        self.assertFalse((state.CONFIG / 'devshell/env.sh').exists())

    def test_backup_tampering_is_rejected_before_restoring_any_file(self):
        target = self.home / '.zshenv'
        target.write_text('original\n')
        self.apply()
        directory, tx = state.latest_transaction()
        entry = next(e for e in tx['files'] if e['before'])
        (directory / entry['backup']).write_text('corrompido')
        with self.assertRaisesRegex(RuntimeError, 'backup'):
            state.rollback_plan()
        self.assertEqual(target.read_text(), 'new\n')

    def test_missing_backup_reports_recoverable_error_without_traceback(self):
        target = self.home / '.zshenv'
        target.write_text('original\n')
        self.apply()
        directory, tx = state.latest_transaction()
        entry = next(e for e in tx['files'] if e['before'])
        (directory / entry['backup']).unlink()
        with self.assertRaisesRegex(RuntimeError, 'backup ausente ou corrompido'):
            state.rollback_plan()

    def test_rollback_refuses_edit_during_restoration(self):
        self.apply()
        directory, tx = state.latest_transaction()
        victim = Path(tx['files'][-2]['path'])
        original = state.restore_entry
        calls = []

        def edit_during_rollback(directory, entry):
            calls.append(entry['path'])
            original(directory, entry)
            if len(calls) == 1:
                victim.write_text('edição concorrente')

        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        with patch.object(state, 'restore_entry', side_effect=edit_during_rollback):
            with self.assertRaisesRegex(RuntimeError, 'alterado durante'):
                state.rollback()
        self.assertEqual(victim.read_text(), 'edição concorrente')
        self.assertEqual(state.latest_transaction()[1]['status'], 'rolling-back')

    def test_rollback_manifest_cannot_write_outside_managed_paths(self):
        self.apply()
        directory, tx = state.latest_transaction()
        tx['files'][0]['path'] = str(self.home / 'precious')
        (directory / 'manifest.json').write_text(json.dumps(tx))
        with self.assertRaisesRegex(ValueError, 'fora do escopo'):
            state.rollback_plan()
        self.assertFalse((self.home / 'precious').exists())

    def test_rollback_uses_recorded_mode_after_backup_chmod(self):
        target = self.home / '.zshenv'
        target.write_text('original\n')
        target.chmod(0o600)
        self.apply()
        directory, tx = state.latest_transaction()
        entry = next(e for e in tx['files'] if e['before'])
        (directory / entry['backup']).chmod(0o644)
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)

    def test_rollback_refuses_metadata_edits_to_applied_file(self):
        self.apply()
        (self.home / '.zshenv').chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'editado'):
            state.rollback_plan()

    def test_interrupted_rollback_can_resume_without_rewriting_restored_files(self):
        target = self.home / '.zshenv'
        target.write_text('original\n')
        self.apply()
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        original = state.restore_entry
        calls = []

        def interrupted(directory, entry):
            calls.append(entry['path'])
            if len(calls) == 2:
                raise OSError('interrupção simulada')
            original(directory, entry)

        with patch.object(state, 'restore_entry', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'interrupção'):
                state.rollback()
        self.assertEqual(state.latest_transaction()[1]['status'], 'rolling-back')
        restored = calls[0]
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        with patch.object(state, 'restore_entry', wraps=original) as restore:
            state.rollback()
        self.assertNotIn(restored, [call.args[1]['path'] for call in restore.call_args_list])
        self.assertEqual(target.read_text(), 'original\n')
        self.assertFalse((state.STATE / 'latest').exists())

    def test_interrupted_rollback_still_refuses_new_edits(self):
        self.apply()
        directory, tx = state.latest_transaction()
        tx['status'] = 'rolling-back'
        (directory / 'manifest.json').write_text(json.dumps(tx))
        (self.home / '.zshenv').write_text('nova edição')
        with self.assertRaisesRegex(RuntimeError, 'editado'):
            state.rollback_plan()

    def test_doctor_reports_source_update_not_yet_applied(self):
        self.apply()
        (self.root / 'dotfiles/dot_zshenv').write_text('versão nova\n')
        with patch.object(sys, 'argv', ['state.py', 'doctor']), patch.object(state, 'version_issues', return_value=({}, [])), \
             patch.object(artifacts, 'health_issues', return_value=[]), patch.object(state, 'report') as report:
            self.assertEqual(state.main(), 3)
        self.assertTrue(any('não corresponde ao perfil' in issue for issue in report.call_args.args[0]['issues']))

    def test_pending_partial_transaction_can_be_recovered(self):
        target = self.home / '.zshenv'
        target.write_text('original\n')
        self.apply()
        directory, tx = state.latest_transaction()
        tx['status'] = 'pending'
        missing = state.CONFIG / 'devshell/env.sh'
        missing.unlink()
        (directory / 'manifest.json').write_text(json.dumps(tx))
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertEqual(target.read_text(), 'original\n')
        self.assertFalse((state.STATE / 'latest').exists())

    def test_parallel_writer_is_refused(self):
        with state.locked():
            with self.assertRaisesRegex(RuntimeError, 'andamento'):
                self.apply()
        self.assertFalse((self.home / '.zshenv').exists())

    def test_repeated_rollback_restores_previous_transaction(self):
        target = self.home / '.zshenv'
        target.write_text('original\n')
        self.apply()
        (self.root / 'dotfiles/dot_zshenv').write_text('newer\n')
        self.apply()
        for expected in ('new\n', 'original\n'):
            os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
            state.rollback()
            self.assertEqual(target.read_text(), expected)

    def test_hardlinked_target_is_refused(self):
        original = self.home / 'other'
        original.write_text('preservar')
        target = self.home / '.zshenv'
        os.link(original, target)
        with self.assertRaisesRegex(ValueError, 'regular independente'):
            state.build_plan()
        self.assertEqual(original.read_text(), 'preservar')


class RememberedProfiles(unittest.TestCase):
    """R-040: o caminho de falha do apply restaura o registro de perfis."""

    setUp = TransactionBoundary.setUp
    apply = TransactionBoundary.apply

    def test_r040_failed_apply_restores_previous_profiles(self):
        record = state.STATE / 'profiles'
        self.apply()
        self.assertEqual(record.read_text().strip(), 'minimal')
        (self.root / 'dotfiles/dot_zshenv').write_text('outra versão\n')
        real_atomic = state.atomic

        def fail_on_commit(path, content, *args, **kwargs):
            if path.name == 'manifest.json' and b'"committed"' in content:
                raise OSError('falha injetada no commit')
            return real_atomic(path, content, *args, **kwargs)

        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}), patch.object(state, 'atomic', side_effect=fail_on_commit):
            with self.assertRaisesRegex(OSError, 'falha injetada'):
                self.apply()
        self.assertEqual(record.read_text().strip(), 'minimal')

    def test_r040_failed_apply_without_previous_record_removes_it(self):
        record = state.STATE / 'profiles'
        self.apply()
        record.unlink()
        (self.root / 'dotfiles/dot_zshenv').write_text('outra versão\n')
        real_atomic = state.atomic

        def fail_on_commit(path, content, *args, **kwargs):
            if path.name == 'manifest.json' and b'"committed"' in content:
                raise OSError('falha injetada no commit')
            return real_atomic(path, content, *args, **kwargs)

        with patch.object(state, 'atomic', side_effect=fail_on_commit):
            with self.assertRaisesRegex(OSError, 'falha injetada'):
                self.apply()
        self.assertFalse(record.exists())

    def test_r040_rollback_shows_profiles_and_refuses_unsafe_record_before_restoring(self):
        record = state.STATE / 'profiles'
        self.apply()
        (self.root / 'dotfiles/dot_zshenv').write_text('outra versão\n')
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}):
            self.apply()
        plan = state.rollback_plan()[0]
        self.assertEqual(plan['profiles_restore'], 'minimal')
        target = self.home / '.zshenv'
        applied = target.read_text()
        record.unlink()
        record.symlink_to(self.home / 'outro')
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        with self.assertRaises(ValueError):
            state.rollback()
        self.assertEqual(target.read_text(), applied)
        self.assertNotIn('rolling-back', (state.STATE / 'transactions' / (state.STATE / 'latest').read_text() / 'manifest.json').read_text())


class DoctorNextStep(unittest.TestCase):
    """R-044: um próximo passo só, manual primeiro, setup depois, nada sem pendência."""

    def step(self, issues, source='lembrados', profiles='personal'):
        return state.next_step(issues, profiles, source)

    def test_r044_setup_resolves_missing_and_outdated_items(self):
        for issue in ('componente ausente: fzf', 'arquivo esperado ausente: /h/.zshenv',
                      'arquivo esperado não corresponde ao perfil: /h/.zshrc', 'interpretador uv ausente: 3.13.11',
                      'ferramenta uv ausente: ruff: não instalada; use install --component python',
                      'ferramenta uv divergente: ruff: /v: modos inseguros na venv (escrita de grupo/outros); rode ./bin/devshell setup, que corrige'):
            with self.subTest(issue):
                self.assertEqual(self.step([issue]), {'kind': 'setup', 'command': ['./bin/devshell', 'setup'], 'reason': issue})

    def test_r044_manual_issue_comes_first_and_unknown_is_manual(self):
        conflict = 'ferramenta uv conflito: ruff: /h/.local/bin/ruff já existe; se for do uv tool, rode `uv tool uninstall ruff`'
        step = self.step(['componente ausente: fzf', conflict])
        self.assertEqual(step['kind'], 'manual')
        self.assertEqual(step['reason'], conflict)
        for issue in ('extensão Zsh local insegura: x', 'arquivo Zsh compilado não permitido: x', 'algo novo e desconhecido',
                      'ferramenta uv divergente: ruff: /v: pyvenv.cfg ausente; revise e mova a venv para fora de devshell/tools',
                      'componente fora do PATH: chezmoi está em /h/.local/bin; abra uma shell nova ou adicione esse diretório ao PATH',
                      'integridade do componente divergente: /h/.local/bin/pyinit', 'interpretador uv divergente: 3.13.10',
                      'permissões inseguras: /h/.config'):
            with self.subTest(issue):
                self.assertEqual(self.step([issue])['kind'], 'manual')

    def test_r044_no_issue_means_no_step_and_informed_profiles_are_kept(self):
        self.assertIsNone(self.step([]))
        self.assertEqual(self.step(['componente ausente: fzf'], 'informados', 'science')['command'],
                         ['./bin/devshell', 'setup', '--profile', 'science'])


class TransactionHistory(unittest.TestCase):
    """R-004, R-005 e R-006 nas falhas que só um teste unitário consegue injetar."""

    setUp = TransactionBoundary.setUp
    apply = TransactionBoundary.apply

    def make_transactions(self, count):
        for index in range(count):
            (self.root / 'dotfiles/dot_zshenv').write_text(f'versão {index}\n')
            self.apply()

    def prune(self, keep):
        os.environ['DEVSHELL_APPROVAL'] = state.prune_plan(keep)['approval']
        state.prune(keep)

    def transaction_ids(self):
        return sorted(path.name for path in (state.STATE / 'transactions').iterdir())

    def test_r005_interrupted_prune_leaves_only_whole_transactions(self):
        self.make_transactions(4)
        removed = state.remove_private_dir
        calls = []

        def fail_on_second(path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('falha injetada')
            removed(path)

        with patch.object(state, 'remove_private_dir', side_effect=fail_on_second):
            oldest = next(name for name in self.transaction_ids()
                          if json.loads((state.STATE / 'transactions' / name / 'manifest.json').read_text())['previous_latest'] is None)
            with self.assertRaisesRegex(RuntimeError, f'poda incompleta; removidas: {oldest};'):
                self.prune(1)
        for name in self.transaction_ids():
            self.assertTrue((state.STATE / 'transactions' / name / 'manifest.json').is_file())
        self.assertTrue(any((state.STATE / 'pruning').iterdir()))
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        (self.root / 'dotfiles/dot_zshenv').write_text('após falha\n')
        self.apply()
        self.prune(1)
        self.assertEqual(list((state.STATE / 'pruning').iterdir()), [])
        self.assertEqual(len(self.transaction_ids()), 1)

    def test_r005_leftover_without_manifest_is_cleaned_and_unexpected_is_refused(self):
        self.make_transactions(2)
        leftover = state.STATE / 'pruning' / ('a' * 32)
        leftover.mkdir(parents=True, mode=0o700)
        (leftover / '0').write_text('backup restante')
        listing = state.history()
        self.assertEqual([row['id'] for row in listing['cleanup']], ['a' * 32])
        plan = state.prune_plan(1)
        self.assertEqual([row['id'] for row in plan['cleanup']], ['a' * 32])
        self.prune(1)
        self.assertEqual(list((state.STATE / 'pruning').iterdir()), [])
        for name in ('nao-hex', 'b' * 32):
            path = state.STATE / 'pruning' / name
            if name == 'nao-hex':
                path.mkdir(mode=0o700)
            else:
                path.symlink_to(self.home)
            before = sorted(str(item) for item in state.STATE.rglob('*'))
            with self.assertRaisesRegex(ValueError, 'SECURITY'):
                state.prune_plan(1)
            self.assertEqual(sorted(str(item) for item in state.STATE.rglob('*')), before)
            path.unlink() if path.is_symlink() else path.rmdir()

    def test_r005_state_changed_under_lock_removes_nothing(self):
        self.make_transactions(3)
        real_locked = state.locked
        latest = state.latest_name()

        @contextlib.contextmanager
        def locked_after_change():
            with real_locked():
                manifest = state.STATE / 'transactions' / latest / 'manifest.json'
                data = json.loads(manifest.read_text())
                manifest.write_text(json.dumps(data | {'created': '2000-01-01T00:00:00Z'}))
                yield

        os.environ['DEVSHELL_APPROVAL'] = state.prune_plan(1)['approval']
        before = self.transaction_ids()
        with patch.object(state, 'locked', locked_after_change):
            with self.assertRaisesRegex(RuntimeError, 'estado mudou'):
                state.prune(1)
        self.assertEqual(self.transaction_ids(), before)

    def test_r001_wrong_types_in_manifest_become_invalid_entries(self):
        self.make_transactions(2)
        oldest = next(name for name in self.transaction_ids() if name != state.latest_name())
        manifest = state.STATE / 'transactions' / oldest / 'manifest.json'
        for field, value in (('previous_latest', ['x']), ('created', 7)):
            data = json.loads(manifest.read_text())
            original = data.get(field)
            manifest.write_text(json.dumps(data | {field: value}))
            rows = {row['id']: row for row in state.history()['transactions']}
            self.assertEqual(rows[oldest]['status'], 'invalida')
            manifest.write_text(json.dumps(data | {field: original}))

    def test_r004_interrupted_inside_chain_has_specific_message(self):
        self.make_transactions(2)
        oldest = next(name for name in self.transaction_ids() if name != state.latest_name())
        manifest = state.STATE / 'transactions' / oldest / 'manifest.json'
        manifest.write_text(json.dumps(json.loads(manifest.read_text()) | {'status': 'pending'}))
        with self.assertRaisesRegex(ValueError, 'na cadeia, mas não é a atual'):
            state.prune_plan(1)

    def test_r003_warns_when_deleting_only_copy_of_replaced_original(self):
        self.make_transactions(1)
        (self.home / '.zshenv').write_text('editado à mão\n')
        (self.root / 'dotfiles/dot_zshenv').write_text('substitui o editado\n')
        self.apply()
        replaced = state.latest_name()
        self.make_transactions(1)
        warnings = state.prune_plan(1)['warnings']
        self.assertTrue(any(replaced in w and str(self.home / '.zshenv') in w for w in warnings), warnings)

    def test_r006_rollback_ignores_previous_latest_outside_transactions(self):
        self.make_transactions(1)
        directory, _ = state.latest_transaction()
        manifest = directory / 'manifest.json'
        manifest.write_text(json.dumps(json.loads(manifest.read_text()) | {'previous_latest': '../..'}))
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertFalse((state.STATE / 'latest').exists())

    def test_r005_removal_refuses_symlink_swapped_after_plan(self):
        outside = self.home / 'fora'
        outside.write_text('preservar')
        doomed = self.home / 'pruning' / ('c' * 32)
        doomed.mkdir(parents=True)
        (doomed / '0').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'não regular'):
            state.remove_private_dir(doomed)
        self.assertEqual(outside.read_text(), 'preservar')
        self.assertTrue((doomed / '0').is_symlink())

    def test_r004_pruning_never_follows_symlink_inside_transaction(self):
        self.make_transactions(2)
        outside = self.home / 'fora'
        outside.write_text('preservar')
        oldest = next(name for name in self.transaction_ids()
                      if json.loads((state.STATE / 'transactions' / name / 'manifest.json').read_text())['previous_latest'] is None)
        (state.STATE / 'transactions' / oldest / '9').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'SECURITY'):
            state.prune_plan(1)
        self.assertEqual(outside.read_text(), 'preservar')

    def test_r006_rollback_does_not_point_latest_to_unreadable_manifest(self):
        self.make_transactions(2)
        directory, transaction = state.latest_transaction()
        (state.STATE / 'transactions' / transaction['previous_latest'] / 'manifest.json').unlink()
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertFalse((state.STATE / 'latest').exists())
        self.assertEqual(state.latest_transaction(), (None, None))


class PythonToolLocks(unittest.TestCase):
    """R-020, R-023 e R-025: leitura dos locks e classificação das ferramentas."""

    HASH = 'a' * 64

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.home.mkdir(mode=0o700)
        for module, key, value in ((python_tools, 'LOCKS', self.base / 'locks'), (state, 'HOME', self.home)):
            active = patch.object(module, key, value)
            active.start()
            self.addCleanup(active.stop)
        active = patch.dict(os.environ, {'XDG_DATA_HOME': str(self.home / 'data')})
        active.start()
        self.addCleanup(active.stop)
        (self.base / 'locks').mkdir()
        self.spec = {'tool_python': '3.13.11', 'tools': [{'name': 'ruff', 'version': '0.17.3'}]}
        self.dirs = {'UV_TOOL_BIN_DIR': str(self.home / 'bin')}

    def write_lock(self, body, version='3.13'):
        header = f'#    uv --no-config pip compile --universal --python-version {version} --generate-hashes -o x -\n'
        (self.base / 'locks/ruff.txt').write_text(header + body)

    def test_r020_reads_continuations_comments_markers_and_normalizes_names(self):
        self.write_lock(f"""ruff==0.17.3 \\
    --hash=sha256:{self.HASH} \\
    --hash=sha256:{'b' * 64}
    # via -r -
Prompt_Toolkit==3.0.53 ; sys_platform == 'win32' \\
    --hash=sha256:{self.HASH}
""")
        lock = python_tools.read_lock(self.base / 'locks/ruff.txt')
        self.assertEqual(lock['python_version'], '3.13')
        self.assertEqual(lock['requirements']['ruff'], {'version': '0.17.3', 'marker': None})
        self.assertEqual(lock['requirements']['prompt-toolkit']['marker'], "sys_platform == 'win32'")
        self.assertEqual(set(python_tools.locks(self.spec)), {'ruff'})

    def test_r020_refuses_invalid_or_mismatched_locks(self):
        cases = {'sem lock': None, 'sem hash': 'ruff==0.17.3\n', 'sem ==': f'ruff>=0.17 --hash=sha256:{self.HASH}\n',
                 'versão raiz': f'ruff==0.1.0 --hash=sha256:{self.HASH}\n',
                 'duplicado': f'ruff==0.17.3 --hash=sha256:{self.HASH}\nRuff==0.17.3 --hash=sha256:{self.HASH}\n'}
        for label, body in cases.items():
            with self.subTest(label):
                (self.base / 'locks/ruff.txt').unlink(missing_ok=True)
                if body is not None:
                    self.write_lock(body)
                with self.assertRaises(ValueError):
                    python_tools.locks(self.spec)
        self.write_lock(f'ruff==0.17.3 --hash=sha256:{self.HASH}\n', version='3.12')
        with self.assertRaisesRegex(ValueError, 'Python 3.12'):
            python_tools.locks(self.spec)

    def test_r020_no_lock_needed_without_python_tools(self):
        self.assertEqual(python_tools.locks({'tool_python': '3.13.11', 'tools': []}), {})

    def test_r025_states_absent_orphan_link_conflict_and_divergent(self):
        self.write_lock(f'ruff==0.17.3 --hash=sha256:{self.HASH}\n')
        lock = python_tools.locks(self.spec)['ruff']
        venv, link = python_tools.paths('ruff', self.dirs)
        link.parent.mkdir(mode=0o700)

        def state():
            return python_tools.tool_state('ruff', lock, self.dirs, '3.13.11')
        self.assertEqual(state()['state'], 'ausente')
        link.symlink_to(venv / 'bin/ruff')
        self.assertEqual(state()['state'], 'link-orfao')
        link.unlink()
        foreign = self.home / 'uv-tools/ruff/bin/ruff'
        foreign.parent.mkdir(parents=True)
        foreign.write_text('#!/bin/sh\n')
        link.symlink_to(foreign)
        row = state()
        self.assertEqual(row['state'], 'conflito')
        self.assertIn('uv tool uninstall ruff', row['detail'][0])
        link.unlink()
        venv.mkdir(parents=True, mode=0o700)
        row = state()
        self.assertEqual(row['state'], 'divergente')
        self.assertIn('pyvenv.cfg', row['detail'][0])

    def test_r025_symlinked_tools_root_blocks_without_creating_anything(self):
        self.write_lock(f'ruff==0.17.3 --hash=sha256:{self.HASH}\n')
        lock = python_tools.locks(self.spec)['ruff']
        elsewhere = self.base / 'elsewhere'
        elsewhere.mkdir(mode=0o700)
        (self.home / 'data').mkdir(mode=0o700)
        (self.home / 'data/devshell').symlink_to(elsewhere)
        (self.home / 'bin').mkdir(mode=0o700)
        row = python_tools.tool_state('ruff', lock, self.dirs, '3.13.11')
        self.assertEqual(row['state'], 'divergente')
        self.assertEqual(list(elsewhere.iterdir()), [])

    def fake_uv(self, version):
        binary = self.base / 'uv'
        binary.write_text(f'#!/bin/sh\nprintf "uv {version}\\n"\n')
        binary.chmod(0o700)
        return str(binary)

    def test_r021_uv_floor_rises_only_with_python_tools(self):
        old_uv = self.fake_uv('0.13.4')
        with patch.object(artifacts, 'COMPONENT', 'python'), patch.object(artifacts.shutil, 'which', return_value=old_uv), \
                patch.dict(os.environ, {'DEVSHELL_APPROVAL': 'hash'}):
            with self.assertRaisesRegex(ValueError, '0.13.5'):
                artifacts.check({'approval': 'hash', 'spec': {'tools': [{'name': 'ruff'}]}})
            artifacts.check({'approval': 'hash', 'spec': {'tools': []}})
        for components, expected in ((['uv', 'python-tools'], True), (['uv'], False)):
            with self.subTest(components=components), patch.object(state, 'COMPONENTS', components), \
                    patch.object(state.shutil, 'which', return_value=old_uv):
                _, issues = state.version_issues()
                self.assertEqual(any('uv' in issue and '0.13.5' in issue for issue in issues), expected, issues)

    def test_r043_modes_message_only_for_paths_inside_the_venv(self):
        self.write_lock(f'ruff==0.17.3 --hash=sha256:{self.HASH}\n')
        lock = python_tools.locks(self.spec)['ruff']
        venv, link = python_tools.paths('ruff', self.dirs)
        venv.mkdir(parents=True, mode=0o700)
        link.parent.mkdir(mode=0o700)
        for path, expected in ((venv / 'lib/x', 'modos inseguros na venv'), (self.home / 'python/bin/python3', 'revise e mova')):
            with self.subTest(path=path), patch.object(python_tools, 'venv_issues', side_effect=ValueError(f'permissões inseguras: {path}')):
                self.assertIn(expected, python_tools.tool_state('ruff', lock, self.dirs, '3.13.11')['detail'][0])

    def test_r021_uv_environment_drops_active_envs_and_user_uv_settings(self):
        with patch.dict(os.environ, {'VIRTUAL_ENV': '/outra', 'CONDA_PREFIX': '/conda', 'UV_VENV_CLEAR': '1',
                                     'UV_INDEX_URL': 'https://exemplo.invalid', 'PATH': '/usr/bin'}):
            env = python_tools.uv_environment({'UV_PYTHON_INSTALL_DIR': '/p', 'UV_CACHE_DIR': '/c'})
        self.assertNotIn('VIRTUAL_ENV', env)
        self.assertNotIn('CONDA_PREFIX', env)
        self.assertEqual({key for key in env if key.startswith('UV_')}, {'UV_PYTHON_INSTALL_DIR', 'UV_CACHE_DIR'})


class StaticChezmoiSource(unittest.TestCase):
    """Atributos, scripts e templates Chezmoi são recusados antes de executar Chezmoi."""

    def test_repository_sources_are_static(self):
        state.static_sources()

    def test_attribute_words_after_dot_prefix_are_literal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.chezmoiroot').write_text('dotfiles\n')
            (root / 'dotfiles/dot_config/tool').mkdir(parents=True)
            for name in ('dot_modify_probe', 'dot_executable_probe', 'dot_config/tool/config.toml'):
                (root / 'dotfiles' / name).write_text('literal\n')
            with patch.object(state, 'ROOT', root):
                state.static_sources()

    def test_chezmoi_attributes_are_refused_before_rendering(self):
        refused = ['modify_dot_probe', 'create_dot_probe', 'symlink_dot_probe', 'remove_dot_probe',
                   'executable_probe', 'private_dot_probe', 'run_onchange_probe.sh', 'dot_probe.tmpl',
                   'exact_dir/file', 'external_dir/file', '.chezmoiscripts/probe.sh', '.chezmoiignore',
                   'dot_config/nested/modify_probe', 'dot_config/once_probe', 'encrypted_dot_probe',
                   'empty_dot_probe', 'readonly_dot_probe', 'literal_dot_probe', 'before_probe.sh',
                   'after_probe.sh', 'dot_probe.literal', 'dot_probe.age', 'dot_probe.asc']
        for name in refused:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / '.chezmoiroot').write_text('dotfiles\n')
                source = root / 'dotfiles' / name
                source.parent.mkdir(parents=True)
                source.write_text('#!/bin/sh\ntouch executed\n')
                with patch.object(state, 'ROOT', root), patch.object(state.shutil, 'which', return_value='/bin/false'), \
                        patch.object(state.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ValueError, 'não estática'):
                        state.chezmoi_render()
                    run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
