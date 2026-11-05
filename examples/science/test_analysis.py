"""Exemplo de teste de uma análise com dados artificiais."""

from analysis import summarize


def test_summary_for_known_values():
    result = summarize([0, 1, 2, 3, 4])
    assert result.loc["count", "value"] == 5
    assert result.loc["mean", "value"] == 2
