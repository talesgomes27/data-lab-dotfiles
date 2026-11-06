"""Fixtures artificiais; testes offline da fronteira de escrita e de arquivos tar."""
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


if __name__ == '__main__':
    unittest.main()
