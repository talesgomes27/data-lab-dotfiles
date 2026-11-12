"""R-010: o workflow roda toda semana com a cobertura do disparo manual (lido como texto, sem parser YAML)."""
from pathlib import Path
import re
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/ci.yml'


class WeeklyWorkflow(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text()

    def test_r010_schedule_runs_monday_off_the_hour(self):
        trigger = re.search(r'^on:\n((?:  .*\n|\n)+)', self.text, re.M)
        self.assertIsNotNone(trigger)
        self.assertRegex(trigger.group(1), r"(?m)^  schedule:\n    - cron: '17 9 \* \* 1'$")

    def test_r010_every_manual_condition_also_accepts_schedule(self):
        conditions = [line.strip() for line in self.text.splitlines() if line.strip().startswith('if:')]
        manual = [line for line in conditions if "'workflow_dispatch'" in line]
        # Dois passos do job checks, os jobs containers e online-smoke.
        self.assertGreaterEqual(len(manual), 4, conditions)
        for line in manual:
            self.assertEqual(line, "if: github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'")

    def test_actions_are_pinned_by_full_sha_with_version(self):
        uses = re.findall(r'^\s*- uses: (.+)$', self.text, re.M)
        self.assertTrue(uses)
        for line in uses:
            self.assertRegex(line, r'^[\w.-]+/[\w.-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$')

    def test_checkout_uses_the_reviewed_node24_release(self):
        # v7.0.1 declara runs.using: node24 (conferido no action.yml do commit, fonte oficial).
        checkouts = re.findall(r'actions/checkout@(\S+) # (\S+)', self.text)
        self.assertEqual(len(checkouts), 3)
        self.assertEqual(set(checkouts), {('3d3c42e5aac5ba805825da76410c181273ba90b1', 'v7.0.1')})


if __name__ == '__main__':
    unittest.main()
