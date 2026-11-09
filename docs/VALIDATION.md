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
| Suíte local com ferramentas em venv com hash | 196 testes Bats e 65 unittest, ShellCheck, shfmt, Ruff 0.17.3 e sintaxe Zsh/Python passaram, sem skips, em HOME/XDG temporários. Smoke online, ci-setup e matriz não executados. |
| Suíte local com histórico e poda | 180 testes Bats e 56 unittest, ShellCheck, shfmt, Ruff 0.17.3 e sintaxe Zsh/Python passaram, sem skips, em HOME/XDG temporários. Matriz de containers e smoke online não executados. |
| Suíte local após guarda estática e Python isolado | 164 testes Bats e 45 unittest, ShellCheck, shfmt, Ruff 0.17.3 e sintaxe Zsh/Python passaram, sem skips, em HOME/XDG temporários. Matriz de containers e smoke online não executados. |
| Suíte local da candidata de pin | 160 testes Bats e 42 unittest, ShellCheck, shfmt e sintaxe Zsh/Python passaram, sem skips. Inclui o novo smoke de recusa de configuração IDE vinculada pelo pyinit distribuído; sem estender a evidência histórica da matriz. |
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

## Matriz e smoke após o Bloco C — 2026-11-09

`workflow_dispatch` na branch do Bloco C, commit b57feba ([execução
42638571515](https://github.com/talesgomes27/data-lab-dotfiles/actions/runs/42638571515)):
`checks` com os cenários opcionais, `online-smoke` e os containers ubuntu e
debian passaram. O smoke instalou ruff, pre-commit e ipython com o uv real e
rede pelas venvs com hash, executou cada um pelo symlink e o `doctor` não
apontou nenhuma ferramenta. Fedora, arch e opensuse falharam por utilitários
ausentes nas imagens mínimas, não por código: `cmp` (diffutils) em 3 testes
anteriores aos Blocos A a C, e `find`/`xargs` (findutils) em 6 testes do
histórico no opensuse. `tests/Containerfile` passa a instalar diffutils e
findutils nas quatro famílias; a matriz com essa correção ainda não rodou.

Na migração da HOME real (uv 0.13.5), o `doctor` apontou pre-commit e ipython
como divergentes: os arquivos vieram em 664 porque o uv, com `--link-mode
copy`, copia os modos do próprio cache, criado antes com umask 002. O smoke não
pegou porque começa com cache novo. A instalação passa a tirar a escrita de
grupo e outros da venv criada na execução, sem seguir symlinks; o stub do
`setup.bats` reproduz os modos do cache e o teste novo falhou antes da correção.

## Venv com hash obrigatório para as ferramentas — 2026-11-09

Bloco C do [plano](plan.md) (R-020 a R-025), com o desenho revisto depois de
Q-001. `bash scripts/check.sh` em HOME/XDG temporários saiu com 0: 196 Bats,
65 unittest, Ruff limpo, sem skips. uv local: 0.13.5.

- Portão (T-201, `tests/uv_constraints.bats`, uv 0.13.5, offline, wheels
  locais): `uv tool install --constraints` instalou com o hash de uma
  dependência transitiva errado; o teste registra isso sem falhar. Por
  observação manual, fora da suíte, o mesmo valeu com `UV_REQUIRE_HASHES=1` e
  `--with-requirements`, e `uv pip sync --require-hashes` instalou sem a
  dependência ausente. `uv pip install --require-hashes -r LOCK` recusou o
  hash errado e o lock sem a dependência, e instalou com o lock correto, sem
  hardlink para o cache. `uv venv` cria em diretório vazio e recusa diretório
  com conteúdo.
- Locks (T-202): gerados do PyPI com cache temporário e sem configuração local;
  ruff com 1 pacote, pre-commit com 11 e ipython com 17 (um só no Windows).
  `uv pip install --dry-run --no-build --require-hashes` passou nas quatro
  plataformas x86_64/aarch64 com glibc e musl. Isso é resolução, não execução:
  aarch64 e musl seguem sem CI.
- CLI (T-203 a T-205): leitura dos locks com continuações, comentários,
  marcadores e nomes PEP 503, e recusa de lock ausente, sem hash, sem `==`,
  duplicado, com versão raiz ou minor do Python divergentes; estados ausente,
  link órfão, conflito e divergente em teste unitário, e sem link, conforme e
  repetição sem chamadas ao uv em Bats; bloqueio da instalação do `uv tool` no
  `setup --dry-run`, no `setup` (antes de qualquer `sudo`) e no plano, com a
  HOME idêntica; venv ativa de outro projeto e outra ferramenta do `uv tool`
  intactas, sem chamada `tool`; falha do `uv pip install` simulada remove a venv
  criada, não cria link e sai com 2; doctor aponta link ausente, versão
  divergente, distribuição fora do lock, dependência do lock ausente,
  interpretador diferente, RECORD divergente sem executar, launcher sem
  interpretador e módulo essencial ausente.
- A revisão do código achou e corrigiu: `safe_path` no lock recusaria checkouts
  com permissão de grupo; `python-done` recalculava o plano depois da
  instalação; quatro asserções `! comando` do Bats não falhavam o teste.
- Os testes de T-203 a T-205 foram escritos junto com o código, não antes,
  diferente do que o plano pede; só o portão T-201 veio antes. Como evidência
  substituta, os testes novos rodaram contra a `main` extraída por `git
  archive` numa pasta temporária: os 12 de R-021 a R-025 no `setup.bats`, os
  2 reescritos do `install.bats` e os unitários (o módulo nem existe lá)
  falharam.
- Revisão independente: um P1 corrigido (com `science`, uma permissão de grupo
  reparável virava bloqueio antes do reparo; agora as ferramentas são
  avaliadas depois dele, com teste) e os P2 e P3: plano em texto com estado,
  venv e link; piso do uv numa constante, com teste que recusa 0.13.4 só com
  `python-tools`; stub que registra o ambiente recebido, com mutação conferida
  (o teste falha se o ambiente do usuário vazar); guarda do caminho da venv
  antes de criar diretórios; interpretador obrigatoriamente no CPython
  gerenciado; RECORD lido com `csv`; mensagem própria para `sem-link`; filtro
  do smoke mais amplo.
- Segunda revisão independente, sem P0/P1. Entraram, cada um com teste que
  falhou antes da correção quando havia defeito: o `setup --dry-run` mostra o
  conflito do `uv tool` mesmo com reparo de permissão pendente (só lendo os
  links); `install --approve --json` volta a emitir um único documento, com o
  resumo das ferramentas no stderr; o teste do bloqueio antes do `sudo` agora
  tem um comando nativo pendente; e há testes de link para fora da venv no
  doctor, de falha na terceira ferramenta listando as concluídas e de execução
  pelo symlink. `RuntimeError` e `csv.Error` de uma venv corrompida viram
  diagnóstico, e os nomes do manifesto são validados antes de virar alvo de
  `chmod`. Não rodou uma terceira revisão sobre esses ajustes.

Não executados: o fluxo com uv real e rede (smoke online), o `ci-setup.sh` com o
Ruff na venv do CI e a matriz de containers, todos dependentes de um
`workflow_dispatch`; e a migração das instalações atuais na sua HOME, que é
manual.

## Execução semanal do CI — 2026-11-09

Bloco B do [plano](plan.md) (R-010). `tests/test_ci_workflow.py` lê o workflow
como texto: falhou nos 2 casos antes da mudança e passou depois. Ele confere o
`cron` `17 9 * * 1` em `on:` e que as quatro condições de `workflow_dispatch`
(dois passos de `checks`, `containers` e `online-smoke`) aceitam também
`schedule`.

Não executados: a primeira execução agendada, que só existe depois do merge na
`main`, e um `workflow_dispatch` nesta branch. O teste não valida a sintaxe
YAML; o PyYAML do Python da distribuição leu o arquivo sem erro, com o `cron` e
as condições dos jobs, mas a validação final é a do GitHub ao rodar.

Revisão independente sem P0/P1/P2. Entraram: igualdade exata da condição no
teste, gatilhos com linha em branco aceitos, nome do passo de zero skips sem
"disparo manual", e o aviso de atraso ou descarte em alta carga no
CONTRIBUTING. Fica fora deste bloco: o passo de zero skips só reconhece skips
do Bats, não do unittest.

## Histórico e poda de transações — 2026-11-09

Bloco A do [plano](plan.md) (R-001 a R-006). Testes escritos antes do código:
os 10 casos iniciais de `tests/history.bats` falharam em 9 (o de opções
inválidas já saía com 2) e os 3 de `TransactionHistory` falharam. Os 6 casos
Bats e 8 unitários acrescentados depois das três revisões independentes
cobrem comportamento já implementado e não foram vistos falhando antes. Nada
foi commitado entre teste e código, então essa ordem não está no histórico do
Git. Depois da implementação,
`bash scripts/check.sh` em HOME/XDG temporários saiu com 0: 180 Bats, 56
unittest, Ruff limpo, sem skips (já com os casos pedidos pela revisão
independente).

- Listagem: cadeia, status `rolled-back` fora da cadeia, entradas inválidas
  com motivo (diretório sem manifesto, symlink, nome `nao-hex`, temporário
  `.devshell-*`), manifestos antigos sem `created` também no `doctor`, e
  árvore de estado idêntica antes e depois (hash de todos os arquivos).
- Poda: plano sem escrita, inclusive com `--dry-run` e com `--dry-run
  --approve`; aviso quando não há transação atual; recusa, com remissão ao
  SECURITY e árvore inalterada, de `pending`, `rolling-back` e status
  desconhecido, de `pending` fora da cadeia (sem sugerir rollback), de
  diretório sem manifesto, manifesto com JSON inválido, temporário
  `.devshell-*`, symlink e nome fora do padrão; aprovação vencida ou com N
  diferente; remoção só do plano com `latest`, `current.json` e transações
  mantidas byte a byte iguais.
- Falha injetada no segundo esvaziamento: `transactions/` ficou só com
  transações inteiras; rollback, apply e nova poda funcionaram, e a poda
  seguinte limpou `pruning/`. Um symlink dentro da transação bloqueia o plano e
  o arquivo apontado fica intacto.
- Rollback depois de `--keep 1` remove `latest`; o seguinte responde "Nenhuma
  transação para restaurar." e um novo `apply` funciona. O caminho de falha do
  `apply` não precisou mudar: ele só restaura um `latest` que existia sob o
  mesmo lock que a poda usa.
- Os exemplos da USAGE são a saída de uma HOME de teste com três transações,
  com ids, hash e datas substituídos por marcadores.
- Três revisões independentes (relatórios na conversa, não versionados), sem
  P0/P1. Entraram: orientação específica para transação interrompida dentro e
  fora da cadeia, aviso sem transação atual, restos de `pruning/` visíveis na
  listagem e no plano, tipos do manifesto validados, `rmdir` pelo descritor do
  diretório pai, `pruning/` na revisão de permissões do setup, e testes de
  resto sem manifesto, resto inesperado, estado alterado sob o lock e ids
  removidos na mensagem de falha. A terceira revisão acrescentou: aviso ao
  podar a única cópia de um original substituído com `--replace-existing`,
  `previous_latest` validado como id antes do rollback usá-lo, aviso quando o
  rollback remove `latest` por manifesto anterior ilegível, ordem de remoção
  testada pela falha injetada (a primeira removida é a mais antiga), recusa de
  symlink trocado dentro de `pruning/` em `remove_private_dir`, e `pruning/` só
  criado quando há o que remover. Fica para decisão do usuário: D-004 trata
  igual manifesto anterior ausente e ilegível (agora com aviso); o usuário
  decidiu manter assim em 2026-11-09.

Limites: a poda não cobre `launcher-backups`, `permission-repairs` e outros
diretórios de estado (N-001). Matriz de containers não executada.

## Ruff no check — 2026-11-09

`ruff check --no-cache lib tests dotfiles scripts` com Ruff 0.17.3 (versão de
`manifests/python.json`) passou após dois ajustes: `check=False` explícito na
consulta de versão, que já conferia o código de saída, e `E402` ignorado só nos
testes, que definem o ambiente antes do import. O conjunto padrão do Ruff 0.17
apontava 33 itens, quase todos de estilo (ordem de imports, `with` aninhado);
as regras ficaram fixadas em `ruff.toml` para o resultado não mudar com o padrão
de outra versão. Um arquivo artificial fora do repositório confirmou F401, F821 e
B006. `bash scripts/check.sh` em HOME/XDG temporários: saída 0, 164 Bats e 45
unittest, sem skips.

Não executados: `scripts/ci-setup.sh`, que exige HOME `/tmp/foundry-*` e baixa o
Ruff do PyPI por `uv tool install` sem hash próprio (só a versão é fixada), a
matriz de containers e o workflow remoto. `examples/` e `templates/` têm projetos
e configurações próprios e não entram nesse lint.

## Guarda estática do Chezmoi e Python isolado — 2026-11-09

Achados S1 e S2 da auditoria local. Comando: `bash scripts/check.sh` com HOME,
XDG_CONFIG_HOME, XDG_DATA_HOME e XDG_CACHE_HOME temporários; saída 0, 164 Bats e
45 unittest, sem skips. Antes da correção, os novos testes falharam: a CLI
importou um `json.py` do PYTHONPATH e `env.sh` executou um `.pth` da `.venv`
herdada; `StaticChezmoiSource` não encontrava a guarda.

- `StaticChezmoiSource` cria fontes com cada prefixo de atributo do Chezmoi
  (inclusive `modify_`, `create_`, `symlink_`, `encrypted_`, `before_`/`after_`),
  sufixos `.tmpl`/`.literal`/`.age`/`.asc`, diretórios `exact_`/`external_`,
  `.chezmoiscripts` e `.chezmoiignore` e confirma a recusa sem chamar Chezmoi;
  `dot_modify_*` continua aceito como nome literal. A execução de `modify_` pelo Chezmoi vem da documentação
  oficial; não foi reproduzida localmente.
- `tests/isolated_python.bats` usa uma `.venv` uv offline com `.pth` hostil e
  PYTHONPATH com `json.py`: plan, doctor, status, install devshell e setup
  dry-run devolvem JSON sem carregá-los; `env.sh` em Bash e Zsh, Nushell e o
  helper direnv (com stubs da stdlib do direnv) também não os carregam.
  A ausência de bytecode continua garantida por `-B` e pelo
  `PYTHONDONTWRITEBYTECODE` já exportado; não há teste que separe os dois.
- A revisão independente sugeriu remover o `sys.path` de `state.py`; o teste
  reforçado mostrou que `doctor` importa `artifacts` sob `-I`, e a linha ficou.

Limites: a CLI e as shells passam a exigir `/usr/bin/python3`, como `project`
já exigia; um sistema sem esse caminho perde a filtragem de PATH nas shells e
recebe erro na CLI. Matriz de containers e
smoke online não foram executados.

## Configuração do Claude Code no projeto — 2026-11-08

O repositório passa a ter `.claude/settings.json`, um hook de lint shell, as
skills `/bump-pyinit` e `/entrega` e o subagente `matrix-runner`. Nada disso
muda o comportamento da CLI, dos perfis ou dos manifestos.

As regras `deny` recusam `sudo`, `chsh`, `chezmoi apply/update/init` e edições
nos destinos dos dotfiles na HOME real. As regras `ask` pedem confirmação para
`devshell apply/install/setup/update/rollback`, `bootstrap.sh` e a matriz de
containers. As regras de Bash comparam só o começo do comando, então
`env X=1 sudo` ou `cd x && chezmoi apply` dependem também das outras camadas.

O hook `PostToolUse` foi exercitado com eventos simulados: formatou `.sh` e
`.bats` com os argumentos do `check.sh`, devolveu saída 2 com o ShellCheck
(SC2086, SC2050) e com `zsh -n` num `dot_zshrc` inválido, e passou sem ação em
`.py`, arquivo ausente, evento sem caminho e JSON inválido. O script entrou nas
listas de ShellCheck e shfmt do `check.sh`. A suíte local passou com 160 Bats e
42 unittest, sem skips. As regras de permissão e o carregamento do hook, das
skills e do subagente pelo Claude Code não foram exercitados num cliente real.

## Candidata de pin A1–A6/F1 — 2026-11-06

Preparada em cópias Git independentes da base Data Lab
`75c53abf7a8bb902798b0a6f0c34766933cf3765`. Somente gitlink, entrada `pyinit`
do manifesto, teste de distribuição, guia de ciência, changelog e este registro
mudam. O checkout original não recebeu a candidata.

O pin proposto é `1d9e14154edac1c290409e6e41f36f1aa7330db4`, merge do
[PR #8 do template](https://github.com/talesgomes27/python-template-linux/pull/8),
incluindo A1–A6/A2-LF-01 e F1/P3. Gitlink, versão e URL usam esse SHA completo.
O script tem **66.910 bytes** e SHA-256
`ba8cba6b9ca32ada2c8101385120abcd846e073ce746df6c343f0cb91e36bd51`.
O conteúdo público retornado pelo conector GitHub para a URL fixada e pela API
de conteúdo coincide byte a byte com o checkout independente e o submódulo
da candidata. As demais entradas de `manifests/artifacts.json` são idênticas.

Validação local atual, em Ubuntu 26.04.1 LTS x86_64/glibc:

- A base congelada passou 159 Bats e 42 unittest, sem skips.
- A regressão nova instala o artefato somente em HOME temporária e apresenta
  uma configuração `.vscode/settings.json` por symlink para uma sentinela
  artificial. Com o pin antigo, o gerador anunciou sucesso em vez da recusa;
  com o novo, retorna 2 antes de chamar uv, preservando integralmente a HOME
  artificial. uv e Git do gerador são simulados nesse caso: nenhum runtime,
  pacote científico ou commit é criado pela regressão.
- `bash scripts/check.sh` passou **160 Bats e 42 unittest**, sem skips,
  incluindo ShellCheck, shfmt e sintaxe Zsh/Python. Os casos existentes cobrem
  hash aprovado, cache corrompido, destino divergente, idempotência, ajuda,
  diagnóstico sem execução do script e migração dry-run sem estado.
- HOME, XDG, cache e TMPDIR foram descartáveis. O runner usou Python 3.13.11,
  uv 0.13.5, Bats 1.13.0, ShellCheck 0.11.0 e shfmt 3.12.0; o Python em
  `/usr/bin/python3` é 3.14.4. Nenhuma ferramenta foi instalada para os checks.

Evidência anterior reaproveitada: a
[CI #16 do merge real do template](https://github.com/talesgomes27/python-template-linux/actions/runs/42311484199)
executou 246 testes em cada CPython 3.11.18, 3.12.16 e 3.13.18, com Ruff
0.17.1 e uv 0.13.7. O evento foi `push` em `main`, com head e checkout
`1d9e14154edac1c290409e6e41f36f1aa7330db4`. Esses testes não foram repetidos
nesta etapa e não constituem CI dos novos bytes do Data Lab.

O instalador foi testado offline com cache semeado; seu transporte HTTPS não
foi exercitado online nesta etapa. Não foram executados containers, CI desta
candidata, instalação na HOME real, servidor/navegador ou fluxo de JupyterLab
real. A wheel artificial das regressões do template comprova grupo, lock e
encaminhamento, sem homologar o aplicativo real ou equivalência científica.
Os resultados não ampliam suporte a outras distribuições ou arquiteturas.

O patch incremental inclui o gitlink. Sua reaplicação é conferida apenas em
outra cópia da base, com seleção explícita do novo commit no submódulo isolado.
Git não transporta todos os modos POSIX; a conferência de bytes, tipos, links
e bits executáveis é separada da preservação dos modos dos arquivos.

Os repositórios originais, seus índices, o `.envrc` pessoal e os binários
instalados são preservados. Não houve commit, push ou instalação na HOME real;
o `pyinit` instalado e a versão consumida pelo Data Lab continuam anteriores.
Aplicar o pin, publicar e reinstalar exigem etapas autorizadas separadamente.
Nenhum lançador, perfil, instalador ou comportamento de `project doctor` mudou.

## Pin de pyinit --migrate — 2026-11-06

Na etapa anterior, o submódulo e o artefato foram fixados no commit
`ee8cf5a0a0be0963c3ee4fbaf1d10181e6c2cdd4`, publicado no
[PR #3 do template](https://github.com/talesgomes27/python-template-linux/pull/3).
A URL usa esse SHA completo. O SHA-256
`a97b02ca983094b937d196499719f9228cd40b69065b5cbca876e6737780af1d`
foi conferido nos bytes do submódulo, no checkout do template e no download
público real de 57.761 bytes. As outras entradas do manifesto não foram alteradas.

O template passou localmente 125 pytest, incluindo sete integrações uv reais
offline com projetos e HOME/XDG/cache temporários. Cobrem requirements, Conda,
Poetry, Pipenv, setuptools, PEP 621 e uv fixado; uma wheel artificial foi
instalada e importada sem PyPI. A revisão para publicação corrigiu fontes dev
concorrentes, extras setuptools em string, pedidos de Python sem patch e a
resolução relativa do executável uv, com regressões RED→GREEN.

Neste Data Lab, `bash scripts/check.sh` passou 159 Bats e 42 unittest,
ShellCheck, shfmt e sintaxe Zsh/Python, sem skips. A nova regressão instala o
artefato em HOME temporária e confirma que `--migrate --dry-run` produz o plano
sem alterar nenhum arquivo/diretório da HOME artificial, criar ambiente ou
autorizar direnv. Ela falhou com o pin anterior e passou com o novo. Os checks
existentes continuam conferindo gitlink, versão, URL, checksum, aprovação e
recusa de artefatos divergentes/corrompidos.

O [CI remoto do template](https://github.com/talesgomes27/python-template-linux/actions/runs/42215180717)
passou nos três jobs Python 3.11, 3.12 e 3.13 para esse commit, incluindo Ruff e
pytest. O resultado não representa instalação nativa em outras distribuições.

O `pyinit` instalado e as configurações da HOME real não foram atualizados.
Instalar a nova versão exige uma operação aprovada separada do componente;
`devshell update` não reinstala o gerador. Não foram migrados projetos reais
nem executados containers ou novo teste em PTY. Os resultados de CI remoto
devem ser conferidos nos PRs de cada repositório; os checks locais não ampliam
a evidência de distribuições ou de equivalência científica.

## Publicação coordenada do template e dos dotfiles — 2026-11-06

Os PRs [#2 do template](https://github.com/talesgomes27/python-template-linux/pull/2)
e [#5 dos dotfiles](https://github.com/talesgomes27/data-lab-dotfiles/pull/5)
foram integrados, nessa ordem. As mains locais foram sincronizadas por
fast-forward, preservando o submódulo no commit revisado `3a79c49`.
A atualização posterior da README documenta lançador, aliases, criação e
manutenção de projetos e os limites da evidência de plataformas. Seus links
internos, âncoras, exemplos de ajuda e `git diff --check` foram conferidos;
não altera comportamento, versões ou arquivos da HOME do usuário.

O [PR #2 do template](https://github.com/talesgomes27/python-template-linux/pull/2)
publicou o commit `3a79c49eb0788f00eaf46457d9510f0be1aa44f9`.
Seu [CI remoto](https://github.com/talesgomes27/python-template-linux/actions/runs/42163374186)
passou nos três jobs Python 3.11, 3.12 e 3.13, incluindo conferência do runtime,
Ruff e pytest. A revisão independente do conjunto não encontrou achados
acionáveis e repetiu 51 Bats focais, dois unittest do lançador e 41 pytest.

Gitlink, versão e URL de `pyinit` no manifesto foram atualizados para esse
commit público. O script baixado da URL fixada coincidiu byte a byte com o
submódulo: SHA-256
`c28a9d5d34a7f254bf02819937100b0ca30f02da95e564ada29fff1017c85a07`.
A suíte completa foi repetida com esse pin e passou em 158 Bats e 42 unittest,
sem skips. A instalação offline de `pyinit` usou o download conferido em cache
temporário; junto com o lançador instalado por hash, o gerador executou a
manutenção por PATH sem override e confirmou `geral → .venv → geral` com uv e
direnv reais, preservando ambiente, interpretador e lock.
Os resultados do próprio Data Lab devem ser consultados por commit no PR e no
[workflow checks](https://github.com/talesgomes27/data-lab-dotfiles/actions/workflows/ci.yml);
a evidência local abaixo não substitui esse resultado remoto.
Publicação e merge de branches/PRs não aplicam arquivos na HOME nem atualizam
a cópia de `pyinit` instalada; instalações continuam exigindo aprovação própria.

## Lançador local devshell — 2026-11-06

`bash scripts/check.sh` passou com 158 Bats e 42 unittest, sem skips, além de
ShellCheck, shfmt e sintaxe Zsh/Python. Foram acrescentados oito Bats e dois
unittest de fronteira; a revisão independente não encontrou achados acionáveis.
As fixtures usaram HOME/XDG/cache temporários:

- Plan/dry-run e aprovação inválida não criaram estado. Instalação offline
  criou lançador `755` e registro `600`, sem cache/download; repetir o plano
  correspondente não reescreveu arquivos nem criou outro backup.
- Conflitos foram preservados sem `--replace-existing`; substituição aprovada
  guardou bytes e modos anteriores em backups privados. Aprovação vencida,
  symlink, hardlink e caminho de backup inseguro foram recusados.
- Falha simulada na gravação de backup preservou o arquivo original; falha
  posterior no registro manteve backup exato e journal `partial` com as etapas
  concluídas. Os registros ficam separados das transações de dotfiles.
- Um checkout com espaços, aspas e expressão shell literal foi instalado e
  executado de outra pasta sem interpretar o caminho ou perder argumentos.
  Checkout movido produziu erro com instrução de reinstalar, sem procurar
  outra cópia. Doctor detectou arquivo divergente/removido sem executá-lo.

O template standalone passou em 41 pytest (38 do gerador), Ruff check/format
e diff; o novo teste confirma descoberta de `devshell` no PATH sem override.
Uma integração adicional instalou o lançador em HOME temporária e executou o
novo modo de manutenção com backend, uv e direnv reais, sem `DEVSHELL_BIN`.
Preservou `.venv`/interpretador/configuração/lock, confirmou reparo não
recursivo e `geral → .venv → geral`, além das recusas de sync/lock desatualizado.

Ajuda, exemplos e `git diff --check` foram conferidos. A validação local não
aplicou arquivos na HOME real nem repetiu containers. O lançador referencia
o checkout confiável e acompanha
suas atualizações; não é uma cópia autossuficiente nem um pin de suas fontes.
Instalação é explícita, separada dos perfis/setup e do rollback de dotfiles.

## Aliases de listagem eza — 2026-11-06

`bash scripts/check.sh` passou com 150 Bats e 40 unittest, sem skips, além de
ShellCheck, shfmt e sintaxe Zsh/Python. A revisão independente não encontrou
achados acionáveis. Os testes pertinentes falharam antes da implementação e
passaram após incluir os seis aliases exatos solicitados.

- Bash e Zsh interativos carregaram `l`, `la`, `ll`, `lla`, `lt` e `lta` pelo
  fragmento compartilhado, preservando argumentos com espaços. `ls` manteve
  seus argumentos anteriores; `l` substituiu o alias padrão Ubuntu sem enviar
  `-CF` ao eza.
- Shells não interativas e perfil sem eza não receberam os seis atalhos.
- Eza real 0.23.4 executou os seis atalhos nas duas shells em diretório
  temporário, incluindo árvore e arquivos ocultos. A ausência do executável
  provoca skip somente nesse cenário real; testes de argumentos usam fixture.

O runner Ubuntu do workflow passou a preparar eza para o novo cenário. O
[pacote Noble](https://packages.ubuntu.com/noble/utils/eza) é 0.18.2; uma consulta
à fonte oficial confirmou `ext` como alias de `extension` no
[parser de ordenação](https://github.com/eza-community/eza/blob/v0.18.2/src/options/filter.rs#L60)
e o estilo `relative` na
[declaração de opções](https://github.com/eza-community/eza/blob/v0.18.2/src/options/flags.rs#L61).
Essa inspeção não substitui execução real no runner; consulte o CI da
publicação coordenada. Containers não foram repetidos. Nenhuma ferramenta
foi instalada no sistema local nem configuração aplicada na HOME real.
Ícones dependem da fonte selecionada no emulador; não houve teste
visual da fonte.

## Orquestração do reparo pelo gerador Python — 2026-11-06

`bash scripts/check.sh` passou com 148 Bats e 40 unittest, sem skips, após a
revisão independente. Duas regressões novas falharam antes da correção e
passaram depois: o reparo consome somente a própria linha de confirmação por
pipe e recusa EOF após `s` sem Enter. Não foram alteradas as guardas de caminhos,
o hash aprovado, o chmod por descritor ou os registros de reparo.

O checkout standalone do template passou em 40 pytest (37 do gerador), Ruff,
ShellCheck, shfmt e ajuda/diff. A revisão identificou também o redirecionamento
de lock por workspace uv. Um teste com uv real offline comprova agora recusa
antes do reparo, sem alterar o lock ancestral.

A integração adicional do novo modo `--fix-permissions --sync --allow-direnv`
usou backend real deste Data Lab, uv 0.13.5 e direnv 2.37.1 em HOME/XDG/cache
temporários, com projeto artificial sem dependências. Comprovaram-se:

- Confirmações independentes e interrupção após recusa/falha, sem autorização
  direnv posterior; lock desatualizado não foi reescrito.
- Reparos restritos à cadeia diagnosticada e registros privados, preservando
  modos de filhos fora dela e inode/configuração/interpretador da `.venv`.
- Sync limitado à `.venv` local apesar de overrides herdados apontarem para
  outro destino artificial; `uv.lock` preservado com `--locked`.
- Seleção `geral → .venv → geral`, incluindo PATH, por exportações reais do
  direnv. Não foi novo teste de inicialização em PTY ou de todas as shells.

A publicação coordenada atualizou submódulo e manifesto para o commit
revisado; a correspondência de bytes/hash/gitlink é verificada pela suíte.
Não houve aplicação na HOME real, recriação de ambientes do usuário ou nova
matriz de containers. O sync real deste incremento
não testou downloads de dependências dos arquétipos nem builds externos.

## Diagnóstico e reparo de permissões de projetos — 2026-11-06

`bash scripts/check.sh` passou com 146 Bats e 40 unittest, sem skips, além de
ShellCheck, shfmt e sintaxe Zsh/Python. O incremento acrescentou 17 Bats e quatro
unittest. As fixtures usaram HOME/XDG/cache privados e .venv criada por uv real
com `--offline --no-python-downloads`; nenhum pacote foi sincronizado.

- Doctor/dry-run relataram os caminhos e modos exatos sem criar estado. EOF,
  resposta negativa e aprovação vencida recusaram o reparo. Confirmação guiada
  e hash explícito funcionaram; o estado saudável não criou novo registro.
- Somente diretórios próprios na cadeia aprovada perderam escrita de
  grupo/outros. Filhos fora da cadeia, arquivos, inode da .venv, interpretadores
  e autorização direnv foram preservados. Symlinks, UID inesperado, caminhos
  fora da HOME e estrutura de ambiente ausente bloquearam a operação.
- Substituição de inode, inclusive durante open, foi recusada por descritor.
  O registro privado preservou modos anteriores e caminhos concluídos também
  na falha parcial simulada. Alterar o código após revisão invalidou o hash.
- As regressões de segurança falharam antes dos ajustes: Python ativo no PATH,
  `sitecustomize` injetado por PYTHONPATH e bytecode persistido pelo modo isolado.
  O comando agora usa `/usr/bin/python3 -I -B`; doctor/dry-run em cópia limpa
  não executaram o payload nem criaram .pyc/estado. Diretório do registro sob
  HOME insegura apareceu como bloqueio prévio. A revisão independente confirmou
  as correções, sem novos achados concretos no delta final.
- Na revisão para publicação, uma reprodução mostrou utilitários homônimos da
  .venv ativa sendo executados antes do diagnóstico. O teste com dirname,
  uname, getconf, ldd e grep falhou antes da correção. A resolução de ROOT passou
  a usar builtins Bash e os comandos project deixaram de detectar plataforma;
  doctor e dry-run passaram sem iniciar os stubs. A ajuda também foi conferida
  chamando `bash devshell` a partir de bin, sem slash no nome do script.
- A integração real do direnv apresentou as permissões e caminhos recusados,
  com orientação para reparo explícito. A saída do helper para PATH continuou
  limpa, com explicações somente em stderr.
- No projeto real já corrigido manualmente, doctor e dry-run retornaram zero,
  sem problemas ou permissões pendentes. Os dois helpers da HOME foram
  atualizados com hash e backup transacional. As permissões do projeto,
  .envrc/.venv existentes e personalização Zsh ficaram intactos; doctor da HOME
  terminou sem problemas/avisos. Ajuda, 96 destinos de links locais e 42 blocos
  shell foram conferidos.

A matriz de containers não foi repetida para este incremento. O resultado do
CI de publicação deve ser consultado no PR do commit correspondente. A verificação
é de caminhos/metadados, não auditoria dos pacotes do ambiente ou proteção contra
escritores do mesmo UID.

## Extensão pessoal Zsh e doctor — 2026-11-05

Validação local em Ubuntu 26.04.1 x86_64/glibc, Zsh 5.9 e módulo nativo
`zsh/stat`. `bash scripts/check.sh` passou com 129 Bats, 36 unittest,
ShellCheck, shfmt e sintaxe Zsh/Python, sem skips. Foram acrescentados 13 Bats
e um unittest; a matriz de containers e o CI remoto não foram repetidos.

- Carregamento real da extensão em Zsh não interativa, no escopo global, com
  XDG contendo espaços e PATH sem programas externos. `typeset` e exports
  foram preservados. Arquivo ausente não criou estado nem emitiu aviso.
- Recusa de permissões de grupo/outros, ancestrais inseguros, symlinks,
  hardlinks, diretório/FIFO no lugar do arquivo, componente `..` e módulo de
  stat indisponível. A exceção sticky exige diretório do sistema; a regressão
  de arquivo regular foi testada simulando apenas o UID raiz do filesystem,
  sem chown ou execução privilegiada.
- A revisão independente identificou a preferência do Zsh por bytecode `.zwc`
  e a exceção sticky indevida para arquivo regular. As reproduções falharam
  antes das correções e passaram depois. Bytecode real criado por `zcompile`,
  mais novo que o texto, foi recusado inclusive por symlink. A revisão confirmou
  também recusa de symlink quebrado e não encontrou outros problemas acionáveis.
- Doctor/setup sinalizaram caches compilados dos quatro arquivos envolvidos.
  Inspeções não executaram conteúdo pessoal; modificar o bootstrap gerenciado
  continuou produzindo divergência de hash. As guardas de aprovação, conflito,
  backup e rollback foram preservadas.
- Migração e rollback passaram com fixtures privadas. Na aplicação local
  autorizada, o trecho pessoal foi preservado byte a byte em arquivo modo 600;
  o bootstrap anterior ficou no backup transacional. As exportações Zsh antigas
  e novas foram comparadas por digest, sem registrar valores privados. Doctor
  terminou sem problemas/avisos; plan não apontou mudanças ou conflitos, e setup
  dry-run não encontrou permissões problemáticas ou bloqueios. Ambientes
  existentes e o arquivo privado referenciado ficaram intactos.

O código pessoal continua fora do conteúdo gerenciado; esses testes não auditam
suas instruções nem fornecem sandbox ou proteção contra escritores do mesmo UID.
As evidências desta seção são locais; a integração remota deve ser conferida
no PR do commit correspondente.

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
- O primeiro CI de PR expôs interferência do `compinit` global do Ubuntu no
  teste PTY. A falha foi reproduzida localmente com uma completion insegura
  artificial. O teste passou após usar `zsh -d -i`, carregando o rc gerenciado
  sem o rc global da distribuição. A guarda `compinit -i` permaneceu intacta;
  nenhum diretório do sistema ou da HOME real teve permissões alteradas.
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
