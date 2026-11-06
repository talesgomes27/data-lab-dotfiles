"""Falhas de backup e instalação do lançador em HOME descartável."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
os.environ.setdefault('DEVSHELL_ROOT', str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DEVSHELL_COMPONENTS', 'bash zsh uv chezmoi')
import state
import launcher


class LauncherBoundary(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name) / 'home'
        self.target = self.home / '.local/bin/devshell'
        self.receipt = self.home / '.state/devshell/launcher.json'
        self.backups = self.receipt.parent / 'launcher-backups'
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'original\n')
        self.target.chmod(0o700)
        for module, values in ((state, {'HOME': self.home, 'STATE': self.receipt.parent}),
                               (launcher, {'TARGET': self.target, 'RECEIPT': self.receipt, 'BACKUPS': self.backups})):
            for key, value in values.items():
                active = patch.object(module, key, value)
                active.start()
                self.addCleanup(active.stop)
        active = patch.dict(os.environ, {'DEVSHELL_REPLACE': '1'})
        active.start()
        self.addCleanup(active.stop)

    def approve(self):
        plan = launcher.build_plan()
        active = patch.dict(os.environ, {'DEVSHELL_APPROVAL': plan['approval']})
        active.start()
        self.addCleanup(active.stop)
        return plan

    def test_backup_failure_preserves_existing_launcher(self):
        plan = self.approve()
        original = state.atomic

        def fail_backup(path, *args, **kwargs):
            if path.is_relative_to(self.backups):
                raise OSError('backup failure')
            return original(path, *args, **kwargs)

        with patch.object(state, 'atomic', side_effect=fail_backup):
            with self.assertRaisesRegex(OSError, 'backup failure'):
                launcher.apply(plan)
        self.assertEqual(self.target.read_bytes(), b'original\n')
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o700)
        self.assertFalse(self.receipt.exists())

    def test_receipt_failure_keeps_exact_backup_and_partial_record(self):
        plan = self.approve()
        original = state.atomic

        def fail_receipt(path, *args, **kwargs):
            if path == self.receipt:
                raise OSError('receipt failure')
            return original(path, *args, **kwargs)

        with patch.object(state, 'atomic', side_effect=fail_receipt):
            with self.assertRaisesRegex(OSError, 'receipt failure'):
                launcher.apply(plan)
        record, = self.backups.glob('*/manifest.json')
        audit = json.loads(record.read_bytes())
        self.assertEqual(audit['status'], 'partial')
        self.assertEqual(audit['completed'], [str(self.target)])
        self.assertEqual((record.parent / '0').read_bytes(), b'original\n')
        self.assertEqual(self.target.read_bytes(), launcher.contents()[self.target][0])
        self.assertFalse(self.receipt.exists())


if __name__ == '__main__':
    unittest.main()
