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

## Ambiente pessoal e troca automática por projeto

Este recurso é opcional e exige o perfil `personal` (componentes uv e direnv),
direnv instalado e a configuração aplicada pelo fluxo normal de revisão e
backup. Em Bash, carregue o fragmento documentado na [instalação](INSTALLATION.md#bash-e-nushell).
Bash, Zsh e Nushell fazem a troca em sessões interativas, antes do próximo
prompt. Scripts não recebem ativação automática; subprocessos herdam o ambiente
que já estiver ativo.

## Criar projetos com o template integrado

O perfil `science` instala `~/.local/bin/pyinit`, o gerador do
[python-template-linux](https://github.com/talesgomes27/python-template-linux),
fixado por commit e SHA-256. O código completo permanece como submódulo em
`templates/python-template-linux`; o instalador baixa apenas o script verificado,
sem depender do caminho da cópia local. O setup pede confirmação própria para
esse componente. Para instalá-lo separadamente, revise o plano e aprove seu hash:

```bash
./bin/devshell install --component pyinit
# Copie o hash exibido após revisar o plano:
./bin/devshell install --component pyinit --approve HASH_REVISADO
```

Em um novo terminal, com `~/.local/bin` no PATH:

```bash
pyinit --help
pyinit ../meu-projeto --archetype ds
# Outros arquétipos: universal, api e cli.
```

O gerador prepara a `.venv`, cria `.envrc` com `use devshell_python` e usa
permissões privadas para novas criações. Runtime e dependências podem ser
baixados durante esse preparo explícito. Ele preserva `.envrc` e permissões já
existentes, não concede autorização direnv e não faz stage, commit ou push.
O perfil `science` oferece o gerador; a troca automática exige também `personal`,
direnv e a configuração do terminal descrita nesta página. Depois de revisar o
arquivo completo, execute manualmente `direnv allow .` na raiz do novo projeto.
Rollback dos dotfiles preserva o gerador e os ambientes criados.

## Preparar o ambiente pessoal

Prepare uma vez o ambiente pessoal. O CPython 3.13.11 do
[manifesto](../manifests/python.json) precisa estar instalado pelo fluxo
aprovado de `install --component python`. O comando abaixo é uma operação
manual de criação de ambiente, fora da transação de dotfiles; não baixa Python
nem instala bibliotecas e recusa um destino já existente, inclusive symlink:

```bash
case "${XDG_DATA_HOME-}" in
    /*) devshell_data=$XDG_DATA_HOME ;;
    *) devshell_data="$HOME/.local/share" ;;
esac
general="$devshell_data/devshell/venvs/geral"
test ! -e "$general" && test ! -L "$general" &&
    (umask 077; uv --no-config venv --no-project --managed-python \
        --no-python-downloads --python 3.13.11 "$general")
```

Abra um novo terminal. Se não houver outra ativação manual ou Conda, `python`
e `python3` apontarão para `geral`. A existência desse diretório habilita o
recurso; nenhum pacote científico é incluído automaticamente. Para conferir:

```bash
python -c 'import sys; print(sys.executable); print(sys.prefix)'
uv pip list
```

Em cada projeto uv, prepare sua `.venv` com `uv sync --locked` após revisar
manifesto e lock. Essa preparação explícita pode baixar dependências. Preserve
o gerenciador e o processo próprios de projetos Poetry, Conda ou outros.
Crie um `.envrc` na raiz com o conteúdo abaixo; se ele já existir, revise-o e
acrescente a linha sem sobrescrever seu conteúdo:

```bash
use devshell_python
```

Depois de ler o arquivo completo, autorize-o:

```bash
cat .envrc
direnv allow .
```

| Navegação | Ambiente selecionado |
|---|---|
| Fora de projeto autorizado | `geral`, se preparado e seguro. |
| Projeto autorizado e suas subpastas | `.venv` da raiz que contém o `.envrc`. |
| Outro projeto autorizado | `.venv` do outro projeto. |
| Saída do projeto | Ambiente anterior, normalmente `geral`. |
| Projeto autorizado sem `.venv` válida | Sem o ambiente anterior no PATH; aviso para preparar/revisar a `.venv`. |
| Projeto sem `.envrc` autorizado | Sem troca; direnv bloqueia arquivos não autorizados. |
| Conda ativo | Preservado, com aviso para desativá-lo explicitamente antes da troca uv. |

O helper só seleciona a `.venv` existente. Ele não executa seu `activate`,
`uv sync` ou instaladores. Evite `layout uv` se deseja manter essa ausência de
sincronização automática. Depois de criar ou reparar a `.venv`, `direnv reload`
permite repetir a seleção sem sair da pasta. Mudanças no `.envrc` exigem nova
revisão e autorização.

O helper não simula `conda deactivate`: Conda tem estado próprio de shell.
Desative-o explicitamente antes de usar a troca por `.venv`; durante uma sessão
Conda, o helper apenas avisa e conserva o ambiente.

`uv pip install` usa primeiro o ambiente ativo. Em repositórios ainda não
configurados, `geral` pode continuar ativo: prefira `uv add`, `uv sync` e
`uv run`, ou indique explicitamente `--python` para operações no destino
pretendido. Não exporte `UV_PROJECT_ENVIRONMENT` globalmente nem use `--active`
para fazer projetos compartilharem `geral`. O ambiente pessoal não recebe
automaticamente as dependências de nenhum projeto.

Para desabilitar o ambiente pessoal, renomeie seu diretório conscientemente e
abra um novo terminal. Para revogar um projeto, use `direnv deny .`. Rollback
dos dotfiles não remove nenhum desses ambientes; shells abertas precisam ser
encerradas para descartar a configuração já carregada.

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
