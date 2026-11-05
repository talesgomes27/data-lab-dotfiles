# Exemplo científico Python

[Início](../../README.md) · [Guia científico](../../docs/SCIENCE.md)

Copie este diretório para um projeto próprio antes de alterar arquivos. O lock
fixa as dependências; o projeto usa sua própria `.venv`.

```bash
uv sync --locked --group notebook --group analytics
uv run --locked --group analytics python analytics.py
uv run --locked --group analytics pytest -q
uv run --locked --group notebook jupyter lab
```

Esses comandos podem baixar pacotes e criar ou atualizar a `.venv` da cópia.
`notebook` inclui JupyterLab; `analytics` inclui DuckDB Python, Polars e
PyArrow; o grupo de desenvolvimento inclui pytest e Ruff. A CLI DuckDB externa
é opcional e independente do pacote Python. `analytics.py` cria e remove um
Parquet artificial em diretório temporário; nenhum dado pessoal é usado.

O comando `jlab` disponível na shell interativa com o perfil `science` equivale
a `uv run --locked --group notebook jupyter lab`, com os argumentos informados.
Ele precisa ser executado em um projeto uv que tenha esse grupo e um lock válido.
