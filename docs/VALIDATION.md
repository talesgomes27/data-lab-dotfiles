# Validação e compatibilidade

[Início](../README.md) · [Contribuição](../CONTRIBUTING.md) · [Limites de segurança](SECURITY.md)

## Estado atual

A versão é experimental. Há evidência local em Ubuntu 26.04 x86_64/glibc e
suíte sem rede em cinco imagens x86_64/glibc. Fixtures de adaptadores e a suíte
em containers não certificam instalação de todos os pacotes de cada distribuição.
As execuções remotas do workflow `checks` estão disponíveis no
[GitHub Actions](https://github.com/talesgomes27/data-lab-dotfiles/actions/workflows/ci.yml).
O resultado de cada execução vale para o commit correspondente.

| Verificação | Resultado e alcance |
|---|---|
| Suíte local | 116 testes Bats e 35 unittest, ShellCheck e shfmt passaram, sem skips. Inclui 17 cenários novos de ambiente pessoal e seis de pyinit/setup, sem estender a evidência histórica da matriz. |
| CI manual completo | Sete jobs aprovados: runner Ubuntu 24.04 com 93 Bats e 35 unittest sem skips, cinco imagens de containers e smoke online. [Execução e alcance](#matriz-smoke-online-e-cenários-opcionais). |
| Configuração | Chezmoi real, aplicação, idempotência, conflitos, backup e rollback exercitados em HOME temporária. |
| Recuperação e guardas | Testes de interrupção/retomada de rollback, edição concorrente, backups corrompidos, symlinks/hardlinks, permissões e hashes. |
| Shells | Bash, Zsh e Nushell exercitados; aliases, prompt, plugins e hooks conferidos. PTY confirmou a inicialização Zsh. |
| Artefatos e uv | Instaladores de versões fixadas e componentes Python exercitados em HOME descartável; versões existentes compatíveis podem ser mantidas. |
| Ciência Python | Em cópia temporária: testes de estatísticas/imports, Parquet com Polars/PyArrow/DuckDB, dois pytest, Ruff e JupyterLab por linha de comando. |
| R/renv | Inicialização e execução do exemplo com R/renv locais, lock por projeto e recusa de caminhos preexistentes, inclusive symlinks pendentes. |
| Uso local dos perfis | Dotfiles aplicados com backup; doctor sem problemas/avisos na verificação posterior. Uma consulta DuckDB artificial retornou o resultado esperado. |
| Prompt e linguagens | Cenários de Git, Python, R, Java, Rust, Go, JavaScript, TypeScript, Quarto e Astro; Java/Rust/Go exercitados com executáveis simulados, sem instalar seus runtimes. |

As bibliotecas científicas foram verificadas em ambientes temporários; essa
evidência não afirma que estejam instaladas nos estudos de cada usuário.
O teste de JupyterLab por CLI não demonstra um fluxo completo de notebook no
navegador. A integridade conferida pelo doctor tem os limites de SECURITY.md.

## Template como submódulo e gerador science — 2026-11-05

O submódulo `templates/python-template-linux` e o manifesto `pyinit` fixam o
commit `3bb356f880d0577be535844cab879085e3801da9`. O SHA-256 do script obtido
pela URL pública corresponde aos bytes do submódulo. O
[PR do template](https://github.com/talesgomes27/python-template-linux/pull/1)
passou no CI com Python 3.11, 3.12 e 3.13, com conferência explícita do
interpretador de cada job; permanece aberto, sem merge.

- `bash scripts/check.sh`: 116 Bats e 35 unittest, ShellCheck, shfmt e sintaxe
  Python, sem skips. Os testes novos cobrem seleção por perfil, leitura sem
  escrita, correspondência manifesto/gitlink/bytes, aprovação, cache corrompido,
  destino divergente/symlink, idempotência, diagnóstico sem execução e
  confirmação própria do setup antes de instalar o gerador.
- Instalação real pela URL fixada, com HOME/XDG/cache temporários: checksum
  conferido e executável instalado com modo 755. `pyinit --help` funcionou.
- O comando instalado criou um projeto universal com uv real. `.envrc` continha
  somente `use devshell_python`, com modo 600; `.venv` tinha modo 700. Git ficou
  sem HEAD, stage ou remotos. Direnv continuou bloqueado; nenhum `allow` foi
  executado. O teste não alterou a HOME real.
- A revisão independente não encontrou problemas acionáveis no incremento.
  Containers e smoke online completo não foram repetidos para esta mudança;
  a matriz histórica abaixo corresponde ao código da execução indicada.

## Ambiente pessoal e direnv — 2026-11-05

Validação local em Ubuntu 26.04.1 x86_64/glibc, com uv 0.13.5, direnv 2.37.1,
Zsh 5.9 e Nushell 0.116.1. Os manifestos Python e as versões dos componentes existentes foram preservados.
`bash scripts/check.sh` passou: 110 testes Bats (17 novos), 35 unittest,
ShellCheck, shfmt e sintaxe Python; nenhum skip. Os ambientes dos novos testes
foram criados por uv real com `--offline --no-python-downloads` e o Python já
instalado, em HOME/XDG/cache temporários.

- Bash, Zsh e Nushell selecionaram `geral` em sessões interativas; a prioridade
  do interpretador de ativações herdadas foi preservada. Shells não interativas
  não ganharam ativação e o perfil work não recebeu a integração direnv.
- PTYs reais nas três shells verificaram abertura fora/dentro do projeto,
  subpastas, troca direta entre dois projetos e retorno ao ambiente pessoal.
  A navegação por zoxide foi exercitada no Zsh local.
- `.envrc` não autorizado permaneceu bloqueado. Em projetos autorizados,
  `activate` não foi executado; `.venv` ausente/insegura retirou o ambiente
  anterior e emitiu aviso. Conda ativo foi preservado com orientação de
  desativação explícita, sem simular a troca de estado de outro gerenciador.
- As guardas recusaram symlinks de diretórios/configuração e diretórios no
  lugar de executáveis. Nomes com espaços/metacaracteres no XDG funcionaram.
  Nushell aplicou remoções de variáveis, manteve PATH como lista e preservou
  o status anterior, inclusive ao receber recusa de autorização do direnv.
- Plan/diff/status/doctor e dry-run de apply/update/setup mantiveram hashes,
  modos e caminhos dos arquivos de configuração, ambientes e cache preparados.
  Rollback removeu o helper gerenciado, preservando `geral` e `.venv`.
- A revisão independente encontrou a aceitação indevida de diretórios como
  executáveis e levantou a borda Conda. Ambos receberam testes que falharam
  antes da correção; a suite completa passou após os ajustes.
- A ajuda da CLI foi conferida em HOME temporária; 100 links/âncoras locais
  e 36 blocos shell em 15 arquivos Markdown passaram nas verificações de
  destino/âncora e `bash -n`. Isso não executa a instalação dos exemplos.

Na etapa de implementação, nenhuma configuração foi aplicada à HOME real e
nenhum ambiente pessoal real foi criado. Na aplicação posteriormente autorizada,
os seis arquivos da integração foram aplicados com hash e backup, preservando
uma extensão privada preexistente na `.zshenv`. A inicialização Bash passou a
usar o fragmento devshell, com backup próprio, preservando o ambiente antigo.
O ambiente `geral` foi criado com CPython 3.13.11 já instalado, sem downloads.

A suíte foi repetida antes da aplicação: 110 Bats e 35 unittest, sem skips.
Na HOME aplicada, seis sessões PTY reais (Bash, Zsh e Nushell, iniciadas fora
e dentro do projeto) passaram em 30 verificações de interpretador, VIRTUAL_ENV,
versão, subpastas e retorno ao ambiente pessoal. O repositório Python de teste
foi criado em diretório temporário, autorizado individualmente e removido após
revogação da autorização; o teste não gravou histórico de comandos. O doctor
reportou somente a divergência preexistente e intencional na `.zshenv` privada,
que não foi sobrescrita nem teve seu registro de integridade alterado.

Não houve commit, push ou publicação. Outros repositórios continuam exigindo
preparo explícito e autorização individual. CI e Containerfile receberam o
pré-requisito direnv, mas a matriz, o CI remoto e o smoke online não foram
reexecutados para esta alteração.
A evidência de outras distribuições abaixo pertence à versão anteriormente
executada; não certifica os novos hooks nessas plataformas.

Uma verificação posterior em dois repositórios existentes reproduziu a recusa
de `.venv` por diretórios `0775`, incluindo um ancestral compartilhado. Foram
ajustados somente sete diretórios enumerados para `0755`, com conferência de
device/inode/dono/modo por descritor e registro dos modos anteriores, sem chmod
recursivo. Um `.envrc` contendo apenas `use devshell_python` foi criado e
autorizado no repositório que ainda não o possuía; o outro foi preservado.
As guardas existentes passaram a aceitar ambos os ambientes sem alteração de
código ou relaxamento de permissões exigidas pela integração.

As três shells passaram em 21 verificações de seleção, subpasta, troca direta
entre os projetos e retorno a `geral`: CPython 3.12.15 e 3.14.10 nas `.venv`
existentes e 3.13.11 em `geral`. Identidades dos diretórios, links dos
interpretadores e hashes de pyvenv.cfg, manifestos e locks foram preservados;
nenhuma `.venv` foi recriada ou sincronizada. No template Python, Ruff check,
Ruff format --check (17 arquivos) e três pytest passaram via `uv run` offline
com `--no-sync`, usando caches temporários. Nenhum dado de aplicação ou segredo
foi usado como fixture; não houve commit ou push.

## Plataformas

| Ambiente | Evidência |
|---|---|
| Ubuntu 26.04, x86_64, glibc | Execução local com ferramentas reais e ambientes temporários. |
| Ubuntu 24.04, Debian 13, Fedora 44, Arch e openSUSE Leap 16.0; x86_64/glibc | Builds e suíte offline como usuário comum aprovados no GitHub Actions: 88 Bats executados, cinco opcionais pulados e 35 unittest por imagem; ShellCheck e shfmt aprovados. |
| aarch64 e musl | Seleção de artefatos/normalização testada; sem execução de runtime. |
| Chezmoi aarch64 + musl | Sem artefato específico adotado; instalação manual. |
| Outras distribuições | Diagnóstico/fallback; sem certificação. |

As imagens usam tags que podem mudar. A disponibilidade de pacotes depende da
release. A primeira execução por plataforma pode exigir correções no mapeamento.

## Revisão da documentação

A reorganização centraliza instalação, uso e ciência; o README contém a
navegação e o glossário. Planos concluídos, entrega, inventário local e auditoria
antiga foram retirados após incorporar contratos e limitações ainda relevantes.
A licença MIT e a atribuição histórica foram preservadas. CLI, dotfiles,
manifestos e ambientes de usuário não foram alterados por esta revisão.

Verificação desta revisão documental:

- `bash scripts/check.sh` passou em uma cópia integral temporária: 92 Bats e
  35 unittest, ShellCheck e shfmt, sem skips.
- Os 18 arquivos Markdown tiveram 90 links/âncoras locais conferidos, sem destino
  ausente; 31 blocos shell passaram em `bash -n`.
- A ilustração SVG do README foi renderizada e inspecionada. Ela é um exemplo
  visual, não uma captura do ambiente nem evidência de suporte de plataforma.
- Não restaram referências aos arquivos de documentação removidos. Os ADRs e
  as instruções para agentes apontam para os guias atuais.
- O texto padrão MIT foi mantido, com atribuições histórica e atual em LICENSE.

Os checks de links e sintaxe não executam os comandos de instalação nem validam
páginas externas ou a renderização no GitHub. Nenhuma instalação real ou
publicação foi feita como parte desta reorganização.

## Limitações remanescentes

- A matriz não instala todos os pacotes personal/extras nem os runtimes dos
  estudos em cada distribuição. Os cinco cenários opcionais são cobertos
  no runner completo sem skips; cada imagem mantém esses cinco skips explícitos.
- Sem validação de runtime musl/aarch64, GPU/PyTorch ou aplicação Shiny.
- Sem teste visual completo do emulador/fonte ou de todas as interfaces de terminal.
- Atualização manual de Chezmoi testada com executáveis artificiais; outros
  componentes precisam de avaliação própria de atualização/recuperação.
- Dependências transitivas de ferramentas uv não têm lock único. O lock
  científico não certifica wheels nativas em todas as plataformas.
- Rollback é restrito a dotfiles regulares; instalações, permissões reparadas e
  pacotes administrativos exigem manutenção própria. ACLs/xattrs/capabilities e
  falhas persistentes de disco não têm garantia de recuperação automática.

Para reproduzir verificações e entender pré-requisitos, consulte
[Contribuição](../CONTRIBUTING.md). Registre resultados novos com plataforma,
comando, alcance e limitações, sem acrescentar históricos pessoais ao manual.


## Java, Rust e Go no Starship

Os módulos nativos `java`, `rust` e `golang` usam blocos coloridos no formato
existente. O teste novo foi observado falhando antes da configuração e passou
depois; cobre arquivos Java/Maven/Gradle, Rust/Cargo e Go, contexto misto,
diretório neutro e indisponibilidade dos executáveis. O Starship real renderizou
versões fornecidas por executáveis artificiais em HOME/XDG temporários, sem
rede ou instalação de toolchains.

`bash scripts/check.sh` passou com 93 Bats e 35 unittest, ShellCheck e shfmt,
sem skips. Os runtimes Java/Rust/Go reais não foram instalados ou exercitados;
a versão exibida depende do ambiente do usuário. O alcance de containers e
CI remoto continua o descrito acima.

A aplicação pelo devshell alterou somente a configuração Starship, com backup.
A fonte e o arquivo ativo coincidem; os três blocos renderizaram sem erros em
diretórios temporários. O doctor final retornou zero problemas, avisos e
alterações pendentes para personal,science,extras.


## Preparação para publicação

A revisão local passou com 93 Bats e 35 unittest, ShellCheck e shfmt, sem skips.
A cópia candidata foi indexada num Git temporário: 85 arquivos, sem caches,
estado de agentes ou credenciais de usuário. `git diff --cached --check` passou;
a busca por padrões conhecidos de credenciais e chaves privadas não encontrou
ocorrências. Isso não constitui garantia de ausência de todo tipo de segredo.
As URLs de artefatos do lock científico não contêm credenciais embutidas.

A licença MIT permanece na raiz. As exclusões de caches e diretórios locais
foram ampliadas; o job da suíte tem nome estável `checks`. A política está em
[main-ruleset.json](../.github/main-ruleset.json) e sua ativação é uma operação
separada do versionamento do arquivo.

O repositório público [data-lab-dotfiles](https://github.com/talesgomes27/data-lab-dotfiles)
foi criado via gh. O ruleset [Protect main](https://github.com/talesgomes27/data-lab-dotfiles/rules/26579758)
foi consultado na API e está ativo, com alvo `refs/heads/main`, sem bypass,
exigência de PR, conversas resolvidas, histórico linear, bloqueio de exclusão e
force push, e check `checks` do GitHub Actions (integration_id 15368).
São exigidas zero aprovações externas para permitir manutenção individual.
O check é dispensado na criação inicial da branch; atualizações posteriores
exigem aprovação do CI. Na preparação, o repositório ainda estava vazio: nenhum commit, push ou release
havia sido feito nessa etapa. A regra efetiva foi consultada mesmo sem a branch criada.

Na preparação local anterior ao primeiro envio, o Docker recusou acesso ao
socket; containers e CI remoto ainda não tinham sido executados. A alteração
do workflow foi revisada; naquela etapa não foi usado um parser YAML adicional. Consulte [Contribuição](../CONTRIBUTING.md#proteger-a-main)
para consultar ou aplicar a política em outro destino.

O Git local foi inicializado em main, com origin apontando para o repositório
criado. Somente os 85 arquivos revisados foram colocados no índice; não houve
commit ou push. A proteção no GitHub foi confirmada por leitura das regras
efetivas para main. A cópia local está preparada para o primeiro envio revisado.


## Primeiro envio e compatibilidade do CI

O commit inicial foi enviado à main com as regras ativas. A
[primeira execução](https://github.com/talesgomes27/data-lab-dotfiles/actions/runs/41949383235)
identificou um aviso SC2015 no ShellCheck do runner Ubuntu 24.04, antes de executar
os testes. A validação de argumentos foi reescrita com `if` explícito,
preservando a recusa de valores ausentes, vazios ou iniciados por outra opção.
Nove casos foram conferidos em HOME temporária, sem escrita.

A correção é integrada por PR e pelo check `checks` do GitHub Actions, usando
o mesmo ruleset. A consulta das regras não substitui o teste de rejeição de um
push direto. Os bloqueios de exclusão e force push são conferidos na política;
não se deve apagar ou reescrever a main apenas para testá-los.


### CI e proteção exercitados por PR

O [PR #1](https://github.com/talesgomes27/data-lab-dotfiles/pull/1) foi usado para
verificar o fluxo protegido. O envio direto do commit de correção à main foi
recusado com GH013, exigindo PR e o check `checks`. Enquanto os checks estavam
pendentes, a API retornou o PR como `BLOCKED`; nenhuma regra foi desativada.

A [execução de PR aprovada](https://github.com/talesgomes27/data-lab-dotfiles/actions/runs/41949774046)
exercitou o commit `30a9c84` no runner Ubuntu 24.04: ShellCheck, shfmt, 88 cenários
Bats e 35 unittest passaram. Dos 93 cenários Bats, cinco foram pulados por falta
de fzf, R, zoxide ou runtimes das linguagens; os cenários com executáveis
simulados continuaram cobertos. Containers e smoke online são jobs manuais e
não foram executados nesse evento. Isso não amplia a certificação multi-distro.


## Matriz, smoke online e cenários opcionais

A [primeira execução manual](https://github.com/talesgomes27/data-lab-dotfiles/actions/runs/41950981536)
executou os cinco builds e o smoke online. O smoke passou; as cinco suítes
falharam nos mesmos dois cenários de setup, por serem executadas como root.
A correção passa a rodar a suíte como usuário comum, sem enfraquecer os testes.

A revisão prepara fzf, zoxide, R/renv, Node.js e Quarto no runner manual e recusa
qualquer skip. Starship fixado e verificado também passa a ser instalado nas
imagens. O alcance da matriz continua sendo build, preparação das ferramentas
de teste e suíte sem rede; não é instalação nativa de todos os perfis em cada
distribuição. A
[segunda execução](https://github.com/talesgomes27/data-lab-dotfiles/actions/runs/41952069464)
aprovou as cinco imagens e o smoke online. O smoke verificou downloads,
instalações de usuário, configuração idempotente e rollback em HOME descartável;
DuckDB CLI permaneceu opcional e ausente.

Nessa execução, os dois cenários R/renv e a prévia fzf passaram. Os outros dois
revelaram uma exigência indevida de função onde zoxide 0.9.3 oferece alias e
timeout do Node pré-instalado no runner. O teste mantém todas as asserções de
navegação, aceitando função ou alias, e o CI prioriza o Node do apt. A suíte
local após essas correções passou com 93 Bats, 35 unittest, ShellCheck e shfmt,
sem skips.

A [execução completa corrigida](https://github.com/talesgomes27/data-lab-dotfiles/actions/runs/41952814746),
no commit `0435098`, aprovou os sete jobs. No runner Ubuntu 24.04 passaram
93 Bats e 35 unittest, ShellCheck e shfmt, sem skips. O passo que exige zero
skips também passou. Os cinco cenários antes omitidos foram exercitados:

| Cenário opcional | Resultado |
|---|---|
| Prévia fzf com aspas e substituição de comando no nome | Passou em PTY, sem executar o nome como código. |
| Exemplo R/renv | Criou o lock em cópia temporária e recusou reinicialização. |
| R com `.Rprofile` como symlink quebrado | Recusou sem criar o destino. |
| `cd` integrado ao zoxide em Zsh | Navegação por consulta, caminhos com espaços, subpastas, `..`, `-`, HOME e `z` passaram. |
| Starship com R, JavaScript, TypeScript, Quarto e Astro | Detecção com runtimes reais passou; Java/Rust/Go continuam cobertos com executáveis simulados. |

Cada uma das cinco imagens aprovou ShellCheck, shfmt, 88 dos 93 Bats e os
35 unittest, com cinco skips explícitos por ausência dos runtimes opcionais.
O smoke online repetiu com sucesso instalação de usuário, idempotência e duas
restaurações de rollback, sem operações administrativas durante o setup.

A documentação teve 100 links/âncoras locais conferidos, o YAML foi analisado
e os oito blocos `run` passaram em `bash -n`. As ajudas de devshell e bootstrap
retornaram zero em HOME temporária. A revisão de segurança conferiu a permissão
`contents: read` do workflow, downloads de CI fixados com SHA-256 e execução
sem privilégios nas imagens. Nenhum pacote foi instalado na máquina do usuário
nesta validação.
