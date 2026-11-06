"""Permissões de setup: fixtures privadas, sem acesso à HOME real."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
os.environ.setdefault('DEVSHELL_ROOT', str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DEVSHELL_COMPONENTS', 'bash zsh uv chezmoi')
os.environ.setdefault('DEVSHELL_COMPONENT', 'uv')
import state
import artifacts
import setup as guided


class PermissionReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir(mode=0o700)
        for module, key, value in [
            (state, 'HOME', self.home), (state, 'CONFIG', self.home / '.config'),
            (state, 'STATE', self.home / '.local/state/devshell'),
            (artifacts, 'DATA', self.home / '.local/share'),
            (artifacts, 'CACHE', self.home / '.cache/devshell/artifacts'),
            (artifacts, 'BIN', self.home / '.local/bin'),
        ]:
            active = patch.object(module, key, value)
            active.start()
            self.addCleanup(active.stop)
        active = patch.object(state, 'COMPONENTS', ['bash', 'zsh', 'uv', 'chezmoi', 'nu', 'python-tools'])
        active.start()
        self.addCleanup(active.stop)
        env = {'UV_PYTHON_INSTALL_DIR': str(self.home / '.local/share/uv/python'),
               'UV_TOOL_DIR': str(self.home / '.local/share/uv/tools'),
               'UV_TOOL_BIN_DIR': str(self.home / '.local/bin'),
               'UV_CACHE_DIR': str(self.home / '.cache/uv')}
        active = patch.dict(os.environ, env)
        active.start()
        self.addCleanup(active.stop)

    def unsafe_paths(self):
        paths = [self.home / '.local', self.home / '.local/bin', self.home / '.config/nushell']
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o775)
        return paths

    def test_all_permission_issues_are_collected_before_changing_anything(self):
        paths = self.unsafe_paths()
        issues = guided.permission_review()
        self.assertEqual({issue['path'] for issue in issues}, {str(path) for path in paths})
        self.assertTrue(all(issue['repairable'] for issue in issues))
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o775 for path in paths))

    def test_repair_changes_only_reviewed_paths_without_recursion(self):
        paths = self.unsafe_paths()
        unrelated = self.home / '.local/unrelated'
        unrelated.mkdir()
        unrelated.chmod(0o777)
        guided.repair_permissions(guided.permission_review())
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o755 for path in paths))
        self.assertEqual(unrelated.stat().st_mode & 0o777, 0o777)

    def test_symlink_is_blocked_and_never_repaired(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        outside.chmod(0o775)
        (self.home / '.config').symlink_to(outside, target_is_directory=True)
        issues = guided.permission_review()
        self.assertTrue(any(issue['kind'] == 'symlink' and not issue['repairable'] for issue in issues))
        with self.assertRaises(ValueError):
            guided.repair_permissions(issues)
        self.assertEqual(outside.stat().st_mode & 0o777, 0o775)

    def test_replaced_inode_invalidates_approval_before_first_chmod(self):
        paths = self.unsafe_paths()
        issues = guided.permission_review()
        target = paths[-1]
        target.rename(target.with_name('old'))
        target.mkdir(mode=0o775)
        target.chmod(0o775)
        with self.assertRaisesRegex(ValueError, 'mudou'):
            guided.repair_permissions(issues)
        self.assertEqual(paths[0].stat().st_mode & 0o777, 0o775)

    def test_descriptor_check_refuses_inode_swapped_during_open(self):
        self.unsafe_paths()
        target = self.home / '.config/nushell'
        issue = next(i for i in guided.permission_review() if i['path'] == str(target))
        real_open = os.open

        def replaced_open(path, flags, *args, **kwargs):
            if Path(path) == target:
                target.rename(target.with_name('anterior'))
                target.mkdir(mode=0o775)
                target.chmod(0o775)
            return real_open(path, flags, *args, **kwargs)

        with patch.object(guided.os, 'open', side_effect=replaced_open):
            with self.assertRaisesRegex(ValueError, 'mudou após revisão'):
                guided.repair_permission(issue)
        self.assertEqual(target.stat().st_mode & 0o777, 0o775)

    def test_hardlinked_dotfile_is_not_a_chmod_target(self):
        target = self.home / '.zshenv'
        target.write_text('privado')
        target.chmod(0o664)
        os.link(target, self.home / 'other')
        issues = guided.permission_review()
        self.assertTrue(any(not issue['repairable'] for issue in issues))
        with self.assertRaises(ValueError):
            guided.repair_permissions(issues)
        self.assertEqual(target.stat().st_mode & 0o777, 0o664)

    def test_external_ancestor_outside_explicit_xdg_scope_is_blocked(self):
        shared = Path(self.temp.name) / 'shared'
        shared.mkdir()
        shared.chmod(0o777)
        with patch.object(state, 'CONFIG', shared / 'config'):
            issues = guided.permission_review()
        issue = next(issue for issue in issues if issue['path'] == str(shared))
        self.assertFalse(issue['repairable'])


if __name__ == '__main__':
    unittest.main()
