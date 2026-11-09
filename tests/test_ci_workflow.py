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


if __name__ == '__main__':
    unittest.main()
