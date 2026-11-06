# Uso cotidiano

[Início](../README.md) · [Instalação](INSTALLATION.md) · [Ciência de dados](SCIENCE.md)

Os exemplos interativos supõem uma sessão Zsh com o perfil `personal` aplicado.
Substitua nomes de arquivos e pastas pelos seus. `extras` é necessário para
selecionar seus pacotes; as bibliotecas de estudos são preparadas separadamente.

## Navegar entre pastas

Visite uma pasta pelo caminho completo. O zoxide guarda visitas localmente e,
no Zsh configurado, integra-se ao comando `cd`:

```bash
cd ~/Documentos/meu-estudo
cd ..
cd meu-estudo
cd -
zoxide query meu-estudo
cdi estudo
```

Um caminho existente tem prioridade; nomes parciais buscam no histórico.
`zoxide query` permite conferir o destino e `cdi` oferece seleção com fzf.
`z` e `zi` também estão disponíveis. `builtin cd caminho` usa o cd nativo.
Bash e scripts mantêm o comportamento nativo de `cd`.

## Listar, localizar e ler arquivos

```bash
ls                          # pastas primeiro; arquivos por extensão
la                          # inclui arquivos ocultos
eza --tree --level=2         # árvore de até dois níveis
rg -n 'faturamento' .        # texto, arquivo e linha
fdfind 'relatorio' .         # nomes de arquivos/pastas no Ubuntu
batcat README.md             # conteúdo com realce de sintaxe
command ls                  # GNU ls, sem o alias interativo
```

Em outras distribuições, os executáveis podem se chamar `fd` e `bat`.
Buscas podem respeitar regras de exclusão e ignorar ocultos por padrão.
`batcat` pode abrir um paginador: use `q` para sair.

| Atalho no Zsh | Uso |
|---|---|
| Tab | Completar comandos e caminhos. |
| Ctrl+R | Procurar um comando no histórico. |
| Ctrl+T | Escolher e inserir um caminho no comando, com prévia se bat estiver disponível. |
| Alt+C | Escolher um diretório para acessá-lo. |

Para abrir um arquivo, digite `batcat `, pressione Ctrl+T, escolha um caminho e
pressione Enter. Confira o comando completo e execute-o. Esc cancela o seletor.
Uma `FZF_CTRL_T_OPTS` já definida tem precedência sobre a prévia do projeto.
A integração de atalhos fzf exige suporte a `fzf --zsh` (versão >=0.48).

Autosuggestions sugere comandos do histórico; o outro plugin realça a sintaxe.
Confira sugestões antes de executar. Não há sincronização remota do histórico.

## Consultar e trabalhar com Git

Dentro de um repositório Git válido:

```bash
gst                                  # branch e alterações locais
gl                                   # dez commits mais recentes
git diff --color=always | delta       # examina diferenças com realce
lazygit                              # interface interativa; perfil extras
```

`gst`, `gl` e `du1` só são definidos se seus nomes estiverem livres. `gs` também
pode ser criado para status, mas é preservado se já pertencer a outro comando,
como Ghostscript. Prefira `gst` nos exemplos.

Delta não configura seu `~/.gitconfig` automaticamente. No paginador, use `q`
para sair. No Lazygit, comece consultando os painéis e use `q` para sair; ações
de estágio, commit e descarte de alterações modificam o repositório.

## Conferir recursos, disco e ajuda

```bash
btop             # CPU, memória e processos; q para sair
ncdu .           # navega pelo uso de disco da pasta; q para sair
du1              # tamanhos até um nível abaixo da pasta atual
tldr tar         # exemplos curtos de tar
tldr git         # exemplos curtos de Git
```

btop, ncdu e tldr pertencem a `extras`. O ncdu possui uma ação de exclusão:
confira o item e a operação antes de utilizá-la. No primeiro uso do tldr,
pode ser necessário executar `tldr --update`, que baixa páginas e grava cache.
O cliente instalado é tealdeer; não há atualização de páginas automática.

## Inspecionar dados sem abrir um notebook

Se a CLI DuckDB estiver instalada, na pasta de um CSV chamado `dados.csv`:

```bash
duckdb -c "SELECT * FROM read_csv_auto('dados.csv') LIMIT 5;"
duckdb -c "SELECT COUNT(*) AS linhas FROM read_csv_auto('dados.csv');"
```

A primeira consulta mostra até cinco registros; a segunda conta as linhas.
Essas consultas usam o arquivo local e não criam uma base persistente.
Troque o caminho pelos seus dados. DuckDB CLI é opcional e independente do
pacote Python DuckDB. `doctor` avisa se ela falta ou está em caminho inseguro.

Para Python/JupyterLab e R/renv, siga [Ciência de dados](SCIENCE.md). O atalho
`jlab` usa o ambiente do estudo e exige o grupo `notebook` e um lock válido.

## Ler o prompt e experimentar Nushell

O Starship mostra diretório, Git e contextos de linguagem detectados. No Zsh,
comandos com pelo menos dois segundos exibem duração; falhas exibem o código
de saída. JavaScript e TypeScript usam arquivos do diretório; Astro usa
`astro.config.js`, `.mjs`, `.ts`, `.mts` ou `.cjs`. Os indicadores não instalam
as linguagens. Java, Rust e Go usam módulos nativos do Starship:

| Linguagem | Exemplos de arquivos que ativam o bloco | Versão consultada |
|---|---|---|
| Java | `Main.java`, `pom.xml`, `build.gradle.kts` | Java disponível no ambiente; respeita JAVA_HOME. |
| Rust | `main.rs`, `Cargo.toml` | Toolchain Rust disponível no ambiente. |
| Go | `main.go`, `go.mod`, `go.work` | Go disponível no ambiente. |

Os blocos mostram o nome e a versão quando ela pode ser obtida. Os runtimes não
são instalados pela configuração do prompt. Consulte os módulos
[Java](https://starship.rs/config/#java), [Rust](https://starship.rs/config/#rust)
e [Go](https://starship.rs/config/#go) para os demais padrões de detecção.
Se ícones aparecerem quebrados, selecione FiraCode Nerd Font Mono.

Para personalizar, edite `dotfiles/dot_config/starship.toml`, revise plan/diff e
aplique pela CLI. Editar só o arquivo instalado cria divergência com as fontes.

Nushell trata saídas como dados estruturados. Execute `nu` e, dentro dela:

```nu
ls | where type == dir
open dados.csv | first 5
exit
```

O CSV precisa existir; `exit` retorna à shell anterior. Nu recebe o código de
saída no prompt, mas não a duração. Bash continua disponível com `bash`; use
`exit` para voltar. As integrações completas do fragmento Bash exigem sua
[inclusão manual](INSTALLATION.md#bash-e-nushell).

## Carregar variáveis por projeto

O direnv executa o `.envrc` do diretório somente após autorização. Leia todo o
arquivo antes de permitir seu uso:

```bash
cat .envrc
# Após revisar e confiar no conteúdo:
direnv allow
# Para retirar a autorização:
direnv deny
```

Mudanças no `.envrc` exigem nova revisão. Não versione senhas. O projeto carrega
o hook de direnv, mas não concede autorizações por conta própria.

Para ter um ambiente Python pessoal ao abrir o terminal e selecionar a `.venv`
ao entrar nos projetos, siga o [preparo do ambiente pessoal e do `.envrc`](SCIENCE.md#ambiente-pessoal-e-troca-automática-por-projeto).
O conteúdo `use devshell_python` usa somente a `.venv` existente. Ao sair,
direnv restaura o ambiente anterior; abrir o terminal ou navegar não cria
ambientes nem instala dependências. A troca ocorre antes do próximo prompt:
em scripts ou em uma linha como `cd projeto && python ...`, use `uv run` ou
um caminho explícito para o interpretador.

## Conferir código e configuração

No projeto Python, use as ferramentas declaradas no ambiente do estudo. As CLI
Ruff, pre-commit e IPython também podem estar disponíveis isoladamente via uv:

```bash
ruff check .
ruff format --check .
ipython
shellcheck meu-script.sh
shfmt -d meu-script.sh
```

`ruff format --check` e `shfmt -d` apenas conferem formatação. Para sair do
IPython, use `exit`. Leia `.pre-commit-config.yaml` antes de executar hooks:
eles podem baixar dependências ou alterar arquivos. `pre-commit install` também
altera hooks do repositório e não é executado automaticamente pelo projeto.

Na raiz do Data Lab Dotfiles, use o mesmo perfil aplicado:

```bash
./bin/devshell status --profile personal,science
./bin/devshell diff --profile personal,science
./bin/devshell doctor --profile personal,science
```

Para testar o próprio projeto, consulte [Contribuição](../CONTRIBUTING.md).
O [diagnóstico](TROUBLESHOOTING.md) trata ausências, permissões, conflitos e
problemas dos atalhos. Os componentes declarados estão em `profiles/` e
`manifests/`; essa relação é diferente do inventário particular de uma máquina.
