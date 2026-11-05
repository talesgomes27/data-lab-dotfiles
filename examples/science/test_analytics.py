"""Verifica o exemplo com dados gerados em diretório temporário."""

from importlib import import_module

import pytest

pytest.importorskip("duckdb")
pytest.importorskip("polars")
pytest.importorskip("pyarrow")

analytics = import_module("analytics")


def test_synthetic_parquet_roundtrip():
    assert analytics.main() == (3, 6)
