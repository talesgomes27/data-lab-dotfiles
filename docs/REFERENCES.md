# Referências oficiais

[Início](../README.md) · [Arquitetura](ARCHITECTURE.md)

As versões e checksums usados por novas instalações estão nos manifestos
[de artefatos](../manifests/artifacts.json) e [Python](../manifests/python.json).
Versões já instaladas e compatíveis podem ser reutilizadas. Não há consulta a
latest no runtime. O [relatório de validação](VALIDATION.md) distingue execução
local, fixtures e cenários pendentes.

| Fonte | Assunto |
|---|---|
| [uv: CLI](https://docs.astral.sh/uv/reference/cli/) | Interpretadores, ferramentas, execução e offline. |
| [uv: armazenamento](https://docs.astral.sh/uv/reference/storage/) | XDG e variáveis UV_*. |
| [uv: configuração](https://docs.astral.sh/uv/concepts/configuration-files/) | Configuração do usuário e do projeto. |
| [uv: lock e sincronização](https://docs.astral.sh/uv/concepts/projects/sync/) | Dependências e ambientes por projeto. |
| [uv: Jupyter](https://docs.astral.sh/uv/guides/integration/jupyter/) | Interface Jupyter e kernels. |
| [uv: PyTorch](https://docs.astral.sh/uv/guides/integration/pytorch/) | Índices e diferenças CPU/CUDA. |
| [Chezmoi: flags](https://www.chezmoi.io/reference/command-line-flags/global/) | Renderização isolada. |
| [Chezmoi: chezmoiroot](https://www.chezmoi.io/reference/special-files/chezmoiroot/) | Diretório de fontes. |
| [Zsh: inicialização](https://zsh.sourceforge.io/Doc/Release/Files.html) | zshenv, zprofile e zshrc. |
| [Bash: manual](https://www.gnu.org/software/bash/manual/) | Shell, scripts e source. |
| [Nushell: configuração](https://www.nushell.sh/book/configuration.html) | env.nu e config.nu. |
| [XDG Base Directory](https://specifications.freedesktop.org/basedir/latest/) | Configuração, dados, cache e estado. |
| [Starship: configuração](https://starship.rs/config/) | Módulos e prompt. |
| [Starship: configuração avançada](https://starship.rs/advanced-config/) | Integrações de shell. |
| [direnv: hooks](https://direnv.net/docs/hook.html) | Ambiente por diretório. |
| [fzf](https://github.com/junegunn/fzf) | Busca e atalhos interativos. |
| [eza: manual](https://github.com/eza-community/eza/blob/main/man/eza.1.md) | Listagem e opções dos aliases. |
| [Bats-core](https://bats-core.readthedocs.io/en/stable/) | Testes Bash. |
| [ShellCheck](https://github.com/koalaman/shellcheck) | Análise de scripts. |
| [shfmt](https://github.com/mvdan/sh) | Formatação shell. |
| [autosuggestions](https://github.com/zsh-users/zsh-autosuggestions/tree/v0.7.1) | Plugin fixado. |
| [syntax highlighting](https://github.com/zsh-users/zsh-syntax-highlighting/tree/0.8.0) | Plugin fixado. |
| [Nerd Fonts v3.5.1](https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.5.1) | FiraCode.zip e release adotada. |
| [tealdeer](https://github.com/tealdeer-rs/tealdeer) | Cliente tldr e páginas. |
| [renv](https://rstudio.github.io/renv/articles/renv.html) | Biblioteca e lock R por projeto. |
| [DuckDB: CLI](https://duckdb.org/docs/stable/clients/cli/overview) | Consultas locais sobre CSV e Parquet. |

Ao mudar um manifesto, confira a release oficial, o asset exato e seu checksum,
e execute nova validação. Fixar versões não equivale a auditar os fornecedores.


Dependências dos cenários opcionais no CI manual: Quarto CLI
[v1.10.19](https://github.com/quarto-dev/quarto-cli/releases/tag/v1.10.19), com
SHA-256 do asset oficial; renv [v1.3.1](https://github.com/rstudio/renv/releases/tag/v1.3.1),
com SHA-256 congelado da fonte oficial obtida pela API GitHub. Os hashes estão
no workflow. Esses downloads só preparam o runner descartável, não a máquina
do usuário ou o instalador dos perfis.
