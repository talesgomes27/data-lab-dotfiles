"""Contratos dos exemplos: dependências isoladas e locks coerentes."""
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScienceExample(unittest.TestCase):
    def test_optional_tools_are_declared_and_locked(self):
        folder = ROOT / 'examples/science'
        project = tomllib.loads((folder / 'pyproject.toml').read_text())
        lock = tomllib.loads((folder / 'uv.lock').read_text())
        groups = project['dependency-groups']
        self.assertTrue(any(value.startswith('jupyterlab') for value in groups['notebook']))
        self.assertTrue(any(value.startswith('pytest') for value in groups['dev']))
        self.assertTrue(all(any(value.startswith(name) for value in groups['analytics'])
                            for name in ('duckdb', 'polars', 'pyarrow')))
        packages = {package['name'] for package in lock['package']}
        self.assertTrue({'jupyterlab', 'pytest', 'duckdb', 'polars', 'pyarrow'} <= packages)


if __name__ == '__main__':
    unittest.main()
