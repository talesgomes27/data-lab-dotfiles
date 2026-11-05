# Validação e compatibilidade

[Início](../README.md) · [Contribuição](../CONTRIBUTING.md) · [Limites de segurança](SECURITY.md)

## Estado atual

A versão é experimental. Há evidência local em Ubuntu 26.04 x86_64/glibc;
fixtures de adaptadores não certificam instalação em outras distribuições.
As execuções remotas do workflow `checks` estão disponíveis no
[GitHub Actions](https://github.com/talesgomes27/data-lab-dotfiles/actions/workflows/ci.yml).
O resultado de cada execução vale para o commit correspondente.

| Verificação | Resultado e alcance |
|---|---|
| Suíte local | 93 testes Bats e 35 unittest, ShellCheck e shfmt passaram na última verificação registrada de código. |
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

## Plataformas

| Ambiente | Evidência |
|---|---|
| Ubuntu 26.04, x86_64, glibc | Execução local com ferramentas reais e ambientes temporários. |
| Ubuntu 24.04, Debian 13, Fedora 44, Arch e openSUSE Leap 16.0 | Adaptadores/fixtures e imagens declaradas; matriz de containers não executada. |
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

- A primeira matriz de containers falhou em dois testes que pressupunham usuário
  comum, pois as imagens executavam como root; a revisão usa usuário sem privilégios.
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

O Docker recusou acesso ao socket; containers não foram executados. Na preparação
anterior ao primeiro envio, o CI remoto e os requisitos por PR ainda estavam
pendentes. A alteração do workflow foi revisada; não havia parser YAML
instalado para validação adicional. Consulte [Contribuição](../CONTRIBUTING.md#proteger-a-main)
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
distribuição. Os resultados da revisão completa serão registrados após sua execução.
