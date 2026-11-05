"""Demonstra Polars, PyArrow e DuckDB com dados artificiais e temporários."""

from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import polars as pl
import pyarrow.parquet as pq


def main():
    with TemporaryDirectory(prefix="foundry-science-") as directory:
        parquet = Path(directory) / "observations.parquet"
        pl.DataFrame({"value": [1, 2, 3]}).write_parquet(parquet)
        rows = pq.read_table(parquet).num_rows
        with duckdb.connect(database=":memory:") as connection:
            total = connection.execute(
                "SELECT SUM(value) FROM read_parquet(?)", [str(parquet)]
            ).fetchone()[0]
        print(f"linhas={rows}; soma={total}")
        return rows, total


if __name__ == "__main__":
    main()
