# Instalação e manutenção

[Início](../README.md) · [Uso](USAGE.md) · [Diagnóstico](TROUBLESHOOTING.md)

## Antes de começar

Você precisa de Linux, Bash >=4.4, Python >=3.11 e utilitários GNU básicos.
O Python do sistema executa a CLI; bibliotecas do estudo ficam em sua própria
`.venv`. Rede é necessária para downloads não presentes em cache. Pacotes da
distribuição podem exigir sudo, mas inspeção e aplicação de dotfiles não.

Consulte a [matriz de evidências](VALIDATION.md). Pacotes mapeados podem não
existir em todas as releases. O setup não habilita COPR, AUR ou repositórios
extras, não atualiza índices nem instala drivers.

## Pré-requisitos por funcionalidade

Para habilitar todos os recursos descritos, considere as camadas abaixo. Não é
necessário instalar todas as ferramentas antes do setup: ele instala ou verifica
os componentes declarados. Runtimes e dependências dos estudos têm preparação
própria; um doctor sem problemas não comprova todo projeto científico externo.

| Camada | O que precisa estar disponível | Preparação |
|---|---|---|
| Iniciar a CLI | Linux, Bash >=4.4, Python >=3.11 com SSL e utilitários GNU (`uname`, `dirname`, `getconf`/`ldd`, `grep`) | Pacotes básicos da distribuição; use o Python do sistema para a CLI. |
| Obter o código e baixar artefatos | Git e certificados CA; conexão HTTPS para arquivos fora do cache | Git é necessário ao clone. Instale `ca-certificates`; curl, tar e gzip são usados nos scripts de CI e downloads manuais. |
| Aplicar dotfiles | Chezmoi >=2.62.0 e diretórios HOME/XDG graváveis pelo usuário e seguros | O setup instala Chezmoi se faltar; os hashes e backups continuam obrigatórios. |
| Terminal personal | Zsh >=5.9, Starship, fzf, zoxide, direnv, ripgrep, fd, bat, eza, Delta e Fontconfig | Pacotes mapeados da distribuição; confira a disponibilidade da sua release. fzf >=0.48 é necessário aos atalhos integrados por `--zsh`. |
| Complementos personal | Nushell >=0.116.1, dois plugins Zsh e FiraCode Nerd Font | O setup pode instalar os componentes de usuário. Escolha a fonte Mono no emulador; os ícones dependem dessa seleção. |
| Ferramentas Python science | uv >=0.13.5, CPython e CLI declaradas no manifesto (Ruff, pre-commit, IPython) | Cada CLI ganha uma venv própria com lock e hash obrigatório; instalações anteriores pelo `uv tool` exigem a migração de [SECURITY](SECURITY.md#escopo-e-downloads). Não instale pacotes com pip no Python do sistema. |
| Gerador de projetos science | `pyinit` (python-template-linux) | Script fixado por commit e SHA-256, instalado em `~/.local/bin` após confirmação; `direnv allow` permanece manual. |
| Scripts e testes science | ShellCheck, shfmt e Bats | Pacotes da distribuição. Para executar a suíte, também são necessários Zsh, Nushell e Chezmoi. |
| Extras | btop, ncdu, tealdeer (`tldr`) e Lazygit | Perfil `extras`; nem todos os adaptadores/releases oferecem todos os pacotes. |
| SQL local | DuckDB CLI | Opcional e externo ao instalador. Confira a origem, o PATH e as permissões da instalação. |

No Debian/Ubuntu os executáveis `fd` e `bat` podem ser `fdfind` e `batcat`.
A disponibilidade de Starship, eza, zoxide e Lazygit depende da release. O
[manifesto de pacotes](../manifests/packages.tsv) é a referência do setup; uma
célula `-` exige preparação manual. A presença de um nome não garante que ele
exista nos repositórios habilitados da sua versão.

### Exemplo de base em Debian ou Ubuntu

Revise os pacotes e execute no seu terminal, se estiverem ausentes:

```bash
sudo apt-get update
sudo apt-get install -- bash python3 git ca-certificates coreutils grep curl tar gzip
python3 --version
bash --version
```

Confirme Python >=3.11. Releases com Python mais antigo não satisfazem o
bootstrap; não substitua `/usr/bin/python3` por um interpretador de estudo.
Depois use o setup para os perfis escolhidos, em vez de copiar uma lista de
pacotes de outra distribuição. Fedora, Arch e openSUSE usam seus próprios
gerenciadores e nomes declarados no manifesto.

### Runtimes e dependências dos estudos

| Recurso | Pré-requisito adicional |
|---|---|
| Python científico e JupyterLab | `.venv` preparada com o lock do estudo. O atalho `jlab` exige o grupo `notebook` com JupyterLab; `analytics` contém DuckDB Python, Polars e PyArrow no exemplo. |
| R e exemplo renv | R e pacote `renv` acessível na biblioteca do usuário antes de rodar `init.R`. Instale renv como usuário comum, seguindo a documentação oficial; não use sudo para instalar pacotes de estudo. |
| Java | JDK instalado e selecionado no ambiente, com JAVA_HOME correto quando utilizado. |
| Rust | Toolchain Rust com `rustc` e Cargo; prepare a versão exigida pelo projeto. |
| Go | Go instalado, disponível no PATH e compatível com o `go.mod` do projeto. |
| JavaScript, TypeScript e Astro | Node.js e o gerenciador adotado pelo projeto. TypeScript e Astro devem ser dependências do projeto quando necessários. |
| Quarto | Quarto CLI instalado separadamente. Compilar documentos também exige os kernels e pacotes do estudo; PDF pode requerer TeX/TinyTeX, conforme o formato. |
| GPU/PyTorch | Combinação compatível de hardware, driver, Python e wheels. O projeto não instala drivers ou CUDA. |

Os módulos Starship consultam runtimes disponíveis, mas não os instalam.
Siga o [guia científico](SCIENCE.md) e os exemplos de Python/R para criar os
ambientes. Fontes oficiais: [renv](https://rstudio.github.io/renv/articles/renv.html),
[Quarto](https://quarto.org/docs/get-started/), [Node.js](https://nodejs.org/en/download),
[Java](https://dev.java/learn/getting-started/), [Rust](https://www.rust-lang.org/tools/install)
e [Go](https://go.dev/doc/install).

### Pré-requisitos para reproduzir todos os testes

A suíte básica precisa de Python >=3.11, Bash, ShellCheck, shfmt, Bats, Chezmoi,
Zsh, Nushell, uv e direnv no PATH. Os novos cenários de ambientes Python usam
uv e direnv reais com HOME/XDG/cache temporários, sem downloads. Para não pular
os cenários opcionais, disponibilize também **eza, fzf, zoxide, R/Rscript,
renv, Node.js e Quarto**. O disparo manual do GitHub Actions prepara essas
ferramentas em runner descartável e recusa qualquer skip. Os testes com Java,
Rust e Go usam executáveis simulados e não instalam seus toolchains.
O cenário de listagem usa eza real e é pulado quando o executável está ausente;
o runner Ubuntu do CI o instala na preparação, junto com as demais ferramentas.

A matriz exige Docker acessível e rede durante o build. A suíte nas imagens é
executada sem rede e com usuário comum; isso não comprova a instalação de todos
os pacotes personal/extras de cada distribuição. O smoke online usa apenas uma
HOME temporária. Não altere permissões do socket Docker para contornar recusas.

Antes de considerar o ambiente pronto: abra uma nova sessão, confira a fonte,
rode doctor com os mesmos perfis aplicados e prepare o ambiente de cada estudo.
Veja o [alcance das verificações](VALIDATION.md) e os [erros comuns](TROUBLESHOOTING.md).

## Obter o projeto e escolher perfis

Na página do repositório no GitHub, abra **Code** e copie a URL de clone, ou
baixe o ZIP e extraia. Abra um terminal na pasta que contém `bootstrap.sh`.
Não execute comandos de uma cópia cujo conteúdo você não revisou.

Use `git clone --recurse-submodules` para incluir a fonte do template Python.
Em clones existentes, `git submodule update --init --recursive` obtém a revisão
fixada. O ZIP do GitHub não inclui o conteúdo dos submódulos; instalar `pyinit`
continua possível pelo manifesto, mas os testes exigem a fonte do template.

A [tabela de perfis](../README.md#perfis) descreve as combinações. Os exemplos
abaixo usam `personal,science`. Se escolher `personal,science,extras`, use essa
mesma seleção em setup, plan, diff, status, doctor e update.

## Instalação guiada

```bash
./bin/devshell setup --profile personal,science --dry-run
./bin/devshell setup --profile personal,science
```

O dry-run inspeciona permissões, ferramentas, pacotes e bloqueios, sem gravar
estado nem baixar arquivos. Para JSON, acrescente `--json` ao dry-run.
A execução efetiva percorre estas etapas:

1. Apresenta caminhos com permissões problemáticas. Após confirmação, remove
   apenas escrita de grupo/outros dos alvos permitidos, sem recursão. Symlinks,
   hardlinks, donos inesperados e ancestrais inseguros fora do escopo exigem
   correção manual.
2. Apresenta pacotes ausentes e mapeados. A execução administrativa tem uma
   confirmação própria; o gerenciador de pacotes pode perguntar novamente.
   Um pacote sem mapeamento bloqueia a tentativa administrativa parcial.
3. Mantém uv >=0.9.0 (>=0.13.5 com `science`), Chezmoi >=2.62.0, Nushell >=0.116.1 e Zsh >=5.9
   compatíveis já disponíveis. Versões antigas exigem atualização manual.
   Cada componente ausente de usuário tem plano e confirmação próprios.
   Plugins, fonte e Python passam por verificação idempotente.
4. Mostra o plano e o diff dos dotfiles. Responda `s` ou `sim` para aplicar.
   Conflitos exigem também a palavra `substituir`. Há backup dos arquivos
   preexistentes alterados.
5. Executa `doctor`. Código zero indica que as verificações do perfil passaram;
   seus limites estão em [Segurança](SECURITY.md).

Resposta vazia, `n` ou EOF cancelam a etapa. As etapas concluídas permanecem;
execute novamente para retomar. Reparos de permissões e instalações não fazem
parte do rollback dos dotfiles. O setup não aceita `--yes` ou `--approve` para
dispensar suas confirmações. `setup --json` exige `--dry-run`.

O componente DuckDB CLI de science é opcional: ausência ou caminho inseguro gera
aviso, sem instalação automática. O pacote Python DuckDB é uma dependência
independente do exemplo científico. Os pacotes de `extras` também variam por
release; omita o perfil se eles não estiverem disponíveis e você não desejar
instalá-los manualmente. `tldr --update` é uma operação manual de rede/cache.

## Primeiro acesso

```bash
zsh
./bin/devshell doctor --profile personal,science
```

Na sessão Zsh, confira `ls`, `la` e Ctrl+R. Selecione **FiraCode Nerd Font Mono**
no emulador; a instalação registra a fonte, mas não muda as preferências visuais.
Confira a família disponível com `fc-match 'FiraCode Nerd Font Mono'`.

Zsh lê `~/.config/zsh/.zshrc` por meio de `ZDOTDIR` em `~/.zshenv`; por isso não
é necessário criar outra cópia de `.zshrc` na HOME. Antes de aprovar `.zshenv`,
revise como migrar uma configuração Zsh anterior, pois não há mesclagem automática.

### Personalização da .zshenv

Mantenha `~/.zshenv` com o conteúdo gerenciado. Para exports e inicialização
pessoais que também precisam de shells não interativas, use
`$ZDOTDIR/.zshenv.local` (`~/.config/zsh/.zshenv.local` no default). Esse arquivo
é opcional, pertence ao usuário e não é criado nem sobrescrito pelo instalador.
Use modo 600 e diretórios sem escrita por grupo/outros; symlinks e hardlinks
não são aceitos. O carregamento exige o módulo nativo `zsh/stat`, verificado no Zsh local; sua ausência recusa
a extensão.

Revise o conteúdo antes de carregá-lo. Por exemplo, o arquivo pessoal pode
conter apenas:

```zsh
export MINHA_PREFERENCIA='valor pessoal'
```

Ao migrar uma `.zshenv` já personalizada, guarde uma cópia privada e mova apenas
as suas linhas para a extensão, preservando o conteúdo que já existir nela.
Revise o plano e o conflito antes de aplicar o bootstrap gerenciado com backup.
Não altere o registro de hashes para ocultar divergências. O rollback recupera
a `.zshenv` anterior e deixa a extensão pessoal intacta.

Doctor continua detectando qualquer alteração da `.zshenv` gerenciada e verifica
a segurança da extensão sem executar seu conteúdo. Não compile esses arquivos
com `zcompile`: os `.zwc` correspondentes não são suportados. Se um deles
existir, revise e remova ou mova somente esse cache para um backup privado antes
de repetir doctor/setup; nenhum cache é removido automaticamente.

A troca da shell de login é opcional e manual. Confira o caminho de Zsh em
`/etc/shells`; se `/usr/bin/zsh` for o caminho válido da máquina, execute
`chsh -s /usr/bin/zsh` e autentique-se no seu terminal. Encerre e reabra a sessão
do usuário. Se a política exigir administrador, peça sua intervenção. Bash
continua disponível para scripts; não altere `/bin/sh` nem os shebangs.

## Bash e Nushell

O `~/.bash_aliases` gerenciado inclui os aliases compartilhados. O Bash padrão
do Ubuntu já o carrega; em outras configurações, isso precisa ser conferido.
O `~/.bashrc` não é sobrescrito. Para as integrações adicionais do fragmento
Bash, revise-o e inclua manualmente no seu `~/.bashrc`:

```bash
source "${XDG_CONFIG_HOME:-$HOME/.config}/devshell/bashrc"
```

Use XDG_CONFIG_HOME absoluto ou seu default `~/.config`. Com eza selecionado e
disponível em sessão interativa, `l` substitui o atalho `l='ls -CF'` do Ubuntu
pela grade do eza. `la`, `ll`, `lla`, `lt` e `lta` oferecem as demais
[formas de listagem](USAGE.md#listar-localizar-e-ler-arquivos).
Use `command ls -CF` para executar a listagem do GNU ls diretamente.
No Bash, o projeto não substitui `cd` por zoxide.

Nushell é complementar. Inicie com `nu`; ela lê os arquivos `env.nu` e
`config.nu` em sua configuração XDG. Para diagnosticar uma configuração
alternativa, use `nu --env-config CAMINHO/env.nu --config CAMINHO/config.nu`.
O prompt Nu recebe o código de saída, mas não a duração do comando.

## Operação manual com hashes

Use esta sequência quando desejar controlar a aplicação separadamente:

```bash
./bin/devshell plan --profile personal,science --json
./bin/devshell diff --profile personal,science
# Revise o plano e copie o valor approval, usando exatamente o mesmo perfil.
./bin/devshell apply --profile personal,science --approve HASH_REVISADO
./bin/devshell doctor --profile personal,science
```

`HASH_REVISADO` é um marcador: substitua-o pelo hash exibido. Uma mudança no
conteúdo ou no estado invalida a aprovação. Conflitos exigem ainda
`--replace-existing`, após ler o diff. `apply` não instala ferramentas.

Se Chezmoi ou uv faltarem, planeje cada instalação e repita com o hash revisado:

```bash
./bin/devshell install --component chezmoi
./bin/devshell install --component chezmoi --approve HASH_DA_INSTALACAO
```

O mesmo fluxo atende `uv`, `nu`, `plugins`, `firacode`, `pyinit` e `python`. Para Python,
use também `--profile science` se quiser as ferramentas CLI declaradas. Se
`~/.local/bin` ainda não estiver no PATH, confira sua segurança e use
`PATH="$HOME/.local/bin:$PATH" ./bin/devshell ...` nessa sessão.
`sh bootstrap.sh` sem argumentos apenas planeja; com argumentos delega à CLI.

## Disponibilizar devshell no PATH

Instale opcionalmente um lançador em `~/.local/bin/devshell`, a partir da raiz
do checkout que deseja usar. A operação é local e funciona offline:

```bash
./bin/devshell install --component devshell --offline
# Revise checkout, conteúdo, modos, conflitos e hash exibidos:
./bin/devshell install --component devshell --offline --approve HASH_REVISADO
```

O lançador usa `/bin/bash` para executar o `bin/devshell` original. Não copia
as bibliotecas e não é um symlink: a CLI continua localizando suas fontes no
checkout. Ele funciona de qualquer diretório, preservando os argumentos.
Com `~/.local/bin` no PATH, use:

```bash
devshell --help
devshell project doctor
```

Se o PATH ainda não contiver esse diretório, abra uma nova sessão com os
dotfiles aplicados ou, após conferir sua segurança, acrescente-o nesta sessão
com `export PATH="$HOME/.local/bin:$PATH"`. O instalador não edita a shell.

Um arquivo diferente no destino, ou um registro divergente, exige a aprovação
do novo plano **e** `--replace-existing`. Arquivos anteriores ficam em backups
privados com seus modos registrados, sob
`$XDG_STATE_HOME/devshell/launcher-backups` (default `~/.local/state/devshell`).
O registro atual fica em `launcher.json`; doctor confere conteúdo e modos sem
executar o lançador. Repetir uma instalação já correspondente não escreve
arquivos, cache ou outro backup. Essa instalação é explícita e separada dos
perfis/setup; não instala pacotes do sistema.

Mantenha o checkout confiável no mesmo caminho. O lançador acompanha suas
atualizações; não fixa os bytes desse checkout. Se mover a cópia, execute a
instalação a partir da nova raiz, revise o plano e aprove a substituição com
backup. Se a origem desaparecer, o lançador falha com instrução de reinstalar.
`update` e rollback de dotfiles preservam essa instalação e seus registros.

## Atualizar configuração e versões

O caminho comum, depois de atualizar o checkout:

```bash
git pull
./bin/devshell setup
```

O setup usa os perfis lembrados (os do último `apply`), começa por um resumo e
só pergunta pelas etapas com algo a mudar. Exemplo numa HOME de teste com o
perfil `minimal` já aplicado:

```text
Resumo do setup (cada etapa pede a própria confirmação):
  permissões: em dia
  pacotes do sistema: em dia
  dotfiles: em dia
  perfis: em dia
Nada a fazer: tudo em dia.
Data Lab Dotfiles — setup
Perfis: minimal (lembrados)
Componentes: bash, zsh, git, uv, chezmoi
…
```

Numa HOME nova, o mesmo resumo lista o que falta, por exemplo
`dotfiles: atualizar (9 arquivo(s) a atualizar, 0 em conflito)` e
`perfis: registrar (minimal)`. Etapas que dependem de um reparo de permissões
aparecem como "reavaliado depois do reparo de permissões". Quem aplicou os
dotfiles antes desta versão roda `./bin/devshell setup --profile SEUS_PERFIS`
uma vez para registrar os perfis.

Para controlar cada passo, siga a operação manual. Para dotfiles, revise as
fontes em `dotfiles/` e o plano:

```bash
./bin/devshell update --profile personal,science
./bin/devshell diff --profile personal,science
./bin/devshell update --profile personal,science --approve HASH_REVISADO
```

`update` não executa git pull nem atualiza ferramentas. Versões e checksums
mudam por revisão de manifestos. O instalador recusa substituir arquivos de
artefatos com conteúdo diferente. Leia os destinos exatos do plano de install;
preserve o executável anterior em backup privado, confira-o e mova-o para essa
área antes de gerar um novo plano de instalação. Para uv, trate uv e uvx juntos.
Só restaure ao destino depois de conferir que não sobrescreverá outra alteração.

Esse procedimento foi testado para Chezmoi com executáveis artificiais; troca
de plugins, fontes e ferramentas uv exige avaliação própria. A troca de vários
arquivos não é atômica. Não a faça durante operações das ferramentas afetadas.
O [rollback](SECURITY.md#backups-e-recuperação) cobre dotfiles, não instalações.

## Offline e caminhos de usuário

`--offline` proíbe downloads e a execução administrativa de pacotes pelo setup.
Para artefatos, prepare o arquivo oficial exato no cache
`$XDG_CACHE_HOME/devshell/artifacts/SHA256`; conteúdo divergente é recusado.
Python usa o cache próprio de uv e interpretadores disponíveis.

Os defaults de configuração, dados e estado seguem XDG. Valores XDG relativos
usam os defaults da CLI. UV_PYTHON_INSTALL_DIR, UV_TOOL_BIN_DIR e UV_CACHE_DIR
absolutos podem ser definidos explicitamente; o projeto não os exporta
globalmente. As venvs das ferramentas ficam em `$XDG_DATA_HOME/devshell/tools`,
e as demais variáveis `UV_*` não valem para a instalação delas. UV_TOOL_DIR
continua validado quando definido, mas as ferramentas do projeto não o usam. A fonte fica em `$XDG_DATA_HOME/fonts/FiraCodeNerdFont`.
Confira mais opções em `./bin/devshell --help`.
