# Data Lab Dotfiles

Dotfiles e ferramentas de terminal para trabalhar com ciência de dados no Linux.
O projeto configura Zsh, Bash, Nushell e ferramentas de navegação, busca e
desenvolvimento. A CLI `devshell` apresenta as alterações antes da aplicação e
mantém backups das configurações gerenciadas. Bibliotecas científicas ficam em
ambientes próprios de cada projeto.

![Ilustração do terminal com contexto Git e Python e exemplos de atalhos](docs/assets/terminal.svg)

A imagem ilustra o uso; a aparência depende da fonte e do emulador de terminal.

[Instalação rápida](#instalação-rápida) · [Perfis](#perfis) ·
[Primeiros comandos](#primeiros-comandos) · [Glossário](#glossário-rápido) ·
[Manuais](#manuais) · [Licença](#licença)

## O que você recebe

- Terminal com prompt Starship, completamento, histórico e dois plugins Zsh.
- Atalhos para listar arquivos, pesquisar, navegar e consultar repositórios Git.
- Interpretadores Python e ferramentas isoladas via uv, com exemplos científicos
  em Python e R para copiar para seus próprios projetos.
- Planejamento, diagnóstico e recuperação de dotfiles pela CLI `devshell`.
- Diagnóstico de `.venv` e reparo revisado de permissões com `project doctor`
  e `project fix-permissions`; veja o [guia de uso](docs/USAGE.md#diagnosticar-e-reparar-permissões-de-uma-venv).

Os indicadores de R, Java, Rust, Go, Node.js, JavaScript, TypeScript, Quarto e
Astro no prompt reconhecem o contexto do diretório. Eles não instalam essas linguagens ou projetos.
JupyterLab, bibliotecas científicas e renv dependem da preparação de cada estudo;
veja o [guia científico](docs/SCIENCE.md).

## Requisitos e plataformas

Para iniciar: Linux, Bash >=4.4, Python >=3.11 e utilitários GNU básicos.
A [lista de pré-requisitos por funcionalidade](docs/INSTALLATION.md#pré-requisitos-por-funcionalidade)
separa o mínimo para iniciar, o terminal completo, runtimes e testes.
O setup pode instalar componentes ausentes de usuário e apresentar pacotes da
distribuição. Downloads exigem rede; pacotes administrativos exigem autorização.
Chezmoi é necessário para aplicar a configuração e pode ser instalado pelo setup.

Há verificação local em Ubuntu 26.04 x86_64/glibc e suíte isolada em containers
de Ubuntu 24.04, Debian 13, Fedora 44, Arch e openSUSE Leap 16.0. Essa matriz
não comprova a instalação de todos os pacotes dos perfis em cada distribuição.
Consulte o [alcance da validação](docs/VALIDATION.md) antes de usar em outra
plataforma. Esta é uma versão experimental.

## Instalação rápida

Clone o repositório público e entre na raiz. Você também pode baixar o ZIP
pelo botão **Code**, extrair e abrir a pasta que contém `bootstrap.sh`.
Para terminal e ciência de dados:

```bash
git clone --recurse-submodules https://github.com/talesgomes27/data-lab-dotfiles.git
cd data-lab-dotfiles
./bin/devshell setup --profile personal,science --dry-run
./bin/devshell setup --profile personal,science
./bin/devshell doctor --profile personal,science
```

O primeiro comando inspeciona. O segundo apresenta permissões, pacotes,
componentes de usuário e alterações nos arquivos, com confirmações separadas.
Conflitos exigem revisão do diff e a palavra `substituir`. O setup termina com
`doctor`; retorno zero indica que as verificações do perfil passaram.

Para incluir btop, ncdu, tldr e Lazygit, use `personal,science,extras` **nos três
comandos**. Mantenha a mesma seleção nas verificações e atualizações futuras.
A disponibilidade dos pacotes varia por versão da distribuição.

Depois, inicie `zsh` ou abra outro terminal se ela já for sua shell de login.
Selecione **FiraCode Nerd Font Mono** nas preferências do emulador para os ícones.
O setup não troca a shell de login; essa escolha é [manual e opcional](docs/INSTALLATION.md#primeiro-acesso).

A [instalação detalhada](docs/INSTALLATION.md) explica requisitos, confirmações,
Bash, operação manual, offline e atualização de ferramentas.

## Perfis

Todos os perfis incluem `minimal`. Os nomes podem ser combinados por vírgulas.

| Perfil | Finalidade e componentes |
|---|---|
| `minimal` | Base: Bash, Zsh, Git, uv e Chezmoi. |
| `personal` | Terminal: Nushell, Starship, fzf, zoxide, direnv, ripgrep, fd, bat, eza, Delta, plugins Zsh e FiraCode Nerd Font. |
| `science` | Python gerenciado, gerador `pyinit`, Ruff, pre-commit, IPython, ShellCheck, shfmt e Bats. Inspeciona DuckDB CLI opcional; bibliotecas científicas ficam por projeto. |
| `work` | Base com ripgrep e ShellCheck, sem os hooks opcionais de `personal`. |
| `extras` | Complementos opcionais: btop, ncdu, tldr/tealdeer e Lazygit. |

`work,personal` habilita as integrações de `personal`. Componentes de perfis
anteriores não são desinstalados ao mudar a seleção.

## Primeiros comandos

Em uma nova sessão Zsh, depois de aplicar `personal`:

| Tarefa | Comando ou atalho |
|---|---|
| Listar arquivos / incluir ocultos | `ls` / `la` |
| Retornar a uma pasta já visitada | `cd parte-do-nome` |
| Escolher uma pasta interativamente | `cdi parte-do-nome` |
| Procurar um comando anterior | Ctrl+R |
| Inserir um caminho com prévia | Ctrl+T |
| Consultar Git, dentro de um repositório | `gst` / `gl` |
| Ver o espaço usado até um nível | `du1` |

`jlab` exige um projeto uv com lock válido e grupo `notebook`; ele não funciona
em qualquer diretório. Siga o [exemplo científico](examples/science/README.md)
ou consulte o [diagnóstico do jlab](docs/TROUBLESHOOTING.md#jlab-sem-grupo-notebook).
O [manual de uso](docs/USAGE.md) apresenta exemplos e como sair das ferramentas.

Opcionalmente, prepare um [ambiente Python pessoal com troca automática](docs/SCIENCE.md#ambiente-pessoal-e-troca-automática-por-projeto):
o terminal inicia em `geral`, usa a `.venv` dos projetos autorizados pelo direnv
e restaura o ambiente anterior ao sair. O preparo é explícito; a navegação não
instala pacotes.

O [python-template-linux](https://github.com/talesgomes27/python-template-linux)
cria novos projetos com `.venv` e `.envrc` compatíveis com esse fluxo.
Veja [como conectar o gerador ao terminal](docs/SCIENCE.md#ambiente-pessoal-e-troca-automática-por-projeto).

## Configuração, atualização e recuperação

As fontes ficam em `dotfiles/`. Zsh usa `~/.config/zsh` por meio de `~/.zshenv`;
Bash e Nushell têm integrações próprias. [Veja os caminhos e a arquitetura](docs/ARCHITECTURE.md).
Para mudar a configuração, edite as fontes, confira `plan` e `diff` e use o setup
ou a aplicação manual aprovada. `update` atualiza somente configuração.

Backups ficam em `~/.local/state/devshell/transactions` por padrão. `rollback`
restaura a última transação de dotfiles e recusa alterações posteriores; ele não
desinstala ferramentas. Leia [segurança e recuperação](docs/SECURITY.md) antes de
restaurar. Não aplique Chezmoi diretamente sobre a HOME usando estas fontes:
isso contornaria o journal da CLI.

## Glossário rápido

| Termo | Significado neste projeto |
|---|---|
| Dotfiles | Arquivos de configuração do terminal e das ferramentas do usuário. |
| Shell | Programa que interpreta comandos, como Zsh ou Bash. |
| Perfil | Conjunto declarativo de componentes selecionados pela CLI. |
| PATH | Lista de diretórios onde a shell procura executáveis. |
| XDG | Convenção para separar configuração, dados, cache e estado; o default de configuração é `~/.config`. |
| Ambiente virtual (`.venv`) | Ambiente Python com as dependências de um projeto. |
| Grupo de dependências | Conjunto nomeado de pacotes no `pyproject.toml`, como `notebook` ou `analytics`. |
| Lock | Arquivo que registra a resolução das dependências, como `uv.lock`. |
| Dry-run | Inspeção da operação sem aplicá-la. |
| Rollback | Restauração da última transação de dotfiles; não desfaz instalações. |

## Manuais

| Preciso de… | Documento |
|---|---|
| Instalar e escolher o modo de operação | [Instalação](docs/INSTALLATION.md) |
| Usar ferramentas e atalhos | [Uso cotidiano](docs/USAGE.md) |
| Preparar Python, Jupyter ou R | [Ciência de dados](docs/SCIENCE.md) |
| Resolver uma falha | [Diagnóstico](docs/TROUBLESHOOTING.md) |
| Entender backups e limites | [Segurança](docs/SECURITY.md) |
| Entender o funcionamento e as decisões | [Arquitetura](docs/ARCHITECTURE.md) e [ADRs](docs/ADR/README.md) |
| Conferir testes e compatibilidade | [Validação](docs/VALIDATION.md) |
| Contribuir ou preparar uma versão | [Contribuição](CONTRIBUTING.md) |

Fontes oficiais estão em [Referências](docs/REFERENCES.md); mudanças destinadas
aos usuários ficam no [Changelog](CHANGELOG.md). Para pedir ajuda, abra uma issue
com a mensagem de erro e a seleção de perfis, sem incluir credenciais ou arquivos
privados. Falhas de segurança têm [orientação própria](docs/SECURITY.md#relatar-uma-vulnerabilidade).

## Licença

Código e documentação do projeto estão sob a [licença MIT](LICENSE).
A atribuição histórica do projeto foi preservada. Ferramentas, plugins e fontes
de terceiros mantêm suas próprias licenças.
