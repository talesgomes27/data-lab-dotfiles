# Uso cotidiano

[Início](../README.md) · [Instalação](INSTALLATION.md) · [Ciência de dados](SCIENCE.md)

Os exemplos interativos supõem uma sessão Zsh com o perfil `personal` aplicado.
Substitua nomes de arquivos e pastas pelos seus. `extras` é necessário para
selecionar seus pacotes; as bibliotecas de estudos são preparadas separadamente.

## Manter o ambiente em dia

Depois de atualizar o checkout, `./bin/devshell setup` faz o que faltar, com uma
confirmação por etapa, e `./bin/devshell doctor` termina com o próximo passo
quando encontra pendências. Os comandos sem `--profile` usam os perfis do último
`apply`; a linha `Perfis:` da saída mostra quais e de onde vieram (`lembrados`,
`informados` ou `padrão`). Se os perfis lembrados tirariam componentes que já
estão aplicados, os comandos param com saída 2 e pedem
`./bin/devshell setup --profile PERFIS` uma vez, com os perfis que você usa.
Em JSON, o `doctor` traz o campo `next_step`.

O estado em `~/.local/state/devshell` pertence a uma HOME e a um
`XDG_CONFIG_HOME`. Um comando rodado com outra HOME ou outro
`XDG_CONFIG_HOME` sobre o mesmo estado para com saída 2 e mostra a
configuração que o estado registra. Para testar outra configuração, use
também um `XDG_STATE_HOME` próprio, ou HOME e todos os XDG temporários
juntos. Só `rollback --list` e `project` funcionam nesse caso. Mudar os
perfis registrados, mesmo sem arquivos a alterar, cria uma transação, que
aparece em `rollback --list` e pode ser desfeita.

### Trocar de perfil e retirar o que ficou de fora

Quando você troca de perfil, por exemplo de `personal` para `minimal`, os
arquivos que só o perfil antigo gerava ficam de fora. O `plan` lista cada um
com o que o próximo `apply` fará (saída executada em HOME temporária, com
`starship.toml` editado à mão):

```console
$ ./bin/devshell plan --profile minimal
  write: ~/.config/devshell/components
  remove: ~/.config/direnv/lib/devshell-python.sh
  remove: ~/.config/nushell/config.nu
  remove: ~/.config/nushell/env.nu
  forget: ~/.config/starship.toml (editado depois do apply; fica intacto)
```

Como cada linha é tratada:
- **`remove`:** o arquivo está igual ao que a CLI escreveu. É removido com
  backup na transação, e o `rollback` o devolve.
- **`forget`:** o arquivo fica intacto e só sai do registro. Isso vale para
  arquivo editado por você, arquivo que já não existe, arquivo em caminho
  inseguro e dotfile que saiu do repositório. Remova à mão, se quiser.
- **Diretórios:** os que ficarem vazios não são removidos.

O `doctor` acusa esses arquivos e sugere o `setup`. No `setup`, a remoção pede
uma confirmação à parte: digite `retirar`.

Um `XDG_CONFIG_HOME` diferente numa sessão não leva à retirada: o comando é
recusado antes, porque o estado pertence a outra configuração.

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
l                           # grade com ícones sempre visíveis
la                          # grade, incluindo arquivos ocultos
ll                          # detalhes, tamanhos legíveis, Git e datas relativas
lla                         # detalhes, incluindo arquivos ocultos
lt                          # árvore de até dois níveis
lta                         # árvore, incluindo arquivos ocultos
rg -n 'faturamento' .        # texto, arquivo e linha
fdfind 'relatorio' .         # nomes de arquivos/pastas no Ubuntu
batcat README.md             # conteúdo com realce de sintaxe
command ls                  # GNU ls, sem o alias interativo
```

`l`, `la`, `ll`, `lla`, `lt` e `lta` são compartilhados por Bash e Zsh em
sessões interativas com o componente eza selecionado e o executável disponível.
As listagens em grade e detalhadas agrupam pastas primeiro e ordenam arquivos
por extensão. Os seis atalhos usam `--icons=always`; para exibir os ícones,
selecione uma Nerd Font no terminal. `ls` mantém ícones automáticos.
Argumentos adicionais são preservados, por exemplo `ll "pasta com espaços"`.

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

## Desinstalar um componente

`uninstall --component X` retira o que `install` colocou na HOME. Vale para
`python` (as venvs das ferramentas e seus symlinks), `devshell` (o lançador),
`pyinit`, `plugins` e `firacode`. Sem `--approve`, ele só mostra o plano,
sem gravar nada (saída executada em HOME temporária):

```console
$ ./bin/devshell uninstall --component devshell
  remove: ~/.local/bin/devshell
  remove: ~/.local/state/devshell/launcher.json
$ ./bin/devshell uninstall --component devshell --approve HASH
2 item(ns) removido(s). Para desfazer: ./bin/devshell install --component devshell.
```

O plano marca cada caminho de um de dois jeitos:
- **`remove`:** a CLI prova que o item é dela: bytes iguais ao gerado, ao
  manifesto, ao recibo do install ou ao pacote em cache. Para as venvs, cada
  arquivo precisa estar no lock.
- **`manual`:** o item existe, mas falta essa prova (por exemplo, um arquivo
  seu dentro da venv, um plugin editado ou uma fonte sua na mesma pasta).
  Fica para você remover à mão, se quiser.

Não há backup: desfazer é rodar `install --component X` de novo, que devolve
os mesmos bytes. O `uv`, o `chezmoi`, o `nu`, o CPython do uv e os pacotes do
sistema nunca são desinstalados. Se o componente continua nos perfis
lembrados, o plano avisa que o próximo `setup` o reinstala.

Os plugins, a fonte e o `pyinit` instalados antes desta versão não têm recibo.
O plano os confere contra o pacote em cache e, sem cache, os deixa como
`manual`. Para gravar o recibo, rode `install --component X` com
`--approve` uma vez; o `setup` não faz isso quando o componente já está em
dia.

## Consultar e podar o histórico de backups

```bash
./bin/devshell rollback --list                  # transações, status e datas
./bin/devshell rollback --prune --keep 3        # plano: o que seria removido
```

Exemplo de listagem e de plano numa HOME de teste com três transações:

```text
Data Lab Dotfiles — rollback-list
  ID: committed, cadeia 0, 1 arquivo(s), AAAA-MM-DDTHH:MM:SSZ
  ID: committed, cadeia 1, 1 arquivo(s), AAAA-MM-DDTHH:MM:SSZ
  ID: committed, cadeia 2, 9 arquivo(s), AAAA-MM-DDTHH:MM:SSZ
```

Plano com `--keep 2`:

```text
Data Lab Dotfiles — rollback-prune
Aprovação: HASH
Aviso: remove a primeira transação (ID), que guarda os dotfiles de antes do primeiro apply
  ID: keep, committed, cadeia 0
  ID: keep, committed, cadeia 1
  ID: delete, committed, cadeia 2
Bytes a remover: 4310
message: Remoção irreversível: os backups removidos não podem ser restaurados.
```

A remoção só acontece com
`./bin/devshell rollback --prune --keep 2 --approve HASH`, usando o hash do
plano revisto, e não tem volta. Leia
[Histórico e poda de backups](SECURITY.md#histórico-e-poda-de-backups) antes.

## Diagnosticar e reparar permissões de uma .venv

Execute a CLI na raiz do Data Lab Dotfiles, apontando para o projeto afetado.
Os comandos `project`, como os demais comandos da CLI, usam `/usr/bin/python3 >=3.11` em modo isolado (`-I -B`),
sem iniciar o Python da `.venv` ou importar código pelo PYTHONPATH do projeto.
O modo `-B` impede gravação de bytecode. Sem `--path`, o diretório atual é
o projeto inspecionado.

```bash
projeto="$HOME/caminho/do/projeto"
./bin/devshell project doctor --path "$projeto"
./bin/devshell project fix-permissions --path "$projeto" --dry-run
./bin/devshell project fix-permissions --path "$projeto"
```

Doctor é somente leitura e retorna 3 se houver problemas. O dry-run apresenta
os modos atuais/propostos sem gravar estado. O reparo mostra o plano e pede sua
confirmação; EOF ou resposta diferente de `s`/`sim` cancela. Para aprovação
explícita por hash, após revisar o plano:

```bash
./bin/devshell project fix-permissions --path "$projeto" --dry-run --json
./bin/devshell project fix-permissions --path "$projeto" --approve HASH_REVISADO
```

`--json` no reparo exige `--dry-run` ou `--approve`. Não existe `--yes`.
Mudanças no código ou nas identidades/modos observados invalidam a aprovação.

O escopo é somente a cadeia de diretórios até `.venv/bin`. Apenas diretórios do
usuário sob sua HOME podem perder escrita de grupo/outros, por exemplo
`0775 -> 0755`. Revise os pais apresentados: retirar escrita de grupo de uma
pasta compartilhada também afeta a criação/remoção de entradas pelo grupo.
Não há recursão ou alteração de arquivos filhos. Symlinks de diretórios,
proprietários inesperados e estrutura de ambiente ausente/inválida exigem
correção manual e bloqueiam todo o reparo. Links de interpretadores criados
por uv continuam permitidos e não são alterados.

Antes do primeiro chmod, os modos/identidades aprovados são registrados em
`$XDG_STATE_HOME/devshell/permission-repairs/ID.json`, com fallback para
`~/.local/state`. O registro privado guarda o plano, caminhos concluídos e
status `complete` ou `partial`. O diretório do registro precisa estar seguro;
problemas nele aparecem como bloqueio antes da confirmação. Cada chmod usa
descritor sem seguir symlink e confere device/inode/tipo/modo/UID/GID/links.

Uma falha pode preservar reparos já concluídos. Confira o registro e execute
novamente doctor antes de retomar. Rollback de dotfiles não restaura esses
modos nem reabilita escrita compartilhada automaticamente.

O comando não cria/recria `.venv`, instala pacotes, executa `uv sync` ou autoriza
`.envrc`. Se faltar o ambiente, prepare-o pelo processo do projeto. Depois de
concluir um reparo de permissões:

```bash
cd "$projeto"
direnv reload
```
