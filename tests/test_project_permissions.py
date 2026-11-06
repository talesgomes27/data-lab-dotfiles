"""Reparo de permissões: somente fixtures privadas, nunca a HOME real."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
os.environ.setdefault('DEVSHELL_ROOT', str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DEVSHELL_COMPONENTS', 'bash zsh uv chezmoi')
os.environ.setdefault('DEVSHELL_COMPONENT', 'uv')
import project
import setup as guided
import state


class ProjectPermissions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'home'
        self.target = self.home / 'work/project'
        (self.target / '.venv/bin').mkdir(parents=True)
        (self.target / '.venv/pyvenv.cfg').write_text('fixture\n')
        for name in ('python', 'python3'):
            (self.target / '.venv/bin' / name).symlink_to(sys.executable)
        self.paths = [self.home / 'work', self.target, self.target / '.venv', self.target / '.venv/bin']
        for path in self.paths:
            path.chmod(0o775)
        for key, value in {'HOME': self.home, 'STATE': self.home / '.state/devshell'}.items():
            active = patch.object(state, key, value)
            active.start()
            self.addCleanup(active.stop)

    def test_unowned_paths_block_all_repairs(self):
        with patch.object(os, 'getuid', return_value=os.getuid() + 1):
            plan = project.inspect_project(self.target)
            self.assertTrue(plan['blockers'])
            with self.assertRaisesRegex(ValueError, 'correção manual'):
                project.repair(plan)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o775 for path in self.paths))
        self.assertFalse(state.STATE.exists())

    def test_partial_failure_records_original_modes_and_completed_paths(self):
        plan = project.inspect_project(self.target)
        original = guided.repair_permission
        calls = []

        def fail_second(issue):
            if calls:
                raise OSError('fixture failure')
            calls.append(issue['path'])
            original(issue)

        with patch.object(guided, 'repair_permission', side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, 'reparo incompleto.*registro'):
                project.repair(plan)
        records = list((state.STATE / 'permission-repairs').glob('*.json'))
        self.assertEqual(len(records), 1)
        record = json.loads(records[0].read_text())
        self.assertEqual(record['status'], 'partial')
        self.assertEqual(record['completed'], [str(self.paths[0])])
        self.assertTrue(all(i['from_mode'] == '0775' for i in record['plan']['permissions']))
        self.assertEqual(self.paths[0].stat().st_mode & 0o777, 0o755)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o775 for path in self.paths[1:]))

    def test_source_change_invalidates_review_before_any_write(self):
        plan = project.inspect_project(self.target)
        changed_root = self.base / 'changed-source'
        for directory in ('bin', 'lib', 'manifests', 'profiles'):
            shutil.copytree(state.ROOT / directory, changed_root / directory)
        with (changed_root / 'lib/project.py').open('a') as stream:
            stream.write('\n# source changed after review\n')
        with patch.object(state, 'ROOT', changed_root):
            with self.assertRaisesRegex(ValueError, 'mudou após a revisão'):
                project.repair(plan)
        self.assertFalse(state.STATE.exists())
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o775 for path in self.paths))


if __name__ == '__main__':
    unittest.main()
