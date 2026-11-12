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

    def test_r040_unsafe_record_refuses_apply_without_creating_transaction(self):
        record = state.STATE / 'profiles'
        self.apply()
        latest = (state.STATE / 'latest').read_text()
        before = sorted(p.name for p in (state.STATE / 'transactions').iterdir())
        record.unlink()
        record.symlink_to(self.home / 'outro')
        (self.root / 'dotfiles/dot_zshenv').write_text('outra versão\n')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.apply()
        self.assertEqual(sorted(p.name for p in (state.STATE / 'transactions').iterdir()), before)
        self.assertEqual((state.STATE / 'latest').read_text(), latest)

    def test_r040_rollback_without_previous_profiles_ignores_unsafe_record(self):
        """Manifesto antigo sem previous_profiles não toca o registro; registro inseguro não bloqueia."""
        record = state.STATE / 'profiles'
        self.apply()
        manifest = state.STATE / 'transactions' / (state.STATE / 'latest').read_text() / 'manifest.json'
        tx = json.loads(manifest.read_text())
        del tx['previous_profiles']
        manifest.write_text(json.dumps(tx))
        outside = self.home / 'outro'
        outside.write_text('personal\n')
        record.unlink()
        record.symlink_to(outside)
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertFalse((self.home / '.zshenv').exists())
        self.assertTrue(record.is_symlink())
        self.assertEqual(outside.read_text(), 'personal\n')
        self.assertIn('rolled-back', manifest.read_text())

    def test_r040_apply_without_changes_replans_under_lock(self):
        self.apply()
        real_build = state.build_plan
        calls = []

        def changing_plan():
            plan = real_build()
            calls.append(plan['approval'])
            if len(calls) > 1:
                plan['approval'] = 'mudou'
            return plan

        os.environ['DEVSHELL_APPROVAL'] = real_build()['approval']
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}), patch.object(state, 'build_plan', side_effect=changing_plan):
            os.environ['DEVSHELL_APPROVAL'] = real_build()['approval']
            with self.assertRaisesRegex(RuntimeError, 'planeje novamente'):
                with patch.object(state, 'chezmoi_render'):
                    state.apply_configuration()
        self.assertEqual((state.STATE / 'profiles').read_text().strip(), 'minimal')

    def latest_manifest(self):
        return json.loads((state.STATE / 'transactions' / (state.STATE / 'latest').read_text() / 'manifest.json').read_text())

    def test_r048_profile_change_without_files_opens_a_transaction(self):
        record = state.STATE / 'profiles'
        self.apply()
        first = (state.STATE / 'latest').read_text()
        registry = json.loads((state.STATE / 'current.json').read_text())
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}), patch.object(state, 'chezmoi_render') as render:
            os.environ['DEVSHELL_APPROVAL'] = state.build_plan()['approval']
            state.apply_configuration()
            render.assert_not_called()
        tx = self.latest_manifest()
        self.assertNotEqual((state.STATE / 'latest').read_text(), first)
        self.assertEqual(tx['status'], 'committed')
        self.assertEqual(tx['files'], [])
        self.assertEqual(tx['previous_latest'], first)
        self.assertEqual(tx['previous_profiles'], 'minimal')
        self.assertEqual(tx['previous_registry'], registry)
        self.assertIn('created', tx)
        self.assertEqual(record.read_text().strip(), 'personal')
        listed = [row['id'] for row in state.history()['transactions']]
        self.assertIn((state.STATE / 'latest').read_text(), listed)
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertEqual(record.read_text().strip(), 'minimal')
        self.assertEqual((state.STATE / 'latest').read_text(), first)

    def test_r048_rollback_with_null_previous_profiles_removes_the_record(self):
        record = state.STATE / 'profiles'
        self.apply()
        first = (state.STATE / 'latest').read_text()
        record.unlink()
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}):
            self.apply()
        self.assertNotEqual((state.STATE / 'latest').read_text(), first)
        self.assertIsNone(self.latest_manifest()['previous_profiles'])
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertFalse(record.exists())

    def test_r048_plan_reports_equivalent_record_as_recorded(self):
        self.apply()
        (state.STATE / 'profiles').write_text('minimal,personal\n')
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}):
            self.assertTrue(state.build_plan()['profiles_recorded'])

    def test_r048_same_or_equivalent_profiles_write_nothing(self):
        self.apply()

        def tree():
            return sorted((str(p), p.read_bytes() if p.is_file() else b'') for p in state.STATE.rglob('*') if p.name != 'lock')
        before = tree()
        self.apply()
        self.assertEqual(tree(), before)
        (state.STATE / 'profiles').write_text('minimal,personal\n')
        before = tree()
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}):
            self.apply()
        self.assertEqual(tree(), before)

    def test_r048_failed_profile_transaction_restores_the_record(self):
        record = state.STATE / 'profiles'
        self.apply()
        first = (state.STATE / 'latest').read_text()
        real_atomic = state.atomic

        def fail_on_commit(path, content, *args, **kwargs):
            if path.name == 'manifest.json' and b'"committed"' in content:
                raise OSError('falha injetada no commit')
            return real_atomic(path, content, *args, **kwargs)

        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}), patch.object(state, 'atomic', side_effect=fail_on_commit):
            with self.assertRaisesRegex(OSError, 'falha injetada'):
                self.apply()
        self.assertEqual(record.read_text().strip(), 'minimal')
        self.assertEqual((state.STATE / 'latest').read_text(), first)
        statuses = {row['id']: row['status'] for row in state.history()['transactions']}
        self.assertEqual(sorted(statuses.values()), ['committed', 'failed-restored'])

    def test_r048_prune_does_not_call_a_profile_only_transaction_the_original_backup(self):
        record = state.STATE / 'profiles'
        record.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        record.write_text('minimal\n')
        # Primeira transação sem arquivos: só perfis (HOME já em dia antes do primeiro apply).
        for target, content in state.desired_files().items():
            Path(target).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            Path(target).write_bytes(content)
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}):
            self.apply()
        first = (state.STATE / 'latest').read_text()
        self.assertEqual(self.latest_manifest()['files'], [])
        (self.root / 'dotfiles/dot_zshenv').write_text('outra versão\n')
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}):
            self.apply()
        plan = state.prune_plan(1)
        self.assertIn(first, [row['id'] for row in plan['transactions'] if row['action'] == 'delete'])
        self.assertFalse(any('antes do primeiro apply' in warning for warning in plan.get('warnings', [])), plan.get('warnings'))

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

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        active = patch.object(state, 'STATE', Path(temporary.name))
        active.start()
        self.addCleanup(active.stop)

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

    def test_r044_informed_profiles_equal_to_remembered_omit_profile(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(state, 'STATE', Path(temporary)):
            (Path(temporary) / 'profiles').write_text('science\n')
            self.assertEqual(self.step(['componente ausente: fzf'], 'informados', 'science')['command'],
                             ['./bin/devshell', 'setup'])
            self.assertEqual(self.step(['componente ausente: fzf'], 'informados', 'minimal,science,science')['command'],
                             ['./bin/devshell', 'setup'])
            self.assertEqual(self.step(['componente ausente: fzf'], 'informados', 'personal')['command'],
                             ['./bin/devshell', 'setup', '--profile', 'personal'])

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

    def managed_venv(self):
        """Venv mínima apontando para um CPython 'gerenciado' em UV_PYTHON_INSTALL_DIR."""
        self.write_lock(f'ruff==0.17.3 --hash=sha256:{self.HASH}\n')
        lock = python_tools.locks(self.spec)['ruff']
        python_dir = self.home / 'data/uv/python'
        cpython = python_dir / 'cpython-3.13.11-linux-x86_64-gnu'
        (cpython / 'bin').mkdir(parents=True, mode=0o700)
        (cpython / 'include/python3.13').mkdir(parents=True, mode=0o700)
        (cpython / 'bin/python3.13').write_text('')
        (cpython / 'bin/python3.13').chmod(0o700)
        (cpython / 'include/python3.13/patchlevel.h').write_text('#define PY_VERSION "3.13.11"\n')
        venv, link = python_tools.paths('ruff', self.dirs)
        (venv / 'bin').mkdir(parents=True, mode=0o700)
        (venv / 'lib/python3.13/site-packages').mkdir(parents=True, mode=0o700)
        (venv / 'pyvenv.cfg').write_text('version_info = 3.13.11\n')
        (venv / 'bin/python').symlink_to(cpython / 'bin/python3.13')
        link.parent.mkdir(mode=0o700)
        for path in (self.home, self.home / 'data', self.home / 'data/uv', python_dir):
            path.chmod(0o700)
        dirs = self.dirs | {'UV_PYTHON_INSTALL_DIR': str(python_dir)}
        return lock, dirs, cpython

    def test_r023_unsafe_managed_python_points_to_interpreter_not_venv(self):
        lock, dirs, cpython = self.managed_venv()
        baseline = python_tools.tool_state('ruff', lock, dirs, '3.13.11')
        self.assertNotIn('CPython gerenciado', ' '.join(baseline['detail']))
        for target in (cpython / 'bin/python3.13', cpython / 'include/python3.13/patchlevel.h', cpython):
            with self.subTest(target=target.name):
                mode = target.stat().st_mode & 0o777
                target.chmod(mode | 0o020)
                try:
                    row = python_tools.tool_state('ruff', lock, dirs, '3.13.11')
                finally:
                    target.chmod(mode)
                self.assertEqual(row['state'], 'divergente')
                detail = row['detail'][0]
                self.assertIn('CPython gerenciado', detail)
                self.assertIn(str(cpython), detail)
                self.assertIn('chmod -R go-w', detail)
                self.assertNotIn('mova a venv', detail)
                self.assertNotIn('modos inseguros na venv', detail)

    def test_r023_unsafe_managed_python_is_manual_in_doctor(self):
        _, dirs, cpython = self.managed_venv()
        (cpython / 'bin/python3').symlink_to('python3.13')
        spec = {'interpreters': ['3.13.11']}
        self.assertEqual(artifacts.interpreter_issues(spec, dirs), [])
        (cpython / 'bin/python3.13').chmod(0o720)
        issues = artifacts.interpreter_issues(spec, dirs)
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].startswith('interpretador uv com caminho inseguro: 3.13.11'), issues)
        self.assertIn('chmod -R go-w', issues[0])
        self.assertEqual(state.next_step(issues, ['minimal'], 'padrão')['kind'], 'manual')

    def test_r022_mode_fix_failure_removes_created_venv(self):
        """D-012: item trocado durante o ajuste de modos (ValueError) também remove a venv criada."""
        venv, link = python_tools.paths('ruff', self.dirs)
        row = {'name': 'ruff', 'state': 'ausente', 'venv': str(venv), 'link': str(link), 'detail': []}

        def fake_run(command, **kwargs):
            (venv / 'bin').mkdir(parents=True, exist_ok=True)
            (venv / 'bin/ruff').write_text('')

        with patch.object(state, 'STATE', self.home / '.state/devshell'), \
                patch.object(python_tools, 'plan_tools', return_value=[row]), \
                patch.object(python_tools.shutil, 'which', return_value='/usr/bin/uv'), \
                patch.object(python_tools, 'commands', return_value=[['uv', 'venv']]), \
                patch.object(python_tools.subprocess, 'run', side_effect=fake_run), \
                patch.object(state, 'drop_group_write_tree', side_effect=ValueError('item trocado durante o ajuste de modo: x')), \
                patch.dict(os.environ, {'DEVSHELL_OFFLINE': '1'}):
            with self.assertRaisesRegex(RuntimeError, 'venv foi removida'):
                python_tools.apply({'spec': {}, 'tools': [row]}, self.dirs | {'UV_PYTHON_INSTALL_DIR': '/p', 'UV_CACHE_DIR': '/c'})
        self.assertFalse(os.path.lexists(venv))
        self.assertFalse(os.path.lexists(link))

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




class StateOwnership(unittest.TestCase):
    """R-047: estado que registra alvos de outra HOME ou de outro XDG_CONFIG_HOME é recusado (incidente do R-046)."""

    FULL = 'personal,science,extras'

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home = self.base / 'H'
        self.other = self.base / 'T'
        for path in (self.home, self.other):
            path.mkdir(mode=0o700)
        self.state = self.home / '.local/state/devshell'

    def env(self, **extra):
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(self.home), 'LANG': 'C.UTF-8'}
        env.update({key: str(value) for key, value in extra.items()})
        return env

    def populate(self, profile, config):
        """Escreve os alvos do perfil em config (sem Chezmoi) e devolve o registro correspondente."""
        script = ('fail(){ echo "$1" >&2; exit 2; }; ROOT=$DEVSHELL_ROOT; source "$ROOT/lib/profiles.sh"; '
                  'resolve_profiles "$1"; DEVSHELL_PROFILES=$1 /usr/bin/python3 -I -c "$2" "$3"')
        code = ('import json,sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); import state\n'
                'reg = {}\n'
                'for target, content in state.desired_files().items():\n'
                '    path = Path(target); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)\n'
                '    path.write_bytes(content); path.chmod(0o600); reg[target] = state.digest(content)\n'
                'print(json.dumps(reg))')
        import subprocess
        result = subprocess.run(['bash', '-c', script, 'x', profile, code + '\n', str(ROOT / 'lib')], check=True,
                                capture_output=True, text=True, env=self.env(DEVSHELL_ROOT=ROOT, XDG_CONFIG_HOME=config))
        return json.loads(result.stdout)

    def apply_real(self, profile=FULL):
        registry = self.populate(profile, self.home / '.config')
        self.state.mkdir(parents=True, mode=0o700)
        for path in (self.home / '.local', self.home / '.local/state'):
            path.chmod(0o700)
        (self.state / 'current.json').write_text(json.dumps(registry))
        return registry

    def devshell(self, *arguments, **extra):
        import subprocess
        return subprocess.run([str(ROOT / 'bin/devshell'), *arguments], check=False, capture_output=True, text=True,
                              env=self.env(**extra), cwd=self.base)

    def tree(self):
        return sorted((str(p.relative_to(self.base)), p.stat().st_mode, p.read_bytes() if p.is_file() else b'')
                      for p in self.base.rglob('*') if not p.is_symlink())

    def assert_foreign(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(str(self.state), result.stderr)
        self.assertIn('outra configuração', result.stderr)

    def test_r047_incident_reproduction_is_refused_without_writing(self):
        self.apply_real()
        self.populate('minimal', self.other)
        before = self.tree()
        plan = self.devshell('plan', '--json', XDG_CONFIG_HOME=self.other)
        self.assert_foreign(plan)
        self.assertIn(str(self.home / '.config'), plan.stderr)
        apply = self.devshell('apply', '--approve', 'a' * 64, XDG_CONFIG_HOME=self.other)
        self.assert_foreign(apply)
        self.assertFalse((self.state / 'profiles').exists())
        self.assertEqual(self.tree(), before)

    def test_r047_every_state_command_is_refused_with_or_without_profile(self):
        self.apply_real()
        self.populate('minimal', self.other)
        before = self.tree()
        commands = [['plan'], ['status'], ['diff'], ['doctor'], ['update'], ['apply', '--approve', 'a' * 64],
                    ['setup', '--dry-run'], ['install', '--component', 'python', '--dry-run'],
                    ['install', '--component', 'devshell', '--dry-run'], ['rollback'], ['rollback', '--prune', '--keep', '1'],
                    ['uninstall', '--component', 'pyinit']]
        for command in commands:
            for profile in ([], ['--profile', 'minimal']):
                if command[0] in ('rollback', 'uninstall') and profile:
                    continue
                with self.subTest(command=command, profile=profile):
                    self.assert_foreign(self.devshell(*command, *profile, XDG_CONFIG_HOME=self.other))
        self.assertEqual(self.tree(), before)

    def test_r047_other_home_with_same_state_is_refused(self):
        self.apply_real()
        other_home = self.base / 'H2'
        other_home.mkdir(mode=0o700)
        result = self.devshell('plan', HOME=other_home, XDG_STATE_HOME=self.home / '.local/state')
        self.assert_foreign(result)

    def test_r047_registry_without_components_or_mixing_roots_is_refused(self):
        registry = self.apply_real()
        components = str(self.home / '.config/devshell/components')
        del registry[components]
        (self.state / 'current.json').write_text(json.dumps(registry))
        self.assert_foreign(self.devshell('plan', '--profile', 'minimal', XDG_CONFIG_HOME=self.other))
        mixed = registry | self.populate('minimal', self.other)
        (self.state / 'current.json').write_text(json.dumps(mixed))
        self.assert_foreign(self.devshell('plan', '--profile', 'minimal', XDG_CONFIG_HOME=self.other))

    def test_r047_foreign_message_comes_before_the_profile_hint(self):
        self.apply_real()
        self.populate('personal', self.other)
        result = self.devshell('plan', XDG_CONFIG_HOME=self.other)
        self.assert_foreign(result)
        self.assertNotIn('nenhum perfil lembrado', result.stderr)

    def test_r047_legitimate_states_are_not_blocked(self):
        self.assertEqual(self.devshell('plan', '--json').returncode, 0)
        registry = self.apply_real('minimal')
        (self.state / 'profiles').write_text('minimal\n')
        self.assertEqual(self.devshell('plan', '--json').returncode, 0)
        self.assertEqual(self.devshell('plan', '--json', XDG_CONFIG_HOME=str(self.home / '.config') + '/').returncode, 0)
        # Dotfile que saiu do checkout não corresponde a nenhum alvo: não é outra configuração.
        removed = registry | {str(self.home / '.config/ferramenta-antiga/config.toml'): 'b' * 64}
        (self.state / 'current.json').write_text(json.dumps(removed))
        self.assertEqual(self.devshell('plan', '--json').returncode, 0)
        (self.state / 'current.json').write_text('{}')
        self.assertEqual(self.devshell('plan', '--json').returncode, 0)

    def test_r047_rollback_list_and_project_are_exempt(self):
        self.apply_real()
        self.populate('minimal', self.other)
        listing = self.devshell('rollback', '--list', XDG_CONFIG_HOME=self.other)
        self.assertEqual(listing.returncode, 0, listing.stderr)
        project = self.devshell('project', 'doctor', '--path', str(self.base), XDG_CONFIG_HOME=self.other)
        self.assertNotIn('outra configuração', project.stderr)

    def test_r047_group_writable_local_does_not_block_before_the_setup_repair(self):
        # D-015: um ~/.local com escrita de grupo (umask 002) é assunto da revisão de permissões do setup.
        (self.home / '.local').mkdir(mode=0o700)
        (self.home / '.local').chmod(0o775)
        result = self.devshell('setup', '--dry-run', '--json', '--profile', 'minimal')
        self.assertNotIn('permissões inseguras', result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.apply_real('minimal')
        (self.home / '.local').chmod(0o775)
        result = self.devshell('setup', '--dry-run', '--json', '--profile', 'minimal')
        self.assertNotIn('outra configuração', result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_r047_removed_dotfile_with_a_target_name_is_not_foreign(self):
        # Um dotfile antigo em CONFIG/x/starship.toml termina como um alvo, mas está dentro da configuração atual.
        registry = self.apply_real('minimal')
        nested = registry | {str(self.home / '.config/ferramenta-antiga/starship.toml'): 'b' * 64,
                             str(self.home / '.config/antigo/.bash_aliases'): 'c' * 64}
        (self.state / 'current.json').write_text(json.dumps(nested))
        result = self.devshell('plan', '--json', '--profile', 'minimal')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_r047_dot_dot_in_xdg_is_unsafe_not_foreign(self):
        self.apply_real()
        result = self.devshell('plan', XDG_CONFIG_HOME=self.home / 'x/../.config')
        self.assertEqual(result.returncode, 2)
        self.assertIn('caminho inseguro', result.stderr)
        self.assertNotIn('outra configuração', result.stderr)



class OrphanRetirement(unittest.TestCase):
    """R-050 e R-055: classificação dos órfãos do registro, sem gravar nada."""

    def setUp(self):
        TransactionBoundary.setUp(self)
        (self.root / 'dotfiles/dot_config/starship.toml').write_text('format = "x"\n')
        (self.root / 'dotfiles/dot_config/nushell').mkdir()
        (self.root / 'dotfiles/dot_config/nushell/config.nu').write_text('# nu\n')
        self.full = ['bash', 'zsh', 'uv', 'chezmoi', 'starship', 'nu']
        active = patch.object(state, 'COMPONENTS', list(self.full))
        active.start()
        self.addCleanup(active.stop)
        self.apply()
        state.COMPONENTS[:] = ['bash', 'zsh', 'uv', 'chezmoi']
        self.starship = self.home / '.config/starship.toml'
        self.nu = self.home / '.config/nushell/config.nu'

    apply = TransactionBoundary.apply

    def retire(self):
        return {row['path']: row for row in state.build_plan()['retire']}

    def write_registry(self, data):
        (state.STATE / 'current.json').write_text(json.dumps(data))

    def test_r050_unchanged_orphan_is_remove_with_snapshot(self):
        rows = self.retire()
        self.assertEqual(rows[str(self.starship)]['action'], 'remove')
        self.assertEqual(rows[str(self.starship)]['before']['sha256'], state.digest(self.starship.read_bytes()))
        self.assertEqual(rows[str(self.nu)]['action'], 'remove')
        self.assertNotIn(str(self.home / '.config/devshell/components'), rows)

    def test_r050_edited_missing_outside_and_unsafe_are_forgotten(self):
        self.starship.write_text('editado por mim\n')
        self.nu.unlink()
        registry = json.loads((state.STATE / 'current.json').read_text())
        registry[str(self.home / '.config/ferramenta-antiga/x.conf')] = 'b' * 64
        self.write_registry(registry)
        rows = self.retire()
        self.assertEqual(rows[str(self.starship)]['action'], 'forget-edited')
        self.assertEqual(rows[str(self.nu)]['action'], 'forget-missing')
        self.assertEqual(rows[str(self.home / '.config/ferramenta-antiga/x.conf')]['action'], 'forget-outside')

    def test_r050_unsafe_cases_are_forget_unsafe_without_exception(self):
        target = self.starship
        cases = {}

        def check(label):
            cases[label] = self.retire()[str(target)]['action']

        content = target.read_bytes()
        target.unlink()
        target.symlink_to(self.home / 'algum-lugar')
        check('symlink')
        target.unlink()
        target.mkdir()
        check('diretório')
        target.rmdir()
        target.write_bytes(content)
        os.link(target, self.home / 'outro-link')
        check('hardlink')
        (self.home / 'outro-link').unlink()
        # Leitura negada (modo 000 para quem não é root): simulada para não depender do usuário do teste.
        real_read = Path.read_bytes

        def denied(path):
            if str(path) == str(target):
                raise PermissionError(13, 'Permission denied', str(path))
            return real_read(path)
        with patch.object(Path, 'read_bytes', denied):
            check('leitura negada')
        # Ancestral só do órfão: ~/.config com escrita de grupo recusaria o plano inteiro, como hoje.
        self.nu.parent.chmod(0o775)
        cases['ancestral com escrita de grupo'] = self.retire()[str(self.nu)]['action']
        self.nu.parent.chmod(0o700)
        # Outro dono: só o arquivo, simulado no stat da classificação (sem root para chown).
        real_lstat = os.lstat

        def foreign_owner(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if str(path) == str(target):
                return os.stat_result((info.st_mode, info.st_ino, info.st_dev, info.st_nlink, info.st_uid + 1,
                                       info.st_gid, info.st_size, int(info.st_atime), int(info.st_mtime), int(info.st_ctime)))
            return info
        with patch.object(state.os, 'lstat', foreign_owner):
            check('outro dono')
        self.assertEqual(len(cases), 6)
        for label, action in cases.items():
            with self.subTest(label):
                self.assertEqual(action, 'forget-unsafe')

    def test_r050_precedence_outside_before_anything_and_no_disk_access(self):
        weird = str(self.home / '.config/fora/fifo')
        registry = json.loads((state.STATE / 'current.json').read_text())
        registry[weird] = 'b' * 64
        self.write_registry(registry)
        real_lstat, real_stat = os.lstat, os.stat

        def guarded(real):
            def call(path, *args, **kwargs):
                if str(path) == weird:
                    raise AssertionError('caminho fora do universo foi consultado no disco')
                return real(path, *args, **kwargs)
            return call
        with patch.object(state.os, 'lstat', guarded(real_lstat)), patch.object(state.os, 'stat', guarded(real_stat)), \
                patch.object(state, 'path_issues', side_effect=lambda p: (
                (_ for _ in ()).throw(AssertionError('path_issues fora do universo')) if str(p) == weird else state_path_issues(p))):
            rows = self.retire()
        self.assertEqual(rows[weird]['action'], 'forget-outside')
        # Editado e inseguro ao mesmo tempo: vale o inseguro (primeiro na ordem).
        self.nu.write_text('editado\n')
        self.nu.parent.chmod(0o775)
        try:
            self.assertEqual(self.retire()[str(self.nu)]['action'], 'forget-unsafe')
        finally:
            self.nu.parent.chmod(0o700)

    def test_r050_retire_list_is_part_of_the_approval(self):
        with_orphans = state.build_plan()['approval']
        state.COMPONENTS[:] = list(self.full)
        without = state.build_plan()['approval']
        state.COMPONENTS[:] = ['bash', 'zsh', 'uv', 'chezmoi']
        self.assertNotEqual(with_orphans, without)
        self.starship.write_text('editado\n')
        self.assertNotEqual(state.build_plan()['approval'], with_orphans)

    def test_r050_read_only_commands_do_not_write(self):
        def tree():
            return sorted((str(p), p.stat().st_mode, p.read_bytes() if p.is_file() else b'')
                          for p in self.home.rglob('*') if not p.is_symlink() and p.name != 'lock')
        before = tree()
        plan = state.build_plan()
        self.assertTrue(plan['retire'])
        with patch.dict(os.environ, {'DEVSHELL_JSON': '0'}), patch('sys.argv', ['state.py', 'diff']), \
                contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            state.main()
        self.assertIn('-format = "x"', out.getvalue())
        self.assertEqual(tree(), before)

    def test_r050_binary_orphan_shows_placeholder_in_diff(self):
        self.starship.write_bytes(b'\xff\xfe')
        registry = json.loads((state.STATE / 'current.json').read_text())
        registry[str(self.starship)] = state.digest(b'\xff\xfe')
        self.write_registry(registry)
        with patch.dict(os.environ, {'DEVSHELL_JSON': '0'}), patch('sys.argv', ['state.py', 'diff']), \
                contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            state.main()
        self.assertIn('(conteúdo binário)', out.getvalue())

    def test_r055_invalid_registry_is_refused(self):
        for label, content in {'lista': '[]', 'número': '3', 'chave relativa': json.dumps({'relativo/x': 'a' * 64}),
                               'valor não texto': json.dumps({str(self.starship): 3}),
                               'hash curto': json.dumps({str(self.starship): 'abc'})}.items():
            with self.subTest(label):
                (state.STATE / 'current.json').write_text(content)
                with self.assertRaisesRegex(ValueError, 'registro inválido'):
                    state.build_plan()


    def apply_tracking_render(self):
        os.environ['DEVSHELL_APPROVAL'] = state.build_plan()['approval']
        with patch.object(state, 'chezmoi_render') as render:
            state.apply_configuration()
        return render

    def registry_now(self):
        return json.loads((state.STATE / 'current.json').read_text())

    def latest_tx(self):
        directory = state.STATE / 'transactions' / (state.STATE / 'latest').read_text()
        return directory, json.loads((directory / 'manifest.json').read_text())

    def test_r051_apply_removes_orphans_with_backup_and_keeps_directories(self):
        content, mode = self.starship.read_bytes(), self.starship.stat().st_mode & 0o777
        self.apply()
        self.assertFalse(self.starship.exists())
        self.assertFalse(self.nu.exists())
        self.assertTrue(self.nu.parent.is_dir())
        registry = self.registry_now()
        self.assertNotIn(str(self.starship), registry)
        self.assertNotIn(str(self.nu), registry)
        directory, tx = self.latest_tx()
        removed = {entry['path']: entry for entry in tx['files'] if entry.get('action') == 'remove'}
        self.assertEqual(set(removed), {str(self.starship), str(self.nu)})
        backup = directory / removed[str(self.starship)]['backup']
        self.assertEqual(backup.read_bytes(), content)
        self.assertEqual(removed[str(self.starship)]['before']['mode'], mode)
        self.assertIsNone(removed[str(self.starship)]['after'])
        self.assertIsNone(removed[str(self.starship)]['applied'])

    def retire_only(self):
        """Perfis já em minimal; um alvo do universo registrado e no disco, sem nada a escrever."""
        self.apply()
        self.starship.write_text('format = "x"\n')
        self.starship.chmod(0o640)
        registry = self.registry_now()
        registry[str(self.starship)] = state.digest(self.starship.read_bytes())
        (state.STATE / 'current.json').write_text(json.dumps(registry))
        self.assertFalse([entry for entry in state.build_plan()['files'] if entry['action'] == 'write'])

    def test_r051_retire_only_plan_opens_transaction_without_chezmoi(self):
        self.retire_only()
        before_latest = (state.STATE / 'latest').read_text()
        render = self.apply_tracking_render()
        render.assert_not_called()
        self.assertNotEqual((state.STATE / 'latest').read_text(), before_latest)
        self.assertFalse(self.starship.exists())
        _, tx = self.latest_tx()
        self.assertEqual(tx['status'], 'committed')

    def test_r051_forget_only_touches_no_file_and_rollback_restores_registry(self):
        self.apply()
        ghost = str(self.home / '.config/nushell/env.nu')
        (self.root / 'dotfiles/dot_config/nushell/env.nu').write_text('# env\n')
        registry = self.registry_now()
        registry[ghost] = 'd' * 64
        (state.STATE / 'current.json').write_text(json.dumps(registry))
        before = self.registry_now()
        self.apply()
        _, tx = self.latest_tx()
        self.assertEqual(tx['files'], [])
        self.assertEqual(tx['forgotten'], [ghost])
        self.assertNotIn(ghost, self.registry_now())
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertEqual(self.registry_now(), before)

    def test_r051_file_changed_after_plan_invalidates_approval(self):
        self.retire_only()
        os.environ['DEVSHELL_APPROVAL'] = state.build_plan()['approval']
        self.starship.write_text('editado depois do plano\n')
        registry = self.registry_now()
        with self.assertRaises(ValueError), patch.object(state, 'chezmoi_render'):
            state.apply_configuration()
        self.assertTrue(self.starship.exists())
        self.assertEqual(self.registry_now(), registry)

    def test_r051_failure_after_first_removal_restores_everything(self):
        registry = self.registry_now()
        real_remove = state.remove_checked
        calls = []

        def fail_second(entry):
            calls.append(entry['path'])
            if len(calls) == 2:
                raise OSError('falha injetada na segunda remoção')
            return real_remove(entry)
        content = {path: path.read_bytes() for path in (self.starship, self.nu)}
        with patch.object(state, 'remove_checked', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'falha injetada'):
                self.apply()
        for path, data in content.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertEqual(self.registry_now(), registry)
        statuses = sorted(row['status'] for row in state.history()['transactions'])
        self.assertIn('failed-restored', statuses)

    def test_r051_bad_backup_removes_nothing(self):
        self.retire_only()
        registry = self.registry_now()
        real_copy = state.shutil.copy2

        def corrupt(source, target, *args, **kwargs):
            result = real_copy(source, target, *args, **kwargs)
            if str(source) == str(self.starship):
                Path(target).write_text('backup corrompido\n')
            return result
        with patch.object(state.shutil, 'copy2', side_effect=corrupt):
            with self.assertRaisesRegex(RuntimeError, 'backup'):
                self.apply_tracking_render()
        self.assertTrue(self.starship.exists())
        self.assertEqual(self.registry_now(), registry)

    def test_r051_parent_swapped_by_symlink_is_refused(self):
        self.apply()
        # Órfão em diretório próprio, para trocar só ele.
        self.nu.write_text('# nu\n')
        registry = self.registry_now()
        registry[str(self.nu)] = state.digest(self.nu.read_bytes())
        (state.STATE / 'current.json').write_text(json.dumps(registry))
        elsewhere = self.home / 'outro-lugar'
        elsewhere.mkdir(mode=0o700)
        (elsewhere / 'config.nu').write_text('# nu\n')
        real_copy = state.shutil.copy2

        def swap(source, target, *args, **kwargs):
            result = real_copy(source, target, *args, **kwargs)
            if str(source) == str(self.nu):
                moved = self.home / 'nushell-original'
                self.nu.parent.rename(moved)
                self.nu.parent.symlink_to(elsewhere, target_is_directory=True)
            return result
        with patch.object(state.shutil, 'copy2', side_effect=swap):
            with self.assertRaises((OSError, ValueError, RuntimeError)):
                self.apply_tracking_render()
        self.assertTrue((elsewhere / 'config.nu').exists())

    def test_r052_rollback_restores_removed_files_and_registry(self):
        registry = self.registry_now()
        content, mode = self.starship.read_bytes(), self.starship.stat().st_mode & 0o777
        self.apply()
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertEqual(self.starship.read_bytes(), content)
        self.assertEqual(self.starship.stat().st_mode & 0o777, mode)
        self.assertEqual(self.registry_now(), registry)

    def test_r052_rollback_refuses_recreated_and_edited_path(self):
        self.apply()
        self.starship.write_text('recriado e editado\n')
        with self.assertRaisesRegex(RuntimeError, 'editado'):
            state.rollback_plan()

    def test_r052_rollback_after_dotfile_left_checkout_points_to_backup(self):
        self.apply()
        directory, _ = self.latest_tx()
        (self.root / 'dotfiles/dot_config/starship.toml').unlink()
        with self.assertRaises(ValueError) as error:
            state.rollback_plan()
        self.assertIn(str(directory), str(error.exception))
        self.assertIn(str(self.starship), str(error.exception))

    def test_r052_prune_lists_and_warns_about_only_copy_of_retired_file(self):
        self.apply()
        retired_tx = (state.STATE / 'latest').read_text()
        (self.root / 'dotfiles/dot_zshenv').write_text('outra versão\n')
        self.apply()
        self.assertIn(retired_tx, [row['id'] for row in state.history()['transactions']])
        plan = state.prune_plan(1)
        self.assertTrue(any(retired_tx in warning and 'retirad' in warning for warning in plan['warnings']), plan['warnings'])


    def test_r053_doctor_reports_orphans_as_setup_step(self):
        plan = state.build_plan()
        issues = state.orphan_issues(plan)
        self.assertIn(f'arquivo gerenciado fora dos perfis: {self.starship} (remove)', issues)
        step = state.next_step(issues, 'minimal', 'informados')
        self.assertEqual(step['kind'], 'setup')

    def test_r053_summary_never_marks_dotfiles_up_to_date_with_orphans(self):
        import setup as guided
        plan = state.build_plan()
        forget_only = dict(plan, files=[dict(entry, action='unchanged', conflict=False) for entry in plan['files']],
                           retire=[dict(row, action='forget-missing') for row in plan['retire']])
        inspection = {'permissions': [], 'native_command': [], 'user_components': [], 'blockers': []}
        with patch.object(guided, 'cli_json', return_value=(forget_only, '')), \
                patch.object(guided.fs, 'read_own_regular', return_value='minimal\n'), \
                patch.dict(os.environ, {'DEVSHELL_PROFILES': 'minimal'}):
            summary = guided.summary(inspection)
        dotfiles = next(step for step in summary['steps'] if step['step'] == 'dotfiles')
        self.assertNotEqual(dotfiles['status'], 'em dia')
        self.assertIn('só saem do registro', dotfiles['detail'])
        self.assertFalse(summary['nothing_to_do'])

    def test_r053_universe_orphans_enter_the_permission_review(self):
        import setup as guided
        with patch.object(guided.artifacts, 'BIN', self.home / '.local/bin'), \
                patch.object(guided.artifacts, 'DATA', self.home / '.local/share'), \
                patch.object(guided.artifacts, 'CACHE', self.home / '.cache/devshell'):
            paths = guided.target_paths()
        self.assertIn(self.nu, paths)
        self.assertIn(self.starship, paths)


    def test_r050_permission_error_while_inspecting_is_forget_unsafe(self):
        real = state.path_issues

        def denied(path):
            if str(path) == str(self.nu):
                raise PermissionError(13, 'Permission denied', str(self.nu.parent))
            return real(path)
        with patch.object(state, 'path_issues', side_effect=denied):
            self.assertEqual(self.retire()[str(self.nu)]['action'], 'forget-unsafe')

    def test_r052_interrupted_before_backup_can_still_be_rolled_back(self):
        """Morte entre o manifesto e a cópia do backup: pending, arquivos intactos e sem backup."""
        self.retire_only()
        registry = self.registry_now()
        copying = []
        real_atomic = state.atomic

        class Killed(BaseException):
            pass

        def copy(*args, **kwargs):
            copying.append(True)
            raise Killed()

        def atomic(path, *args, **kwargs):
            if copying:
                raise Killed()
            return real_atomic(path, *args, **kwargs)
        with patch.object(state.shutil, 'copy2', side_effect=copy), patch.object(state, 'atomic', side_effect=atomic):
            with self.assertRaises(Killed):
                self.apply_tracking_render()
        _, tx = self.latest_tx()
        self.assertEqual(tx['status'], 'pending')
        self.assertTrue(self.starship.exists())
        plan = state.rollback_plan()[0]
        os.environ['DEVSHELL_APPROVAL'] = plan['approval']
        state.rollback()
        self.assertTrue(self.starship.exists())
        self.assertEqual(self.registry_now(), registry)

    def test_r053_orphan_without_repair_stays_out_of_the_permission_review(self):
        import setup as guided
        moved = self.home / 'nushell-real'
        self.nu.parent.rename(moved)
        self.nu.parent.symlink_to(moved, target_is_directory=True)
        with patch.object(guided.artifacts, 'BIN', self.home / '.local/bin'), \
                patch.object(guided.artifacts, 'DATA', self.home / '.local/share'), \
                patch.object(guided.artifacts, 'CACHE', self.home / '.cache/devshell'):
            paths = guided.target_paths()
        self.assertNotIn(self.nu, paths)
        self.assertIn(self.starship, paths)
        self.assertEqual(self.retire()[str(self.nu)]['action'], 'forget-unsafe')

    def test_r051_removal_refuses_a_file_swapped_after_the_content_check(self):
        self.retire_only()
        registry = self.registry_now()
        real_rename = state.os.rename
        calls = []

        def rename(source, target, *args, **kwargs):
            if not calls:
                calls.append(target)
                # Um editor salva por rename logo antes da retirada.
                replacement = self.starship.with_name('.editor-tmp')
                replacement.write_text('salvo agora pelo editor\n')
                real_rename(replacement, self.starship)
            return real_rename(source, target, *args, **kwargs)
        with patch.object(state.os, 'rename', side_effect=rename):
            with self.assertRaises(RuntimeError):
                self.apply_tracking_render()
        self.assertEqual(self.starship.read_text(), 'salvo agora pelo editor\n')
        self.assertEqual(self.registry_now(), registry)


state_path_issues = state.path_issues



class Uninstall(unittest.TestCase):
    """R-060 a R-064: desinstalação com prova de dono, em HOME temporária."""

    def setUp(self):
        import launcher
        import uninstall
        self.launcher, self.uninstall = launcher, uninstall
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home = self.base / 'home'
        self.home.mkdir(mode=0o700)
        data, cache, state_dir = self.home / '.local/share', self.home / '.cache/devshell/artifacts', self.home / '.local/state/devshell'
        patches = [(state, 'HOME', self.home), (state, 'CONFIG', self.home / '.config'), (state, 'STATE', state_dir),
                   (artifacts, 'DATA', data), (artifacts, 'CACHE', cache), (artifacts, 'BIN', self.home / '.local/bin'),
                   (launcher, 'TARGET', self.home / '.local/bin/devshell'), (launcher, 'RECEIPT', state_dir / 'launcher.json'),
                   (launcher, 'BACKUPS', state_dir / 'launcher-backups'), (state, 'COMPONENTS', ['bash', 'zsh', 'uv', 'chezmoi'])]
        for module, key, value in patches:
            active = patch.object(module, key, value)
            active.start()
            self.addCleanup(active.stop)
        env = {'XDG_DATA_HOME': str(data), 'DEVSHELL_PROFILES': 'minimal', 'DEVSHELL_JSON': '1', 'DEVSHELL_APPROVAL': '',
               'DEVSHELL_MACHINE': 'x86_64', 'DEVSHELL_LIBC': 'gnu', 'DEVSHELL_OFFLINE': '1'}
        active = patch.dict(os.environ, env)
        active.start()
        self.addCleanup(active.stop)
        for name in ('XDG_BIN_HOME', 'UV_TOOL_BIN_DIR', 'UV_PYTHON_INSTALL_DIR'):
            if name in os.environ:
                active = patch.dict(os.environ)
                active.start()
                self.addCleanup(active.stop)
                del os.environ[name]
        self.data, self.cache, self.state_dir = data, cache, state_dir
        self.artifacts = []
        active = patch.object(uninstall, 'load_artifacts', side_effect=lambda: list(self.artifacts))
        active.start()
        self.addCleanup(active.stop)

    def write(self, path, content, mode=0o644):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(content)
        path.chmod(mode)
        return path

    def actions(self, component):
        return {item['path']: item['action'] for item in self.uninstall.plan(component)['items']}

    def tarball(self, members):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for name, data in members.items():
                info = tarfile.TarInfo('repo-1.0/' + name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def plugin(self, name, members, cached=True):
        content = self.tarball(members)
        sha = state.digest(content)
        self.artifacts.append({'component': 'plugins', 'name': name, 'arch': 'any', 'libc': 'any', 'format': 'tar.gz',
                               'sha256': sha, 'version': '1', 'url': 'https://github.com/x/y'})
        if cached:
            self.write(self.cache / sha, content)
        root = self.data / 'devshell/plugins' / name
        for relative, data in members.items():
            self.write(root / relative, data)
        return root

    def receipt(self, component, files, destination, artifacts_sha=()):
        self.write(self.state_dir / 'install-receipts' / f'{component}.json', json.dumps(
            {'version': 1, 'component': component, 'destination': str(destination), 'files': files,
             'artifacts': list(artifacts_sha)}).encode(), 0o600)

    def tree(self):
        return sorted((str(p), p.lstat().st_mode, p.read_bytes() if p.is_file() and not p.is_symlink() else b'')
                      for p in self.home.rglob('*'))

    def test_r060_excluded_and_unknown_components_are_refused(self):
        for component in ('uv', 'chezmoi', 'nu', 'tudo', 'all'):
            with self.subTest(component), self.assertRaises(ValueError):
                self.uninstall.plan(component)

    def test_r061_devshell_removes_only_generated_bytes_and_lists_original_backup(self):
        for path, (content, mode) in self.launcher.contents().items():
            self.write(path, content, mode)
        self.assertEqual(set(self.actions('devshell').values()), {'remove'})
        self.launcher.TARGET.write_text('#!/bin/sh\necho meu\n')
        self.assertEqual(self.actions('devshell')[str(self.launcher.TARGET)], 'manual')
        backup = self.write(self.launcher.BACKUPS / ('a' * 32) / '0', b'original do usuario\n', 0o600)
        self.write(self.launcher.BACKUPS / ('a' * 32) / 'manifest.json', json.dumps(
            {'status': 'complete', 'completed': [str(self.launcher.TARGET)],
             'plan': {'files': [{'path': str(self.launcher.TARGET), 'backup': '0', 'before': {'sha256': 'x'}}]}}).encode(), 0o600)
        items = {item['path']: item for item in self.uninstall.plan('devshell')['items']}
        self.assertEqual(items[str(backup)]['action'], 'manual')
        self.assertIn('cp', items[str(backup)]['reason'])

    def test_r061_pyinit_by_manifest_or_receipt(self):
        current, older = b'#!/bin/sh\n# pyinit atual\n', b'#!/bin/sh\n# pyinit antigo\n'
        self.artifacts.append({'component': 'pyinit', 'arch': 'any', 'libc': 'any', 'format': 'raw', 'binary': 'pyinit',
                               'sha256': state.digest(current), 'version': '1', 'url': 'https://github.com/x/y'})
        target = self.write(artifacts.BIN / 'pyinit', current, 0o755)
        self.assertEqual(self.actions('pyinit')[str(target)], 'remove')
        target.write_bytes(older)
        self.assertEqual(self.actions('pyinit')[str(target)], 'manual')
        self.receipt('pyinit', {'pyinit': state.digest(older)}, artifacts.BIN)
        self.assertEqual(self.actions('pyinit')[str(target)], 'remove')

    def test_r061_plugins_with_receipt_cache_or_neither(self):
        root = self.plugin('hl', {'hl.zsh': b'# hl\n', 'highlighters/main/main.zsh': b'# main\n'})
        files = {str(root / 'hl.zsh'), str(root / 'highlighters/main/main.zsh')}
        self.assertEqual({p for p, a in self.actions('plugins').items() if a == 'remove'}, files)
        (root / 'hl.zsh').write_text('# editado\n')
        self.assertEqual(self.actions('plugins')[str(root / 'hl.zsh')], 'manual')
        (root / 'hl.zsh').write_text('# hl\n')
        for cached in self.cache.iterdir():
            cached.unlink()
        with patch.object(artifacts, 'download', side_effect=AssertionError('o plano não pode baixar')):
            self.assertEqual(set(self.actions('plugins').values()), {'manual'})
            self.receipt('plugins', {'hl/hl.zsh': state.digest(b'# hl\n'),
                                     'hl/highlighters/main/main.zsh': state.digest(b'# main\n')}, self.data / 'devshell/plugins')
            self.assertEqual({p for p, a in self.actions('plugins').items() if a == 'remove'}, files)

    def test_r062_receipt_escaping_the_destination_is_ignored(self):
        outside = self.write(self.home / 'importante.txt', b'meu\n')
        for bad in ({'../../../importante.txt': state.digest(b'meu\n')}, {str(outside): state.digest(b'meu\n')}):
            with self.subTest(bad):
                self.receipt('plugins', bad, self.data / 'devshell/plugins')
                self.assertNotIn(str(outside), [p for p, a in self.actions('plugins').items() if a == 'remove'])
        self.receipt('plugins', {'hl/x.zsh': 'curto'}, self.data / 'devshell/plugins')
        self.uninstall.plan('plugins')

    def test_r061_symlink_and_hardlink_are_manual(self):
        root = self.plugin('hl', {'hl.zsh': b'# hl\n', 'b.zsh': b'# b\n'})
        (root / 'hl.zsh').unlink()
        (root / 'hl.zsh').symlink_to(self.home / 'fora.zsh')
        os.link(root / 'b.zsh', self.home / 'b-link')
        actions = self.actions('plugins')
        self.assertEqual(actions[str(root / 'hl.zsh')], 'manual')
        self.assertEqual(actions[str(root / 'b.zsh')], 'manual')

    def test_r060_plan_writes_nothing_and_hash_follows_the_list(self):
        root = self.plugin('hl', {'hl.zsh': b'# hl\n'})
        before = self.tree()
        first = self.uninstall.plan('plugins')
        self.assertEqual(self.tree(), before)
        (root / 'hl.zsh').write_text('# editado\n')
        self.assertNotEqual(self.uninstall.plan('plugins')['approval'], first['approval'])

    def test_r060_warns_when_component_is_in_remembered_profiles(self):
        self.plugin('hl', {'hl.zsh': b'# hl\n'})
        self.write(self.state_dir / 'profiles', b'personal\n', 0o600)
        self.assertTrue(any('reinstal' in warning for warning in self.uninstall.plan('plugins')['warnings']))
        self.write(self.state_dir / 'profiles', b'science\n', 0o600)
        self.assertTrue(any('python-tools' in warning or 'reinstal' in warning
                            for warning in self.uninstall.plan('python')['warnings']))

    def leftover_venv(self, name='b' * 32):
        """Resto de uma desinstalação interrompida: uma venv inteira, provada pelo inventário."""
        venv = self.venv_with_record()
        leftover = self.data / 'devshell/uninstalling' / name
        leftover.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        venv.rename(leftover)
        return leftover, {'ruff': {'requirements': {'ruff': {'version': '0.17.3', 'marker': None}}}}

    def test_r060_leftovers_of_an_interrupted_uninstall_appear_in_the_plan(self):
        leftover, locks = self.leftover_venv()
        strange = self.write(self.data / 'devshell/uninstalling/estranho', b'x')
        with patch.object(python_tools, 'locks', return_value=locks):
            items = {item['path']: item['action'] for item in self.uninstall.plan('python')['items']}
        self.assertEqual(items[str(leftover)], 'remove')
        self.assertEqual(items[str(strange)], 'manual')

    def venv_with_record(self, extra=None):
        venv = self.data / 'devshell/tools/ruff'
        site = venv / 'lib/python3.13/site-packages'
        module = self.write(site / 'ruff/__init__.py', b'# ruff\n')
        executable = self.write(venv / 'bin/ruff', b'#!/x/python\n', 0o755)
        self.write(venv / 'pyvenv.cfg', b'version_info = 3.13.11\n')
        (venv / 'bin/python').symlink_to(self.home / 'cpython/bin/python3.13')
        (venv / 'lib64').symlink_to('lib')
        info = site / 'ruff-0.17.3.dist-info'
        self.write(info / 'METADATA', b'Name: ruff\nVersion: 0.17.3\n')
        rows = [f'ruff/__init__.py,{python_tools.record_hash(module.read_bytes())},7',
                f'../../../bin/ruff,{python_tools.record_hash(executable.read_bytes())},12',
                f'ruff-0.17.3.dist-info/METADATA,{python_tools.record_hash((info / "METADATA").read_bytes())},30',
                'ruff-0.17.3.dist-info/RECORD,,']
        self.write(info / 'RECORD', ('\n'.join(rows) + '\n').encode())
        self.write(site / 'ruff/__pycache__/__init__.cpython-313.pyc', b'pyc')
        if extra:
            self.write(venv / extra, b'meu arquivo\n')
        return venv

    def test_r061_venv_inventory_rejects_any_file_outside_the_record(self):
        lock = {'requirements': {'ruff': {'version': '0.17.3', 'marker': None}}}
        venv = self.venv_with_record()
        ok, reason, digest_ok = self.uninstall.inventory(venv, lock)
        self.assertTrue(ok, reason)
        for extra in ('lib/python3.13/site-packages/meu.pth', 'bin/meu-script', 'share/jupyter/x.json',
                      'lib/python3.13/site-packages/ruff/extra.py'):
            with self.subTest(extra):
                (venv / extra).parent.mkdir(parents=True, exist_ok=True)
                (venv / extra).write_text('meu\n')
                self.assertFalse(self.uninstall.inventory(venv, lock)[0])
                (venv / extra).unlink()
        (venv / 'lib/python3.13/site-packages/ruff/__init__.py').write_text('# editado\n')
        self.assertFalse(self.uninstall.inventory(venv, lock)[0])
        self.assertTrue(digest_ok)

    def test_r061_python_plan_uses_the_whole_manifest_and_inventory(self):
        venv = self.venv_with_record()
        link_dir = self.home / '.local/bin'
        link_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        (link_dir / 'ruff').symlink_to(venv / 'bin/ruff')
        lock = {'requirements': {'ruff': {'version': '0.17.3', 'marker': None}}}
        with patch.object(python_tools, 'locks', return_value={'ruff': lock}), \
                patch.object(python_tools, 'venv_issues', return_value=[]):
            actions = self.actions('python')
            self.assertEqual(actions[str(venv)], 'remove')
            self.assertEqual(actions[str(link_dir / 'ruff')], 'remove')
            self.write(venv / 'bin/meu-script', b'x')
            actions = self.actions('python')
            self.assertEqual(actions[str(venv)], 'manual')
        with patch.object(python_tools, 'locks', return_value={'ruff': lock}), \
                patch.object(python_tools, 'venv_issues', return_value=[f'permissões inseguras: {venv}/bin']):
            item = next(item for item in self.uninstall.plan('python')['items'] if item['path'] == str(venv))
            self.assertEqual(item['action'], 'manual')
            self.assertIn('setup', item['reason'])


    def install_plugin(self, members, approval='h'):
        content = self.tarball(members)
        sha = state.digest(content)
        self.write(self.cache / sha, content)
        artifact = {'component': 'plugins', 'name': 'hl', 'arch': 'any', 'libc': 'any', 'format': 'tar.gz',
                    'sha256': sha, 'version': '1', 'url': 'https://github.com/x/y'}
        self.artifacts[:] = [artifact]
        plan = {'operation': 'install-plugins', 'artifacts': [artifact], 'destination': str(self.data / 'devshell/plugins'),
                'approval': approval}
        with patch.object(artifacts, 'COMPONENT', 'plugins'), patch.dict(os.environ, {'DEVSHELL_APPROVAL': approval}), \
                contextlib.redirect_stdout(io.StringIO()):
            artifacts.apply(plan)
        return sha

    def test_r062_install_writes_a_private_receipt_with_every_file(self):
        sha = self.install_plugin({'hl.zsh': b'# hl\n', 'highlighters/main/main.zsh': b'# main\n'})
        receipt = self.state_dir / 'install-receipts/plugins.json'
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
        data = json.loads(receipt.read_text())
        self.assertEqual(data['version'], 1)
        self.assertEqual(data['destination'], str(self.data / 'devshell/plugins'))
        self.assertEqual(data['files'], {'hl/hl.zsh': state.digest(b'# hl\n'),
                                         'hl/highlighters/main/main.zsh': state.digest(b'# main\n')})
        self.assertEqual(data['artifacts'], [sha])
        # Com o recibo, o plano prova tudo mesmo sem o cache.
        for cached in self.cache.iterdir():
            cached.unlink()
        self.assertEqual(set(self.actions('plugins').values()), {'remove'})

    def test_r062_install_without_changes_rewrites_a_missing_receipt(self):
        self.install_plugin({'hl.zsh': b'# hl\n'})
        receipt = self.state_dir / 'install-receipts/plugins.json'
        receipt.unlink()
        self.install_plugin({'hl.zsh': b'# hl\n'})
        self.assertTrue(receipt.exists())

    def test_r062_failed_install_writes_no_receipt(self):
        real_atomic = state.atomic

        def fail_second(path, *args, **kwargs):
            if path.name == 'main.zsh':
                raise OSError('falha injetada')
            return real_atomic(path, *args, **kwargs)
        with patch.object(state, 'atomic', side_effect=fail_second), self.assertRaises(OSError):
            self.install_plugin({'hl.zsh': b'# hl\n', 'highlighters/main/main.zsh': b'# main\n'})
        self.assertFalse((self.state_dir / 'install-receipts/plugins.json').exists())


    def approve(self, component):
        planned = self.uninstall.plan(component)
        with patch.dict(os.environ, {'DEVSHELL_APPROVAL': planned['approval']}):
            return self.uninstall.apply(planned)

    def test_r063_plugins_removes_proven_files_and_empty_dirs_keeps_user_files(self):
        self.install_plugin({'hl.zsh': b'# hl\n', 'highlighters/main/main.zsh': b'# main\n'})
        root = self.data / 'devshell/plugins/hl'
        result = self.approve('plugins')
        self.assertEqual(result['removed'], 2)
        self.assertFalse(root.exists())
        self.assertTrue((self.data / 'devshell/plugins').is_dir())
        self.assertFalse((self.state_dir / 'install-receipts/plugins.json').exists())
        self.assertIn('install --component plugins', result['message'])

    def test_r063_user_file_keeps_its_directory(self):
        self.install_plugin({'hl.zsh': b'# hl\n', 'highlighters/main/main.zsh': b'# main\n'})
        mine = self.write(self.data / 'devshell/plugins/hl/highlighters/meu.zsh', b'meu\n')
        self.approve('plugins')
        self.assertTrue(mine.exists())
        self.assertFalse((self.data / 'devshell/plugins/hl/highlighters/main').exists())
        self.assertFalse((self.data / 'devshell/plugins/hl/hl.zsh').exists())

    def test_r063_stale_approval_removes_nothing(self):
        self.install_plugin({'hl.zsh': b'# hl\n'})
        planned = self.uninstall.plan('plugins')
        (self.data / 'devshell/plugins/hl/hl.zsh').write_text('# editado\n')
        before = self.tree()
        with patch.dict(os.environ, {'DEVSHELL_APPROVAL': planned['approval']}), self.assertRaises((ValueError, RuntimeError)):
            self.uninstall.apply(planned)
        self.assertEqual(self.tree(), before)
        with patch.dict(os.environ, {'DEVSHELL_APPROVAL': 'outro'}), self.assertRaises(ValueError):
            self.uninstall.apply(self.uninstall.plan('plugins'))

    def test_r063_failure_midway_leaves_whole_items_and_next_plan_continues(self):
        self.install_plugin({'a.zsh': b'# a\n', 'b.zsh': b'# b\n'})
        real = state.remove_checked
        calls = []

        def fail_second(entry):
            calls.append(entry['path'])
            if len(calls) == 2:
                raise OSError('falha injetada')
            return real(entry)
        with patch.object(state, 'remove_checked', side_effect=fail_second), self.assertRaises(OSError):
            self.approve('plugins')
        remaining = {p for p, a in self.actions('plugins').items() if a == 'remove'}
        self.assertEqual(len(remaining), 1)
        self.approve('plugins')
        self.assertFalse((self.data / 'devshell/plugins/hl').exists())

    def test_r063_firacode_keeps_user_fonts_and_refreshes_the_cache(self):
        dest = self.data / 'fonts/FiraCodeNerdFont'
        font = self.write(dest / 'FiraCodeNerdFontMono-Regular.ttf', b'fonte')
        self.receipt('firacode', {'FiraCodeNerdFontMono-Regular.ttf': state.digest(b'fonte')}, dest)
        mine = self.write(dest / 'MinhaFonte.ttf', b'minha')
        calls = []
        with patch.object(self.uninstall.shutil, 'which', return_value='/usr/bin/fc-cache'), \
                patch.object(self.uninstall.subprocess, 'run', side_effect=lambda command, **kw: calls.append(command)):
            self.approve('firacode')
        self.assertFalse(font.exists())
        self.assertTrue(mine.exists())
        self.assertEqual(calls, [['fc-cache', '-f', str(dest)]])

    def test_r063_devshell_removes_launcher_and_receipt(self):
        for path, (content, mode) in self.launcher.contents().items():
            self.write(path, content, mode)
        self.approve('devshell')
        self.assertFalse(self.launcher.TARGET.exists())
        self.assertFalse(self.launcher.RECEIPT.exists())

    def python_ready(self):
        venv = self.venv_with_record()
        cpython = self.write(self.home / 'cpython/bin/python3.13', b'interpretador')
        link_dir = self.home / '.local/bin'
        link_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        (link_dir / 'ruff').symlink_to(venv / 'bin/ruff')
        lock = {'requirements': {'ruff': {'version': '0.17.3', 'marker': None}}}
        return venv, link_dir / 'ruff', cpython, lock

    def test_r063_venv_goes_through_uninstalling_and_keeps_the_cpython(self):
        venv, link, cpython, lock = self.python_ready()
        renames = []
        real_rename = self.uninstall.os.rename

        def track(source, target, *args, **kwargs):
            renames.append(str(target))
            return real_rename(source, target, *args, **kwargs)
        with patch.object(python_tools, 'locks', return_value={'ruff': lock}), \
                patch.object(python_tools, 'venv_issues', return_value=[]), \
                patch.object(self.uninstall.os, 'rename', side_effect=track):
            self.approve('python')
        self.assertFalse(venv.exists())
        self.assertFalse(os.path.lexists(link))
        self.assertTrue(cpython.exists())
        self.assertTrue(any('/devshell/uninstalling/' in target for target in renames))
        self.assertEqual(list((self.data / 'devshell/uninstalling').iterdir()), [])

    def test_r063_venv_changed_after_rename_goes_back(self):
        venv, link, cpython, lock = self.python_ready()
        real_inventory = self.uninstall.inventory
        calls = []

        def changed(path, lock_data):
            ok, reason, digest = real_inventory(path, lock_data)
            # Só a reconferência depois de renomear (dentro de uninstalling/) vê a venv mudada.
            if '/devshell/uninstalling/' in str(path):
                calls.append(path)
                return ok, reason, 'outro'
            return ok, reason, digest
        with patch.object(python_tools, 'locks', return_value={'ruff': lock}), \
                patch.object(python_tools, 'venv_issues', return_value=[]), \
                patch.object(self.uninstall, 'inventory', side_effect=changed), self.assertRaises(RuntimeError):
            self.approve('python')
        self.assertEqual(len(calls), 1)
        self.assertTrue((venv / 'pyvenv.cfg').exists())
        self.assertEqual(list((self.data / 'devshell/uninstalling').iterdir()), [])

    def test_r063_leftovers_are_cleaned_by_the_approved_apply(self):
        leftover, locks = self.leftover_venv()
        with patch.object(python_tools, 'locks', return_value=locks):
            self.approve('python')
        self.assertFalse(leftover.exists())


    def test_r061_rejected_or_unproven_leftover_is_manual(self):
        lock = {'requirements': {'ruff': {'version': '0.17.3', 'marker': None}}}
        venv = self.venv_with_record()
        leftover = self.data / 'devshell/uninstalling' / ('c' * 32)
        leftover.parent.mkdir(parents=True, mode=0o700)
        venv.rename(leftover)
        with patch.object(python_tools, 'locks', return_value={'ruff': lock}):
            self.assertEqual(self.actions('python')[str(leftover)], 'remove')
            self.write(leftover / 'bin/meu-script', b'meu')
            self.assertEqual(self.actions('python')[str(leftover)], 'manual')
            rejected = self.data / 'devshell/uninstalling' / ('rejected-' + 'd' * 32)
            rejected.mkdir()
            self.assertEqual(self.actions('python')[str(rejected)], 'manual')

    def test_r061_link_stays_when_the_venv_stays(self):
        venv, link, cpython, lock = self.python_ready()
        with patch.object(python_tools, 'locks', return_value={'ruff': lock}), \
                patch.object(python_tools, 'venv_issues', return_value=['metadados ilegíveis: x']):
            actions = self.actions('python')
        self.assertEqual(actions[str(venv)], 'manual')
        self.assertEqual(actions[str(link)], 'manual')
        self.write(venv / 'bin/meu', b'x')
        with patch.object(python_tools, 'locks', return_value={'ruff': lock}), \
                patch.object(python_tools, 'venv_issues', return_value=[]):
            self.assertEqual(self.actions('python')[str(link)], 'manual')

    def test_r061_custom_paths_produce_a_warning(self):
        with patch.dict(os.environ, {'UV_TOOL_BIN_DIR': str(self.home / 'bin-proprio')}):
            self.assertTrue(any('caminhos' in warning for warning in self.uninstall.plan('python')['warnings']))
        self.assertFalse(any('caminhos' in warning for warning in self.uninstall.plan('pyinit')['warnings']))

    def test_r061_inventory_edge_cases_are_manual(self):
        lock = {'requirements': {'ruff': {'version': '0.17.3', 'marker': None}}}
        venv = self.venv_with_record()
        site = venv / 'lib/python3.13/site-packages'
        foreign = self.write(site / 'outro-1.0.dist-info/METADATA', b'Name: outro\nVersion: 1.0\n')
        self.write(site / 'outro-1.0.dist-info/RECORD', b'')
        self.assertFalse(self.uninstall.inventory(venv, lock)[0])
        foreign.parent.joinpath('RECORD').unlink()
        foreign.unlink()
        foreign.parent.rmdir()
        record = site / 'ruff-0.17.3.dist-info/RECORD'
        original = record.read_bytes()
        record.write_bytes(original + b'../../../../fora.txt,,\n')
        self.assertFalse(self.uninstall.inventory(venv, lock)[0])
        record.write_bytes(original)
        (venv / 'bin/atalho').symlink_to('/usr/bin/env')
        self.assertFalse(self.uninstall.inventory(venv, lock)[0])
        (venv / 'bin/atalho').unlink()
        self.write(venv / 'bin/activate_meu.sh', b'meu')
        self.assertFalse(self.uninstall.inventory(venv, lock)[0])
        (venv / 'bin/activate_meu.sh').unlink()
        hidden = self.write(site / 'privado/x.py', b'x')
        hidden.parent.chmod(0o000)
        try:
            with patch.object(self.uninstall.os, 'walk', side_effect=lambda *a, **k: (_ for _ in ()).throw(PermissionError(13, 'negado'))):
                self.assertFalse(self.uninstall.inventory(venv, lock)[0])
        finally:
            hidden.parent.chmod(0o700)

    def test_r063_refuses_recursive_removal_without_symlink_protection(self):
        leftover, locks = self.leftover_venv('e' * 32)
        with patch.object(python_tools, 'locks', return_value=locks), \
                patch.object(self.uninstall.shutil.rmtree, 'avoids_symlink_attacks', False), self.assertRaises(RuntimeError):
            self.approve('python')
        self.assertTrue(leftover.exists())

    def test_r061_corrupt_cache_and_foreign_receipt_leave_files_manual(self):
        root = self.plugin('hl', {'hl.zsh': b'# hl\n'})
        for cached in self.cache.iterdir():
            cached.write_bytes(b'corrompido')
        self.assertEqual(self.actions('plugins')[str(root / 'hl.zsh')], 'manual')
        for receipt in ({'version': 2}, {'destination': str(self.home / 'outro')}):
            data = {'version': 1, 'component': 'plugins', 'destination': str(self.data / 'devshell/plugins'),
                    'files': {'hl/hl.zsh': state.digest(b'# hl\n')}, 'artifacts': []} | receipt
            self.write(self.state_dir / 'install-receipts/plugins.json', json.dumps(data).encode(), 0o600)
            with self.subTest(receipt):
                self.assertEqual(self.actions('plugins')[str(root / 'hl.zsh')], 'manual')

    def test_r062_failed_font_cache_writes_no_receipt(self):
        content = b'fonte'
        artifact = {'component': 'firacode', 'arch': 'any', 'libc': 'any', 'format': 'zip', 'sha256': 'f' * 64,
                    'version': '1', 'url': 'https://github.com/x/y'}
        dest = self.data / 'fonts/FiraCodeNerdFont'
        plan = {'operation': 'install-firacode', 'artifacts': [artifact], 'destination': str(dest), 'approval': 'h',
                'commands': [['fc-cache', '-f', str(dest)]]}
        with patch.object(artifacts, 'COMPONENT', 'firacode'), patch.dict(os.environ, {'DEVSHELL_APPROVAL': 'h'}), \
                patch.object(artifacts, 'download', return_value=content), \
                patch.object(artifacts, 'members', return_value={'FiraCodeNerdFontMono-Regular.ttf': content}), \
                patch.object(artifacts.shutil, 'which', return_value='/usr/bin/fc-cache'), \
                patch.object(artifacts.subprocess, 'run', side_effect=artifacts.subprocess.CalledProcessError(1, 'fc-cache')), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(artifacts.subprocess.CalledProcessError):
            artifacts.apply(plan)
        self.assertFalse((self.state_dir / 'install-receipts/firacode.json').exists())



class ChainRollback(unittest.TestCase):
    """R-070: rollback --all, com a cadeia inteira conferida antes de qualquer gravação."""

    def setUp(self):
        TransactionBoundary.setUp(self)
        (self.root / 'dotfiles/dot_config/starship.toml').write_text('format = "x"\n')
        self.full = ['bash', 'zsh', 'uv', 'chezmoi', 'starship']
        active = patch.object(state, 'COMPONENTS', list(self.full))
        active.start()
        self.addCleanup(active.stop)
        self.initial = self.home_tree()
        self.apply()                                   # A: perfis completos
        self.ids = [self.latest()]
        (self.root / 'dotfiles/dot_zshenv').write_text('nova versão\n')
        self.apply()                                   # B: dotfile alterado
        self.ids.append(self.latest())
        state.COMPONENTS[:] = ['bash', 'zsh', 'uv', 'chezmoi']
        self.apply()                                   # C: retira o starship.toml
        self.ids.append(self.latest())
        with patch.dict(os.environ, {'DEVSHELL_PROFILES': 'personal'}):
            self.apply()                               # D: só perfis
        self.ids.append(self.latest())
        os.environ['DEVSHELL_APPROVAL'] = ''

    apply = TransactionBoundary.apply

    def latest(self):
        return (state.STATE / 'latest').read_text()

    def home_tree(self):
        return sorted((str(p.relative_to(self.home)), p.read_bytes() if p.is_file() else b'')
                      for p in self.home.rglob('*') if '.state' not in p.parts and not p.is_dir())

    def manifest(self, name):
        return state.STATE / 'transactions' / name / 'manifest.json'

    def edit_manifest(self, name, change):
        data = json.loads(self.manifest(name).read_text())
        change(data)
        self.manifest(name).write_text(json.dumps(data))

    def run_all(self):
        plan = state.chain_rollback_plan()
        os.environ['DEVSHELL_APPROVAL'] = plan['approval']
        reports = []
        with patch.object(state, 'report', side_effect=reports.append):
            state.chain_rollback()
        return reports

    def test_r070_plan_lists_the_chain_newest_first_without_writing(self):
        before = sorted(str(p) for p in state.STATE.rglob('*'))
        plan = state.chain_rollback_plan()
        self.assertEqual([row['id'] for row in plan['transactions']], list(reversed(self.ids)))
        self.assertEqual(sorted(str(p) for p in state.STATE.rglob('*')), before)
        oldest = plan['transactions'][-1]
        self.assertTrue(any(row['path'].endswith('.zshenv') and row['to'] == 'remover' for row in oldest['files']))
        self.assertIn('profiles_restore', plan['transactions'][0])
        (self.home / '.zshenv').write_text('nova versão\n')
        self.assertEqual(state.chain_rollback_plan()['approval'], plan['approval'])
        self.edit_manifest(self.ids[0], lambda data: data.update(created='2020-01-01T00:00:00Z'))
        self.assertNotEqual(state.chain_rollback_plan()['approval'], plan['approval'])

    def test_r070_apply_returns_the_home_to_before_the_first_transaction(self):
        reports = self.run_all()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]['restored_transactions'], 4)
        self.assertEqual(self.home_tree(), self.initial)
        self.assertFalse((state.STATE / 'latest').exists())
        self.assertFalse((state.STATE / 'profiles').exists())
        self.assertEqual(json.loads((state.STATE / 'current.json').read_text()), {})

    def test_r070_edit_in_the_middle_is_found_before_any_write(self):
        (self.home / '.zshenv').write_text('editado por mim\n')
        before = sorted((str(p), p.read_bytes() if p.is_file() else b'') for p in self.home.rglob('*'))
        with self.assertRaises((RuntimeError, ValueError)) as error:
            state.chain_rollback_plan()
        self.assertIn('.zshenv', str(error.exception))
        self.assertIn(self.ids[1], str(error.exception))
        self.assertEqual(sorted((str(p), p.read_bytes() if p.is_file() else b'') for p in self.home.rglob('*')), before)

    def test_r070_mode_only_change_says_mode(self):
        (self.home / '.zshenv').chmod(0o644)
        with self.assertRaisesRegex((RuntimeError, ValueError), 'modo alterado'):
            state.chain_rollback_plan()

    def test_r070_missing_backup_is_refused(self):
        data = json.loads(self.manifest(self.ids[1]).read_text())
        entry = next(e for e in data['files'] if e['path'].endswith('.zshenv'))
        (state.STATE / 'transactions' / self.ids[1] / entry['backup']).unlink()
        with self.assertRaisesRegex((RuntimeError, ValueError), 'backup'):
            state.chain_rollback_plan()

    def test_r070_pruned_chain_warns_and_still_undoes_what_remains(self):
        import shutil as sh
        sh.rmtree(state.STATE / 'transactions' / self.ids[0])
        plan = state.chain_rollback_plan()
        self.assertEqual(len(plan['transactions']), 3)
        self.assertTrue(any('podad' in warning for warning in plan['warnings']))
        self.run_all()
        self.assertFalse((state.STATE / 'latest').exists())

    def test_r070_invalid_chain_and_missing_latest_are_errors_not_nothing_to_do(self):
        (state.STATE / 'transactions' / self.ids[0] / 'intruso').write_text('x')
        with self.assertRaisesRegex(ValueError, 'inválida'):
            state.chain_rollback_plan()
        (state.STATE / 'transactions' / self.ids[0] / 'intruso').unlink()
        (state.STATE / 'latest').unlink()
        with self.assertRaisesRegex(ValueError, 'latest'):
            state.chain_rollback_plan()

    def test_r070_interrupted_states(self):
        self.edit_manifest(self.ids[3], lambda data: data.update(status='pending'))
        state.chain_rollback_plan()
        self.edit_manifest(self.ids[3], lambda data: data.update(status='committed'))
        self.edit_manifest(self.ids[1], lambda data: data.update(status='pending'))
        with self.assertRaisesRegex(ValueError, 'interrompida'):
            state.chain_rollback_plan()
        for status in ('rolled-back', 'failed-restored'):
            with self.subTest(status):
                self.edit_manifest(self.ids[1], lambda data, s=status: data.update(status=s))
                with self.assertRaisesRegex(ValueError, status):
                    state.chain_rollback_plan()

    def test_r070_old_manifests_without_applied_or_profiles(self):
        def strip(data):
            data.pop('previous_profiles', None)
            for entry in data['files']:
                entry.pop('applied', None)
        self.edit_manifest(self.ids[0], strip)
        plan = state.chain_rollback_plan()
        self.assertEqual(plan['transactions'][-1]['profiles_restore'], 'desconhecidos')
        self.run_all()
        self.assertEqual(self.home_tree(), self.initial)

    def test_r070_failure_midway_keeps_undone_and_next_plan_continues(self):
        real = state.undo_transaction
        calls = []

        def fail_third(*args):
            calls.append(args)
            if len(calls) == 3:
                raise OSError('falha injetada')
            return real(*args)
        with patch.object(state, 'undo_transaction', side_effect=fail_third), self.assertRaises(RuntimeError):
            self.run_all()
        self.assertEqual(json.loads(self.manifest(self.ids[3]).read_text())['status'], 'rolled-back')
        remaining = state.chain_rollback_plan()['transactions']
        self.assertEqual([row['id'] for row in remaining], [self.ids[1], self.ids[0]])
        self.run_all()
        self.assertEqual(self.home_tree(), self.initial)

    def test_r070_single_rollback_is_unchanged(self):
        os.environ['DEVSHELL_APPROVAL'] = state.rollback_plan()[0]['approval']
        state.rollback()
        self.assertEqual(self.latest(), self.ids[2])



    def test_r070_dangling_or_malformed_latest_is_an_error(self):
        for value in ('f' * 32, 'lixo'):
            with self.subTest(value):
                (state.STATE / 'latest').write_text(value)
                with self.assertRaisesRegex(ValueError, 'latest'):
                    state.chain_rollback_plan()

    def test_r070_cycle_in_the_chain_is_an_error(self):
        self.edit_manifest(self.ids[3], lambda data: data.update(previous_latest=self.ids[3]))
        with self.assertRaisesRegex(ValueError, 'ciclo'):
            state.chain_rollback_plan()

    def test_r070_failure_message_counts_what_was_undone(self):
        real = state.undo_transaction
        calls = []

        def fail_second(*args):
            calls.append(args)
            if len(calls) == 2:
                raise OSError('falha injetada')
            return real(*args)
        with patch.object(state, 'undo_transaction', side_effect=fail_second), \
                self.assertRaisesRegex(RuntimeError, '1 transação'):
            self.run_all()


class LeaveHelpers(unittest.TestCase):
    """R-071, R-072 e R-074: resumo, o que fica e a remoção opcional do estado."""

    def setUp(self):
        import leave
        self.leave = leave
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name) / 'home'
        self.home.mkdir(mode=0o700)
        self.state_dir = self.home / '.local/state/devshell'
        for module, key, value in ((state, 'HOME', self.home), (state, 'STATE', self.state_dir),
                                   (state, 'CONFIG', self.home / '.config'),
                                   (artifacts, 'DATA', self.home / '.local/share'),
                                   (artifacts, 'CACHE', self.home / '.cache/devshell/artifacts'),
                                   (artifacts, 'BIN', self.home / '.local/bin')):
            active = patch.object(module, key, value)
            active.start()
            self.addCleanup(active.stop)

    def plans(self, uninstall_items, chain, errors=()):
        def fake(*arguments):
            if arguments[0] == 'rollback':
                return (None, 'devshell: arquivo editado após aplicação') if 'rollback' in errors else ({'transactions': chain}, '')
            component = arguments[2]
            if component in errors:
                return None, f'devshell: falha em {component}'
            return {'items': uninstall_items.get(component, []), 'warnings': []}, ''
        return patch.object(self.leave, 'cli_json', side_effect=fake)

    def test_r071_summary_lists_only_steps_with_work_in_order(self):
        items = {'python': [{'action': 'remove', 'path': '/v'}], 'devshell': [{'action': 'remove', 'path': '/l'}],
                 'plugins': [{'action': 'manual', 'path': '/p'}]}
        with self.plans(items, [{'id': 'a' * 32, 'files': []}]):
            summary = self.leave.summary(purge=False)
        self.assertEqual([step['step'] for step in summary['steps']], ['uninstall python', 'uninstall devshell', 'rollback --all'])
        self.assertEqual(summary['blockers'], [])

    def test_r071_every_failing_plan_is_a_blocker_before_any_question(self):
        with self.plans({}, [], errors=('rollback', 'plugins')):
            summary = self.leave.summary(purge=False)
        self.assertEqual(len(summary['blockers']), 2)
        self.assertTrue(any('editado' in blocker for blocker in summary['blockers']))
        self.assertTrue(any('plugins' in blocker for blocker in summary['blockers']))

    def make_state(self, status='rolled-back'):
        manifest = json.dumps({'status': status, 'files': [], 'previous_latest': None, 'previous_registry': {}})
        for name, content in (('transactions/' + 'a' * 32 + '/manifest.json', manifest), ('launcher-backups/x/0', '{}'),
                              ('permission-repairs/r.json', '{}'), ('install-receipts/plugins.json', '{}'),
                              ('current.json', '{}'), ('profiles', 'minimal\n')):
            path = self.state_dir / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_text(content)
        return self.state_dir

    def test_r074_purge_is_offered_only_after_the_whole_chain(self):
        self.make_state()
        (self.state_dir / 'latest').write_text('a' * 32)
        plan = self.leave.purge_plan()
        self.assertFalse(plan['offered'])
        self.assertIn('latest', plan['reason'])
        (self.state_dir / 'latest').unlink()
        plan = self.leave.purge_plan()
        self.assertTrue(plan['offered'])
        self.assertIn('transactions', plan['contents'])
        self.assertGreater(plan['bytes'], 0)

    def test_r074_purge_removes_only_the_state_directory(self):
        self.make_state()
        cache = self.home / '.cache/devshell/artifacts/x'
        cache.parent.mkdir(parents=True, mode=0o700)
        cache.write_text('pacote')
        sibling = self.home / '.local/state/outro-programa'
        sibling.mkdir(mode=0o700)
        plan = self.leave.purge_plan()
        with patch.dict(os.environ, {'DEVSHELL_APPROVAL': plan['approval']}):
            self.leave.purge(plan)
        self.assertFalse(self.state_dir.exists())
        self.assertTrue(cache.exists())
        self.assertTrue(sibling.exists())
        self.assertEqual([p.name for p in self.state_dir.parent.iterdir()], ['outro-programa'])

    def test_r074_purge_refuses_symlink_and_stale_approval(self):
        target = self.home / 'elsewhere'
        target.mkdir(mode=0o700)
        (target / 'importante').write_text('x')
        self.state_dir.parent.mkdir(parents=True, mode=0o700)
        self.state_dir.symlink_to(target, target_is_directory=True)
        self.assertFalse(self.leave.purge_plan()['offered'])
        self.state_dir.unlink()
        self.make_state()
        plan = self.leave.purge_plan()
        (self.state_dir / 'novo').write_text('x')
        with patch.dict(os.environ, {'DEVSHELL_APPROVAL': plan['approval']}), self.assertRaises((ValueError, RuntimeError)):
            self.leave.purge(plan)
        self.assertTrue(self.state_dir.exists())
        self.assertTrue((target / 'importante').exists())

    def test_r072_remains_lists_what_stays(self):
        self.make_state()
        with self.plans({'python': [{'action': 'manual', 'path': '/venv-minha', 'reason': 'arquivo meu'}]}, []):
            remains = self.leave.remains()
        text = ' '.join(remains)
        self.assertIn(str(self.state_dir), text)
        self.assertIn('/venv-minha', text)
        self.assertIn('./bin/devshell', text)
        self.assertIn('CPython', text)


    def test_r074_purge_is_refused_with_transactions_outside_the_chain(self):
        for status in ('committed', 'pending'):
            with self.subTest(status):
                self.make_state(status)
                plan = self.leave.purge_plan()
                self.assertFalse(plan['offered'])
        self.make_state()
        (self.state_dir / 'transactions' / ('a' * 32) / 'manifest.json').write_text('{}')
        self.assertFalse(self.leave.purge_plan()['offered'])

    def test_r074_failed_removal_reports_where_the_state_went(self):
        self.make_state()
        plan = self.leave.purge_plan()
        with patch.dict(os.environ, {'DEVSHELL_APPROVAL': plan['approval']}), \
                patch.object(self.leave.shutil, 'rmtree', side_effect=OSError('falha')), \
                self.assertRaisesRegex(RuntimeError, 'devshell-purge'):
            self.leave.purge(plan)
        self.assertTrue(any('devshell-purge' in line for line in self.leave.remains_paths()))

    def test_r074_purge_plan_warns_about_the_launcher_original(self):
        self.make_state()
        self.assertTrue(any('lançador' in warning for warning in self.leave.purge_plan()['warnings']))


if __name__ == '__main__':
    unittest.main()
