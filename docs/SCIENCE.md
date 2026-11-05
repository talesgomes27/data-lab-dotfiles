# Ciência de dados por projeto

[Início](../README.md) · [Uso cotidiano](USAGE.md) · [Diagnóstico](TROUBLESHOOTING.md)

O perfil `science` prepara interpretadores Python e ferramentas CLI. Bibliotecas
científicas, notebooks e pacotes R pertencem aos estudos. Um indicador de R,
Quarto ou Astro no prompt não significa que seu runtime tenha sido instalado.

## O que cada comando administra

| Escopo | Exemplo | Efeito |
|---|---|---|
| Interpretador por usuário | `uv python install --no-bin 3.13.11` | Instala CPython gerenciado sem criar python/python3 genérico no PATH. |
| CLI isolada | `uv tool install ruff==0.17.3` | Cria ambiente da ferramenta e disponibiliza seu executável. |
| Dependência do estudo | `uv add pandas` | Altera pyproject.toml, uv.lock e a `.venv` do projeto. |
| Ferramenta eventual | `uvx --from ruff==0.17.3 ruff check .` | Usa ambiente isolado/cache; pode baixar pacotes. |

O [manifesto Python](../manifests/python.json) fixa interpretadores e ferramentas
administrados pelo projeto. O instalador não usa `--default` ou `--force`, nem
substitui o Python da distribuição. Dependências transitivas das CLI uv não têm
lock único; o lock do exemplo científico é separado.

Antes de alterar um estudo existente, leia seu README e preserve o gerenciador
e o lock adotados. Não aponte UV_PROJECT_ENVIRONMENT de vários estudos para o
mesmo ambiente. Use `uv python list --only-installed` e `uv tool list` para
consultar os recursos disponíveis.

## Experimentar o exemplo Python

O [exemplo science](../examples/science/README.md) contém `.python-version`,
`pyproject.toml`, `uv.lock` e dados artificiais gerados pelos scripts.
Na raiz do Data Lab Dotfiles, crie uma cópia em uma pasta nova:

```bash
mkdir ../meu-estudo && cp -R examples/science/. ../meu-estudo/
```

Se o comando falhar, pare e escolha outro destino; não copie sobre um estudo
existente. Depois de a cópia ser criada com sucesso:

```bash
cd ../meu-estudo
uv sync --locked --group notebook --group analytics
uv run --locked python analysis.py
uv run --locked --group analytics python analytics.py
uv run --locked --group analytics pytest -q
```

A sincronização pode baixar pacotes e cria/atualiza a `.venv` da cópia.
`analysis.py` imprime estatísticas descritivas de dados artificiais;
`analytics.py` demonstra Polars, Parquet, PyArrow e uma consulta DuckDB em memória.
Os dois testes devem passar com `analytics` habilitado. O Parquet temporário é
removido pelo próprio exemplo. Nenhum dado pessoal é necessário.

| Grupo | Conteúdo |
|---|---|
| Dependências principais | NumPy, pandas, SciPy, statsmodels, scikit-learn, Matplotlib e ipykernel. |
| `notebook` | JupyterLab. |
| `analytics` | DuckDB Python, Polars e PyArrow. |
| `dev` | pytest e Ruff; grupo de desenvolvimento. |

O DuckDB Python da `.venv` é independente da CLI DuckDB, que é opcional no
perfil science. Rodar o exemplo não instala a CLI no sistema.

## Iniciar e encerrar JupyterLab

Dentro da cópia preparada:

```bash
jlab
# Alternativa explícita ao atalho:
# uv run --locked --group notebook jupyter lab
```

Abra o endereço local exibido no terminal. Ctrl+C encerra o servidor; confirme
se solicitado. `jlab --no-browser` evita a abertura automática do navegador.
A inicialização pode sincronizar a `.venv` e baixar dependências do grupo.
O atalho não instala JupyterLab globalmente.

`jlab` exige um projeto uv, lock válido e um grupo chamado `notebook` em
`[dependency-groups]`. O pacote Python chamado `notebook` é outro conceito.
Em um estudo uv que você pretende modificar, para criar o grupo esperado:

```bash
uv add --group notebook jupyterlab
jlab
```

Isso altera `pyproject.toml` e `uv.lock` e sincroniza o ambiente. Se JupyterLab
já estiver instalado na `.venv` e você quiser apenas iniciá-lo sem sincronização:

```bash
uv run --locked --no-sync python -m jupyterlab
```

Essa alternativa depende da instalação existente. Consulte o
[diagnóstico do jlab](TROUBLESHOOTING.md#jlab-sem-grupo-notebook) se faltar o grupo,
o módulo ou o lock.

## Criar um novo estudo Python

Os comandos abaixo criam um projeto e podem baixar pacotes:

```bash
uv init meu-estudo
cd meu-estudo
uv python pin 3.13.11
uv add numpy pandas scipy statsmodels scikit-learn matplotlib ipykernel
uv add --group notebook jupyterlab
uv add --dev ruff pytest
uv add --group analytics duckdb polars pyarrow
uv run --locked --group notebook jupyter lab
```

Versione `pyproject.toml`, `uv.lock` e `.python-version`. `uv sync --locked`
recusa um lock desatualizado. `uv run --locked` preserva o lock, mas pode
sincronizar o ambiente. Para usar um Python específico sem fixá-lo no projeto,
consulte `uv run --python 3.13.11 ...`.

Para uma interface Jupyter separada, você pode registrar o kernel do estudo:

```bash
uv add ipykernel
uv run python -m ipykernel install --user --name meu-estudo --display-name 'Python (meu-estudo)'
uvx --from jupyterlab jupyter lab
```

O registro `--user` grava um kernelspec fora do projeto. Se mover ou remover a
`.venv`, atualize/remova esse registro. Escolha o kernel do estudo na interface.
Para reproduzir a interface separada, fixe também a versão de JupyterLab em uvx.

## R e renv

O [exemplo R](../examples/r-science/README.md) requer R e `renv` disponíveis;
o perfil não instala R, renv ou Shiny. Consulte a
[documentação do renv](https://rstudio.github.io/renv/articles/renv.html) para sua
preparação. Confira o requisito antes de iniciar:

```bash
Rscript --vanilla -e 'stopifnot(requireNamespace("renv", quietly = TRUE))'
```

Retorno zero, sem mensagem, indica que o pacote pode ser encontrado. Na raiz
do Data Lab Dotfiles, copie o exemplo para uma pasta nova:

```bash
mkdir ../meu-estudo-r && cp -R examples/r-science/. ../meu-estudo-r/
```

Somente se a cópia foi criada com sucesso:

```bash
cd ../meu-estudo-r
Rscript --vanilla init.R
Rscript analysis.R
```

`init.R` cria `.Rprofile`, `renv/` e `renv.lock` usando o R e o renv locais;
recusa esses caminhos se já existirem, inclusive symlinks pendentes.
`analysis.R` imprime um resumo de dados artificiais. Uma interrupção pode deixar
arquivos parciais; revise-os antes de tentar novamente. Em um estudo renv,
registre mudanças de pacotes com `renv::snapshot()`. `renv::restore()` pode
baixar e instalar pacotes na biblioteca do projeto. O exemplo não demonstra Shiny.

## PyTorch e dependências nativas

PyTorch, drivers e CUDA não fazem parte do perfil. Verifique Python, wheels,
hardware e a [integração oficial uv/PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/).
Em um estudo dedicado, um ponto de partida CPU pode usar:

```toml
[project]
name = "estudo-torch-cpu"
version = "0.1.0"
requires-python = ">=3.12,<3.14"
dependencies = ["torch"]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu" }
```

Execute `uv lock`, revise e use `uv sync --locked`. Associe torchvision e
torchaudio ao mesmo índice se adicioná-los. Para GPU, escolha uma combinação
publicada para o driver/hardware; o exemplo não configura nem valida isso.

A existência de um lock não garante wheels em musl/aarch64 ou suporte de GPU.
Sem wheel compatível, bibliotecas como SciPy/statsmodels podem exigir
compiladores e BLAS/LAPACK. O [relatório de validação](VALIDATION.md) delimita
os cenários exercitados.
