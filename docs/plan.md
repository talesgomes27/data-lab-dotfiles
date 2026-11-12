```yaml
pipeline: pre-code-pipeline
gate: PC-5
estado: aprovado
modo: por-efeito
esforco: rigoroso
aprovacoes:
  - item: spec (PC-2) e decisões D-001 a D-008 (PC-3)
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Aprovar e seguir' na conversa"
  - item: plano (A1), com os ajustes em D-003/D-004 e as decisões D-009/D-010
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Aprovar o plano' na conversa"
  - item: entrega do Bloco A (A3, T-001 a T-006) e commit na branch
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Aceito a entrega, pode commitar' na conversa"
  - item: manter D-004 (manifesto anterior ilegível remove latest, com aviso)
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Pode manter como está' na conversa"
  - item: entrega do Bloco B (A3, T-101) e commit na branch
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'aceito a entrega, pode realizar o commit' na conversa"
  - item: novo desenho do Bloco C após Q-001 (spec v3, D-007, D-008, D-010 a D-013, ADR 004 revisto)
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Aprovar o desenho' na conversa"
  - item: plano revisto do Bloco C (A1, T-201 a T-206), com os achados do plan-reviewer incorporados
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Aprovar o plano' na conversa"
  - item: entrega do Bloco C (A3, T-201 a T-206), com os testes de T-203 a T-205 escritos junto com o código e a rodada contra a main como evidência substituta
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'aceito' na conversa"
  - item: desenho do Bloco D (spec v4, R-040 a R-045, D-014 a D-019; Q-004 pela D-015)
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Aprovar o desenho' na conversa"
  - item: plano revisto do Bloco D (A1, T-301 a T-307), com os achados do plan-reviewer incorporados
    por: usuario
    em: "2026-11-09"
    evidencia: "resposta 'Aprovar o plano' na conversa"
  - item: execução do T-900 até o fim (commit, push e workflow_dispatch na branch), sem o merge
    por: usuario
    em: "2026-11-12"
    evidencia: "resposta 'Siga o plano até o final. Só peça autorização para o merge.' na conversa"
  - item: Q-003 respondida (manter a notificação padrão do GitHub) e correção dos P3 da revisão do T-900
    por: usuario
    em: "2026-11-12"
    evidencia: "resposta 'Opção 1. Após pode corrigir os P3' na conversa"
  - item: desenho do Bloco E (spec v6, R-050 a R-054, D-022 a D-026, N-010 a N-013), com escopo "retirar órfãos" e órfão editado preservado
    por: usuario
    em: "2026-11-12"
    evidencia: "respostas 'Retirar órfãos (Recomendado)', 'Preservar e desregistrar (Recomendado)' e 'Aprovar o desenho' na conversa"
revisao_do_plano:
  por: subagente plan-reviewer
  em: "2026-11-09"
  resultado: "pronto com ressalvas; P1 e P2 incorporados (spec v2, D-003/D-004 ajustadas, D-009/D-010 novas)"
revisao_do_bloco_c:
  por: subagente plan-reviewer
  em: "2026-11-09"
  resultado: "não pronto; 4 P1, 9 P2 e 7 P3 incorporados (D-008, D-010, D-012 detalhadas; T-204 e T-205 reordenadas)"
revisao_do_bloco_d:
  por: subagente plan-reviewer
  em: "2026-11-09"
  resultado: "não pronto; 5 P1, 8 P2 e 6 P3 incorporados (spec v5: R-040 e D-014 a D-019 detalhadas)"
revisao_do_bloco_e:
  por: subagente revisor de plano
  em: "2026-11-12"
  resultado: "pronto com ressalvas; 7 P2 e 9 P3 incorporados (spec v7: R-055 e D-027 novos, R-050 a R-054 detalhados, D-014 ajustada)"
revisao_t900:
  por: subagente revisor independente
  em: "2026-11-12"
  resultado: "sem P0/P1; 2 P2 e 4 P3. P2 do apply (transação vazia) corrigido; o P2 do interpretador gerenciado foi corrigido depois (D-020); os P3 ficam registrados em docs/VALIDATION.md"
dispensas:
  - gate: PC-1
    motivo: sem fontes de dados a perfilar
  - gate: PC-4
    motivo: nenhuma estrutura antecede o código; os locks nascem em T-202
proximo_passo: apurar a origem do registro de perfis errado (ROADMAP, item 0); depois, aprovação do usuário do plano revisto do Bloco E antes do código
pendencias: ["R-010: execução agendada na main"]
```

# Plano: histórico de transações, CI agendado, lock das ferramentas uv, setup simplificado e retirada de órfãos

Requisitos em [spec.md](spec.md); decisão do lock no
[ADR 004](ADR/004-lock-ferramentas-uv.md). A ordem segue o pedido: itens 1 e 2,
depois o 3, depois o 4. Cada bloco termina com `bash scripts/check.sh` verde e
pode ir num PR próprio.

Onde cada verificação roda:

- **Local offline:** `bash scripts/check.sh` com HOME/XDG/cache temporários
  (Bats, unittest, ShellCheck, shfmt, Ruff). Vale para todas as tarefas.
- **Local com rede:** só T-202, que consulta o PyPI com cache temporário.
- **CI remoto:** `workflow_dispatch` na branch de trabalho para a matriz e o
  smoke online (T-101, T-206); a primeira execução agendada só existe depois
  do merge na `main`.

## Bloco A: histórico e poda (itens 1 e 2)

### T-001 Testes do histórico e da poda, antes do código
- Requisitos: R-001, R-002, R-003, R-004, R-005, R-006
- Objetivo: fixar o comportamento esperado em testes que falham hoje.
- Arquivos: `tests/history.bats` (novo), `tests/test_boundaries.py`
- Dependências: nenhuma
- Critério de aceite: cada critério de R-001 a R-006 tem ao menos um teste com
  o ID no nome, incluindo: falha injetada no meio da poda seguida de rollback,
  apply e nova poda; os três órfãos realistas (diretório sem manifesto,
  temporário `.devshell-*` dentro da transação, `pending` fora da cadeia);
  status desconhecido; aviso sobre a primeira transação da cadeia. Todos falham
  pelo motivo esperado (flag desconhecida ou função ausente), e o restante da
  suíte continua verde.
- Verificação: `bats tests/history.bats` e
  `python3 -m unittest tests.test_boundaries` falham só nos testes novos.

### T-002 Opções `--list`, `--prune` e `--keep` na CLI
- Requisitos: R-001, R-003
- Objetivo: aceitar as opções só em `rollback` e recusar combinações inválidas.
- Arquivos: `bin/devshell`
- Dependências: T-001
- Critério de aceite: `--keep` exige inteiro >= 1 e `--prune`; `--list` não
  aceita `--prune`, `--approve` nem `--keep`; fora de `rollback` as três saem
  com 2; `--help` descreve as opções; `--dry-run` com `--prune` só planeja.
- Verificação: testes de parsing de T-001 passam; `bin/devshell --help` exibe
  as linhas novas.

### T-003 `created` e listagem
- Requisitos: R-001, R-002
- Objetivo: gravar `created` em UTC nas transações novas e listar todas.
- Arquivos: `lib/state.py`
- Dependências: T-002
- Critério de aceite: enumeração única das transações reaproveitada por T-004,
  que classifica cada entrada (válida ou inválida, com motivo) sem lançar
  exceção; a listagem mostra as inválidas, a poda as recusa. A listagem não cria
  `$XDG_STATE_HOME/devshell` nem chama `locked()`.
- Verificação: testes R-001 e R-002 passam; `find "$HOME"` igual antes e depois.

### T-004 Plano e execução da poda
- Requisitos: R-003, R-004, R-005
- Objetivo: selecionar pela cadeia a partir de `latest`, calcular o hash (D-003)
  e remover só o aprovado, sob `locked()`.
- Arquivos: `lib/state.py`
- Dependências: T-003
- Critério de aceite: recusas de R-004 antes de qualquer remoção, só com status
  `committed`, `rolled-back` ou `failed-restored`; hash com `latest` e N (D-003);
  replanejamento sob o lock; cada `delete`, da mais antiga para a mais nova, é
  renomeada para `devshell/pruning/ID` e só então esvaziada com `dir_fd` e
  `O_NOFOLLOW` (D-009); restos em `pruning/` de uma poda interrompida são
  limpos na seguinte; falha parcial lista os ids removidos e sai com 2.
- Verificação: testes R-003 a R-005 passam, inclusive o de hash vencido e o de
  symlink dentro da transação.

- Desvio registrado na execução: `lib/setup.py` passou a incluir `pruning/` na
  revisão de permissões do setup (teste em `tests/test_setup.py`), para uma
  permissão insegura ali não bloquear a poda sem diagnóstico.

- Desvio registrado na execução: as transações fora da cadeia são removidas
  antes das da cadeia, e as da cadeia da mais antiga para a mais nova; assim a
  parte restante da cadeia continua contígua a partir de `latest`. O plano de
  poda também avisa sobre transações que guardam a única cópia de um original
  substituído com `--replace-existing`, além da primeira da cadeia.

### T-005 Rollback na borda do histórico
- Requisitos: R-006
- Objetivo: aplicar D-004 em `rollback()` e no caminho de falha de
  `apply_configuration()`.
- Arquivos: `lib/state.py`
- Dependências: T-004
- Critério de aceite: com `previous_latest` ausente ou sem `manifest.json`
  legível, `latest` é removido; `rollback` seguinte responde "Nenhuma transação para restaurar.".
- Desvio registrado na execução: o caminho de falha de `apply_configuration()`
  não mudou, porque ele só restaura um `latest` lido sob o mesmo lock que a poda
  usa, e a poda nunca remove `latest`.
- Verificação: teste R-006 passa; testes atuais de `tests/transactions.bats`
  e `test_repeated_rollback_restores_previous_transaction` continuam verdes.

### T-006 Documentação do bloco A
- Requisitos: R-030
- Objetivo: USAGE com exemplos executados, SECURITY (irreversibilidade e tabela
  de recuperação), ARCHITECTURE, CHANGELOG e VALIDATION.
- Arquivos: `docs/USAGE.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`,
  `CHANGELOG.md`, `docs/VALIDATION.md`
- Dependências: T-005
- Critério de aceite: exemplos de USAGE rodados em HOME temporária com a saída
  conferida; SECURITY traz o procedimento manual para cada entrada inválida
  que bloqueia a poda e avisa que a primeira transação guarda os originais;
  VALIDATION registra comando, resultado e limites.
- Verificação: `bash scripts/check.sh` verde; leitura do diff de docs.

## Bloco B: CI agendado (item 3)

### T-101 Execução semanal do workflow
- Requisitos: R-010, R-030
- Objetivo: `schedule` com `17 9 * * 1` e condições dos jobs aceitando
  `schedule` (D-006).
- Arquivos: `tests/test_ci_workflow.py` (novo, escrito antes),
  `.github/workflows/ci.yml`, `CONTRIBUTING.md`, `docs/VALIDATION.md`
- Dependências: nenhuma do bloco A
- Critério de aceite: o teste lê o YAML como texto (sem parser externo) e
  falha antes da mudança; depois passa. CONTRIBUTING explica destinatário da
  notificação e desativação após 60 dias.
- Verificação: local, `python3 -m unittest tests.test_ci_workflow`; remota,
  `workflow_dispatch` na branch com os sete jobs, e a primeira execução
  agendada após o merge (planejada).

## Bloco C: venv com hash obrigatório para as ferramentas (item 4)

Revisto em 2026-11-09 depois de Q-001: o `uv tool install` não aplica hashes,
e o bloco passa a usar uma venv por ferramenta com `uv pip install
--require-hashes` (D-008, ADR 004).

### T-201 Prova offline do comportamento de hash do uv
- Requisitos: R-022
- Objetivo: fixar em teste o comportamento do uv de que o desenho depende.
- Arquivos: `tests/uv_constraints.bats` (reescrito)
- Dependências: nenhuma
- Critério de aceite: usa o `setup` de `core_setup.bash` (HOME, XDG e UV_*
  temporários). Com dois wheels locais (A depende de B), `--offline --no-index
  --find-links` e o Python do sistema: `uv pip install --python VENV/bin/python
  --require-hashes --no-build --link-mode copy -r LOCK` recusa o hash errado de
  B e o lock sem B, e instala com o lock correto; confere que `uv venv` recusa
  diretório não vazio sem `--clear`. O comportamento do `uv tool install
  --constraints` é registrado na saída (`>&3`) com aviso para rever o ADR 004
  se o uv passar a aplicar o hash, sem falhar a suíte.
- Verificação: `bats tests/uv_constraints.bats`, também na matriz com
  `--network none` (via `workflow_dispatch`).

### T-202 Gerar os locks e conferir as plataformas
- Requisitos: R-020
- Objetivo: criar `manifests/python-tools/{ruff,pre-commit,ipython}.txt` (D-007).
- Arquivos: `manifests/python-tools/*.txt`, `CONTRIBUTING.md`, `docs/VALIDATION.md`
- Dependências: T-201
- Critério de aceite: cada arquivo vem de `uv --no-config pip compile
  --universal --python-version 3.13 --generate-hashes --index-url
  https://pypi.org/simple --no-python-downloads` sobre `NOME==VERSÃO`, com
  `UV_CACHE_DIR` temporário; o cabeçalho guarda o comando (com
  `--python-version`), e o CONTRIBUTING também. Q-002: para cada
  `{x86_64,aarch64}-unknown-linux-{gnu,musl}`, `uv pip install --dry-run
  --no-build --require-hashes --python-platform P --python-version 3.13
  --target TMP -r LOCK` passa; faltando wheel em alguma, parar e levar ao
  usuário. VALIDATION registra o resultado sem declarar suporte além disso.
- Verificação: precisa de rede (PyPI); conferir `==`, `--hash=sha256:`, versão
  raiz igual à do manifesto e as quatro plataformas.

### T-203 Validação dos locks no plano de instalação
- Requisitos: R-020
- Objetivo: `python_spec()` recusa lock ausente, requisito sem `==`, sem hash
  sha256, versão raiz divergente ou `--python-version` do cabeçalho diferente
  do minor de `tool_python`, só quando `python-tools` está nos componentes.
- Arquivos: `tests/test_boundaries.py` (antes), `lib/artifacts.py`
- Dependências: T-202
- Critério de aceite: o leitor junta continuações `\`, ignora comentários e
  linhas vazias, guarda marcadores sem avaliá-los e normaliza nomes (PEP 503);
  cada recusa sai com 2 no plano; perfil sem `python-tools` não exige lock.
- Verificação: testes unitários com locks artificiais com marcadores e nomes
  com `_` e `-`; testes de plano com `--profile science`.

### T-204 Conferência da venv contra o lock e doctor
- Requisitos: R-023, R-025
- Objetivo: uma função única classifica cada ferramenta e é usada pelo plano
  de instalação, pelo `setup inspect` e pelo `doctor`.
- Arquivos: `tests/test_boundaries.py` (antes), `lib/artifacts.py`, `lib/state.py`
- Dependências: T-203
- Critério de aceite: estados e ação:

  | Venv `devshell/tools/NOME` | `$UV_TOOL_BIN_DIR/NOME` | Estado | Instalação |
  |---|---|---|---|
  | ausente | ausente | ausente | cria venv e symlink |
  | conforme | ausente | sem link | cria só o symlink |
  | conforme | symlink exato para a venv | conforme | nada |
  | ausente | symlink para a venv | link órfão | bloqueia (revisar e remover o link) |
  | divergente ou parcial | qualquer | divergente | bloqueia (revisar e mover a venv) |
  | qualquer | outro executável ou symlink (ex.: `uv tool`) | conflito | bloqueia com `uv tool uninstall NOME` |

  "Conforme": `pyvenv.cfg` regular com a versão de `tool_python`;
  `bin/python` resolvido com `resolve()`, depois `safe_path` e `patchlevel.h`
  como hoje; cada `dist-info` instalada no lock com a mesma versão (nomes PEP
  503), e cada linha do lock sem marcador instalada; RECORD do executável e
  dos módulos essenciais conferido. O symlink é lido com `lstat`/`readlink`,
  com `safe_path` só no diretório pai. A conferência não chama o uv nem executa
  a ferramenta. `doctor` traz o estado de cada ferramenta e, no conflito, a dica
  de migração; `VERSION_FLOORS` usa 0.13.5 para o uv com `python-tools`.
- Verificação: testes com venv artificial em HOME temporária para cada linha da
  tabela e cada caso de R-023.

### T-205 Instalação em venv sob o lock
- Requisitos: R-021, R-022, R-025
- Objetivo: trocar `uv tool install` pelo fluxo de D-008 e D-012 num helper
  Python chamado por `lib/uv.sh`.
- Arquivos: `tests/setup.bats` e `tests/test_boundaries.py` (antes),
  `lib/artifacts.py`, `lib/uv.sh`, `lib/setup.py`, `lib/setup.sh`
- Dependências: T-204
- Critério de aceite:
  - o plano mostra comandos, venv, symlink e o estado de cada ferramenta, e o
    hash muda com o lock ou com o estado;
  - sob `fs.locked()`, o estado é reclassificado e precisa bater com o plano;
  - comandos: `uv --no-config --no-progress venv --managed-python
    --no-python-downloads --python TOOL_PYTHON VENV` e `uv --no-config pip
    install --python VENV/bin/python --require-hashes --no-build --link-mode
    copy -r LOCK`, com `--offline` no modo offline, sem `VIRTUAL_ENV`,
    `CONDA_PREFIX` e `UV_*` do usuário além dos diretórios;
  - o stub de uv registra essas flags, e o log não tem nenhuma chamada `tool`;
  - uma venv ativa de outro projeto, uma ferramenta estranha em `UV_TOOL_DIR` e
    em `UV_TOOL_BIN_DIR` saem intactas;
  - falha simulada do `uv pip install` remove só a venv criada (`os.mkdir`
    exclusivo), não cria symlink, sai com 2 e lista as ferramentas já feitas;
  - repetir com tudo conforme não altera nada;
  - `target_paths` do setup inclui só `devshell/tools` e `devshell/tools/NOME`,
    e um `setup` repetido depois da instalação não bloqueia;
  - os bloqueios de T-204 entram em `blockers` do `setup inspect`, visíveis no
    `--dry-run` e antes do comando administrativo.
- Verificação: testes novos; `bats tests/setup.bats`. O fluxo com uv real e
  rede fica para T-206, porque o CPython gerenciado não existe offline.

### T-206 Smoke online, ci-setup e documentação
- Requisitos: R-024, R-030
- Objetivo: exercitar o fluxo real com rede e documentar a mudança.
- Arquivos: `scripts/online-smoke.sh`, `scripts/ci-setup.sh`,
  `docs/SECURITY.md`, `docs/ADR/003-uv.md`, `docs/ADR/004-lock-ferramentas-uv.md`,
  `docs/ADR/README.md`, `docs/ARCHITECTURE.md`, `docs/INSTALLATION.md`,
  `docs/SCIENCE.md`, `CHANGELOG.md`, `docs/VALIDATION.md`
- Dependências: T-205
- Critério de aceite:
  - o smoke instala as três ferramentas, executa cada uma pelo symlink e
    confere que `doctor --profile science` não aponta ferramenta;
  - `ci-setup.sh` instala o Ruff com o lock e `--require-hashes` numa venv
    própria do CI (`$HOME/.cache/ci-ruff`), com o PATH ajustado só ali, fora de
    `UV_TOOL_BIN_DIR` e de `devshell/tools`, para não bloquear o smoke;
  - SECURITY: sem a lacuna das transitivas; com os limites (marcadores não
    avaliados, confiança no PyPI na revisão, piso do uv), a migração (`uv tool
    uninstall NOME` e `install --component python` aprovado) e a revisão manual
    de venv parcial após interrupção;
  - CHANGELOG avisa que o doctor aponta as ferramentas antigas até a migração;
  - INSTALLATION atualiza o piso do uv e os diretórios; ADR 003 aponta o 004;
    ADR 004 adotado.
- Verificação: remota, `workflow_dispatch` na branch com `online-smoke` e
  `containers` verdes; local, `bash scripts/check.sh`.

## Bloco D: setup simplificado

O caminho comum passa a ser `git pull` e `./bin/devshell setup`; os comandos
individuais não mudam. Testes antes do código em cada tarefa.

### T-301 Testes dos perfis lembrados
- Requisitos: R-040
- Objetivo: fixar a precedência, a persistência e as exceções antes do código.
- Arquivos: `tests/profiles.bats` (novo), `tests/test_boundaries.py`
- Dependências: nenhuma
- Critério de aceite: casos para lembrado, informado e `minimal` em `plan`,
  `doctor`, `status`, `diff`, `install` e `setup --dry-run`; `profile_source`
  na saída e no JSON, fora do hash; `apply` sem mudança gravando o registro;
  HOME já aplicada sem registro saindo com 2 e pedindo `--profile`; `project` e
  `install --component devshell` funcionando com registro gravado; registro
  inválido saindo com 2 sem `--profile` e só avisando com `--profile`;
  `rollback` funcionando com registro corrompido; restauração no `rollback`, no
  caminho de falha do `apply`, com `previous_profiles` nulo e com manifesto
  antigo sem a chave (aviso); ordem e duplicatas normalizadas; leitura sem
  gravar (árvore de estado idêntica). Todos falham pelo motivo esperado.
- Verificação: `bats tests/profiles.bats` e os unittest novos falham só nos
  casos novos.

### T-302 Gravação e leitura dos perfis
- Requisitos: R-040
- Objetivo: D-014 e D-015.
- Arquivos: `bin/devshell`, `lib/profiles.sh`, `lib/state.py`, `lib/setup.py`
  (`target_paths` com `STATE/profiles`)
- Dependências: T-301
- Critério de aceite: os casos de T-301 passam; os testes existentes que
  dependem do `minimal` implícito continuam verdes ou são ajustados com
  `--profile` explícito, sem enfraquecer o que conferem.
- Verificação: `bash scripts/check.sh` inteiro.

### T-303 `pending` nos planos de instalação
- Requisitos: R-042
- Objetivo: D-017.
- Arquivos: `tests/test_boundaries.py` e `tests/install.bats` (antes),
  `lib/artifacts.py`
- Dependências: T-302
- Critério de aceite: testes falham antes do código; por componente, presente
  e conforme dá `false`, ausente ou divergente dá `true`; um arquivo de plugin
  fora do `health` divergente é o limite documentado; `pending` fica fora do
  hash e `install --approve` continua igual.
- Verificação: testes por componente.

### T-304 Modos das venvs no reparo do setup
- Requisitos: R-043
- Objetivo: D-018.
- Arquivos: `tests/setup.bats` e `tests/test_setup.py` (antes),
  `lib/setup.py`, `lib/state.py`, `lib/python_tools.py`
- Dependências: T-302
- Critério de aceite: testes falham antes do código; venv do fixture com
  `bin/python` symlink e arquivos 664 aparece como reparável e o setup
  prossegue; depois do `s`, nenhum arquivo da venv tem escrita de grupo e o
  doctor aceita a ferramenta; troca de arquivo depois da revisão é recusada pela
  identidade; nada fora de `devshell/tools` muda; texto agrupado por venv;
  teste com cerca de 2000 arquivos fixando saída e tempo; mensagem própria no
  doctor; a instalação usa a função por descritor de `state.py`.
- Verificação: testes novos; `bats tests/setup.bats`.

### T-305 Resumo do setup e componentes em dia
- Requisitos: R-041, R-042
- Objetivo: D-016 e o uso de `pending` no `setup`.
- Arquivos: `tests/setup.bats` (antes), `scripts/online-smoke.sh`,
  `lib/setup.py`, `lib/setup.sh`
- Dependências: T-303, T-304
- Critério de aceite: testes falham antes do código; o resumo é a primeira
  saída e diz que cada etapa pede a sua confirmação; etapas dependentes do
  reparo aparecem como "reavaliado depois do reparo", com teste; tudo em dia dá
  "nada a fazer", saída 0, nenhuma pergunta e nenhuma pendência que o setup
  resolva; componente `pending: false` não gera pergunta nem chamada; `--dry-run
  --json` traz `summary`; os testes do setup e o `online-smoke.sh` que
  respondem por posição passam a conferir o texto de cada pergunta respondida.
- Verificação: testes novos, inclusive o cenário de atualização do projeto com
  dotfiles e ferramentas desatualizados; `bash scripts/check.sh`.

### T-306 Próximo passo no doctor
- Requisitos: R-044
- Objetivo: D-019.
- Arquivos: `tests/test_boundaries.py` e `tests/setup.bats` (antes),
  `lib/state.py`
- Dependências: T-302, T-304
- Critério de aceite: testes falham antes do código; um teste por tipo de
  pendência (resolvida pelo setup, manual, nenhuma, doctor com saída 2); texto
  termina com "Próximo passo: ..."; JSON com `next_step` ou `null`;
  `--profile` no comando só quando a origem não é `lembrados`; invariante
  "setup com nada a fazer, doctor sem sugerir setup".
- Verificação: testes novos.

### T-307 Documentação do caminho comum
- Requisitos: R-045
- Objetivo: README, INSTALLATION, USAGE, CHANGELOG e VALIDATION.
- Arquivos: `README.md`, `docs/INSTALLATION.md`, `docs/USAGE.md`,
  `CHANGELOG.md`, `docs/VALIDATION.md`
- Dependências: T-305, T-306
- Critério de aceite: "Atualizar" com dois comandos e saída executada em HOME
  temporária; aviso de migração para quem já tem a HOME aplicada (`setup
  --profile ...` uma vez); seção avançada com plan/apply/install/rollback;
  CHANGELOG com a mudança do perfil padrão e o campo `next_step`.
- Verificação: `bash scripts/check.sh`; leitura do diff; remota,
  `workflow_dispatch` na branch (smoke e containers), com autorização própria.

## Bloco E: retirada de arquivos órfãos

Item 1 do [ROADMAP](ROADMAP.md), com o escopo da D-022: o registro
`current.json` é a fonte, sem manifesto de migrações. Testes antes do código em
cada tarefa, vistos falhando pelo motivo esperado. Toda verificação local roda
com HOME/XDG/cache temporários.

Onde cada verificação roda: a sessão remota tem só `python3` e `uv`, sem Bats,
ShellCheck, shfmt, Zsh ou Chezmoi. Ali, "visto falhando" vale para os unittest,
com `chezmoi_render` substituído por patch. Os Bats novos (`retire.bats` e os
casos de `setup.bats`) e o exemplo da USAGE, que precisa do Chezmoi, são
vistos falhando e depois passando no `workflow_dispatch` da branch, ou
localmente onde houver as ferramentas.

### T-401 Testes da classificação dos órfãos
- Requisitos: R-050, R-055
- Objetivo: fixar as cinco ações, a validação do registro e a ausência de
  escrita antes do código.
- Arquivos: `tests/test_boundaries.py` (classe nova `OrphanRetirement`),
  `tests/retire.bats` (novo)
- Dependências: nenhuma
- Critério de aceite:
  - registro com um órfão por ação: `remove` (no universo, conteúdo igual ao
    registrado), `forget-edited`, `forget-missing`, `forget-outside` (caminho
    fora de `desired_files(all_components=True)`, inclusive fora da HOME) e
    `forget-unsafe` (symlink no próprio caminho, symlink em ancestral, ancestral
    com escrita de grupo, hardlink, diretório no lugar do arquivo, arquivo com
    modo 000 e outro dono simulado com patch de `os.getuid`);
  - precedência: um caso que se encaixa em duas ações fica com a primeira da
    ordem de R-050;
  - um órfão fora do universo que é FIFO ou caminho inexistente muito longo
    vira `forget-outside` sem nenhum `stat` ou leitura (patch que falha se
    chamado);
  - `CONFIG/devshell/components`, que é sempre desejado, nunca é órfão;
  - a lista `retire` muda o hash de aprovação: o mesmo plano com e sem órfão
    tem hashes diferentes, e mudar a ação, o motivo ou o snapshot de um órfão
    também muda o hash;
  - `plan`, `status`, `diff` e `doctor` deixam a árvore de estado e a HOME
    idênticas (comparação por caminho, modo e SHA-256);
  - o `diff` em texto mostra o `remove` como diff unificado para vazio, e um
    órfão não UTF-8 como "(conteúdo binário)";
  - R-055: `current.json` lista, número, objeto com chave relativa, valor que
    não é texto e hash curto saem com 2, sem traceback e sem gravar nada.
- Verificação: os testes novos falham só nos casos novos.

### T-402 Classificação no plano
- Requisitos: R-050, R-055
- Objetivo: D-023 e D-024.
- Arquivos: `lib/state.py` (`registry`, `build_plan`, `report` e o `diff` em
  `main()`)
- Dependências: T-401
- Critério de aceite: os casos de T-401 passam. A classificação usa
  `snapshot` e `path_issues`, sem seguir symlinks, e não lança exceção por
  órfão inseguro: o caso vira `forget-unsafe` com o motivo. O texto do `plan`
  lista `remove:` e `forget:` com o motivo. Os testes existentes continuam
  verdes sem ajuste de asserção.
- Verificação: `python3 -m unittest`; os Bats ficam com o CI quando a sessão
  não tiver Bats.

### T-403 Testes do apply e do rollback com retirada
- Requisitos: R-051, R-052
- Objetivo: fixar a transação antes do código.
- Arquivos: `tests/test_boundaries.py` (`OrphanRetirement`),
  `tests/retire.bats`
- Dependências: T-402
- Critério de aceite:
  - `apply` de `personal` para `minimal`: remove os quatro arquivos de
    `nu`/`starship`/`direnv`, guarda backup com modo e dono, deixa
    `current.json` sem órfãos e preserva os diretórios;
  - um plano só com órfãos, sem nada a escrever, abre transação e não chama o
    `chezmoi_render`;
  - só `forget-*`: transação com `files: []`, nenhum arquivo tocado, entradas
    fora do registro; o rollback dessa transação devolve as entradas;
  - arquivo alterado entre o plano e o apply: hash vencido e nada muda;
  - falha injetada depois da primeira remoção: o arquivo volta do backup, o
    registro anterior volta e a transação não fica `committed`;
  - backup com SHA-256 diferente do `before` (patch no `copy2`): nada é
    removido e o registro não muda;
  - diretório pai trocado por symlink entre a conferência e a remoção (patch):
    a remoção é recusada pela identidade e o arquivo do outro lado fica;
  - `rollback` aprovado recoloca conteúdo, modo e dono e restaura as entradas
    `forget-*` no registro;
  - caminho recriado e editado depois do apply: o rollback recusa;
  - dotfile retirado do checkout depois do apply (patch em `desired_files`):
    o rollback recusa com a mensagem que aponta o backup;
  - `rollback --prune` e `rollback --list` aceitam a transação nova, e a poda
    avisa quando remove a única cópia de um arquivo retirado;
  - um manifesto antigo, sem `forgotten`, continua aceito.
- Verificação: os testes novos falham só nos casos novos.

### T-404 Apply e rollback
- Requisitos: R-051, R-052
- Objetivo: D-025 e D-026.
- Arquivos: `lib/state.py` (`apply_configuration`, o caminho de falha e
  `rollback_plan`, se precisar)
- Dependências: T-403
- Critério de aceite: os casos de T-403 passam. O caminho sem mudanças só é
  usado quando não há escrita nem órfão (D-014 ajustada). A remoção acontece
  sob o lock: backup conferido por SHA-256, diretório pai aberto sem seguir
  symlinks e com identidade conferida, `unlink` com `dir_fd`, como em
  `drop_group_write_tree`. O `remove` entra na lista do caminho de falha logo
  depois do `unlink`. O registro final é `registro anterior − órfãos |
  escritos`. Uma transação sem escrita não executa o Chezmoi.
- Verificação: `python3 -m unittest`; leitura do diff contra a D-026.

### T-405 Doctor e setup
- Requisitos: R-053
- Objetivo: incluir os órfãos no diagnóstico, no `next_step`, no resumo e na
  etapa de aplicação do `setup`.
- Arquivos: `tests/test_boundaries.py`, `tests/test_setup.py`,
  `tests/setup.bats` (antes), `lib/state.py` (`doctor`, `SETUP_RESOLVES`),
  `lib/setup.py` (`summary`, `target_paths`), `lib/setup.sh` (contagem e
  pergunta da etapa de aplicação)
- Dependências: T-404
- Critério de aceite:
  - testes falham antes do código;
  - o `doctor` acusa `arquivo gerenciado fora dos perfis: CAMINHO (AÇÃO)`,
    sai com 3 e o `next_step` é `setup`;
  - o resumo conta os órfãos e não marca a etapa `em dia` com órfãos, nem só
    com `forget-*`;
  - com `retire` não vazio, a pergunta "Registrar os perfis…" nunca aparece
    nem aprova o hash;
  - com algum `remove`, o setup lista os arquivos e exige a palavra
    `retirar`; resposta diferente ou EOF cancela sem gravar nada (teste com
    `tests/answer.py` conferindo o texto da pergunta);
  - D-027: um órfão do universo com ancestral de escrita de grupo aparece na
    revisão de permissões; depois do reparo, vira `remove`;
  - um plano só com órfãos pergunta na etapa de aplicação, com o texto
    começando por "Aplicar os dotfiles" (os testes respondem por esse
    prefixo) e informando quantos arquivos serão removidos e quantos só saem
    do registro;
  - depois do `setup`, o `doctor` não acusa órfãos;
  - o invariante "setup com nada a fazer, doctor sem sugerir setup" continua
    valendo.
- Verificação: testes novos; `bash scripts/check.sh` onde houver as
  ferramentas.

### T-406 Documentação da retirada
- Requisitos: R-054
- Objetivo: README, USAGE, SECURITY, ARCHITECTURE, CHANGELOG e ROADMAP.
- Arquivos: `README.md`, `docs/USAGE.md`, `docs/SECURITY.md`,
  `docs/ARCHITECTURE.md`, `CHANGELOG.md`, `docs/ROADMAP.md`
- Dependências: T-405
- Critério de aceite:
  - USAGE com exemplo executado em HOME temporária de troca de
    `personal` para `minimal`, mostrando `remove:` e `forget:`;
  - linha "Arquivo retirado" na tabela de recuperação do SECURITY, com os
    limites do rollback (dotfile que saiu do repositório) e da poda (única
    cópia), e a lembrança de que, com `--replace-existing`, o original do
    usuário está só na transação daquele apply;
  - USAGE avisa sobre `XDG_CONFIG_HOME` diferente numa sessão;
  - ARCHITECTURE descreve o registro como fonte da retirada;
  - CHANGELOG marca a mudança de comportamento do `apply`;
  - no ROADMAP, o item 1 vira "concluído" e o escopo reduzido fica
    registrado.
- Verificação: links locais conferidos; `bin/devshell --help` sem mudança de
  flags.

### T-490 Encerramento do Bloco E
- Requisitos: R-050, R-051, R-052, R-053, R-054, R-055
- Objetivo: fechar o bloco com evidência, como o T-900.
- Arquivos: `docs/spec.md` (estados e evidências), `docs/VALIDATION.md`
- Dependências: T-406
- Critério de aceite: `workflow_dispatch` na branch com os sete jobs verdes e
  zero skips; revisão independente sem P0/P1 abertos; cada requisito com
  evidência; seção datada na VALIDATION.
- Verificação: comandos acima, registrados na VALIDATION. O merge é decidido
  pelo usuário.

## Encerramento

### T-900 Verificação final e revisão independente
- Requisitos: R-001, R-002, R-003, R-004, R-005, R-006, R-010, R-020, R-021, R-022, R-023, R-024, R-025, R-030, R-040, R-041, R-042, R-043, R-044, R-045
- Objetivo: fechar cada bloco com evidência.
- Arquivos: `docs/spec.md` (estados e evidências), `docs/VALIDATION.md`
- Dependências: T-006, T-101, T-206, T-307
- Critério de aceite: `bash scripts/check.sh` verde sem skips;
  `spec_check.py --stage a3` limpo (ferramenta da pre-code-pipeline, fora do
  repositório, rodada com `--root .`); revisão independente sem P0/P1 abertos;
  cada requisito com evidência ou pendência justificada.
- Verificação: comandos acima, registrados em VALIDATION.

## Efeitos externos previstos

| Efeito | Tarefa | Destino |
|---|---|---|
| Consulta ao PyPI com cache temporário (geração dos locks e conferência das quatro plataformas) | T-202 | pypi.org, via `uv pip compile` e `uv pip install --dry-run` |
| Commit na branch de trabalho | cada bloco | repositório local |
| Push da branch e PR | cada bloco | `origin` (talesgomes27/data-lab-dotfiles) |
| `workflow_dispatch` na branch, com downloads reais de apt, GitHub e PyPI nos runners | T-101, T-201, T-206, T-900, T-490 | GitHub Actions do repositório |
| Migração das suas instalações atuais (`uv tool uninstall` e nova instalação) | depois do merge do Bloco C | sua HOME; feita por você, não pela CLI |
| Execução semanal após o merge, sem prazo, com os mesmos downloads e notificação de falha para quem editou o cron | T-101 | GitHub Actions; desativada após 60 dias sem atividade |

Aceitar este plano não autoriza nenhum desses efeitos: cada um pede autorização
própria na execution-pipeline, no momento em que for executado. Nenhum instala
nada na HOME real; o merge na `main` fica com você.
