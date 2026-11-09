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
revisao_do_plano:
  por: subagente plan-reviewer
  em: "2026-11-09"
  resultado: "pronto com ressalvas; P1 e P2 incorporados (spec v2, D-003/D-004 ajustadas, D-009/D-010 novas)"
dispensas:
  - gate: PC-1
    motivo: sem fontes de dados a perfilar
  - gate: PC-4
    motivo: nenhuma estrutura antecede o código; os locks nascem em T-202
proximo_passo: Bloco B (T-101) pela execution-pipeline, quando o usuário pedir
pendencias: [Q-001, Q-002, Q-003]
```

# Plano: histórico de transações, CI agendado e lock das ferramentas uv

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

## Bloco C: lock das ferramentas uv (item 4)

### T-201 Prova de que o uv aplica os hashes das constraints
- Requisitos: R-022
- Objetivo: responder Q-001 antes de qualquer outra tarefa do lock.
- Arquivos: `tests/uv_constraints.bats` (novo)
- Dependências: nenhuma
- Critério de aceite: o teste monta com `zipfile` dois wheels mínimos, A
  (com entry point) dependendo de B, e roda `uv tool install A` com
  `--offline --no-index --find-links`, `--python "$(command -v python3)"` sem
  Python gerenciado, e HOME/UV_* temporários. Com o hash de B errado em
  `--constraints`: falha, stderr menciona hash, `UV_TOOL_DIR/A` não existe.
  Com os hashes certos: instala. Registra também, sem exigir resultado, o que
  acontece ao instalar com constraints sobre A já instalada sem elas e com um
  pacote ausente do lock; os resultados entram no ADR 004 e no SECURITY.
- Verificação: `bats tests/uv_constraints.bats`, inclusive na matriz com
  `--network none`. Se o hash errado instalar, parar o bloco C e reabrir PC-3
  com o usuário (D-008).

### T-202 Gerar os arquivos de lock
- Requisitos: R-020
- Objetivo: criar `manifests/python-tools/{ruff,pre-commit,ipython}.txt` (D-007).
- Arquivos: `manifests/python-tools/*.txt`, `CONTRIBUTING.md`
- Dependências: T-201
- Critério de aceite: cada arquivo vem de `uv --no-config pip compile
  --universal --python-version 3.13 --generate-hashes --index-url
  https://pypi.org/simple --no-python-downloads` sobre `NOME==VERSÃO` do
  manifesto, com `UV_CACHE_DIR` temporário; o comando exato fica no
  CONTRIBUTING. Q-002: para cada requisito, há wheel com hash no lock para
  x86_64 e aarch64, glibc e musl (ou wheel `py3-none-any`); faltando algum,
  parar e levar ao usuário.
- Verificação: precisa de rede (PyPI); conferir que todo requisito tem `==` e
  `--hash=sha256:`, que a versão raiz bate com `manifests/python.json` e a
  cobertura de plataformas acima.

### T-203 Validação dos locks no plano de instalação
- Requisitos: R-020
- Objetivo: `python_spec()` recusa lock ausente, requisito sem `==`, sem hash
  sha256 ou versão raiz divergente, só quando `python-tools` está nos
  componentes.
- Arquivos: `tests/test_boundaries.py` (antes), `lib/artifacts.py`
- Dependências: T-202
- Critério de aceite: o leitor junta continuações `\`, ignora comentários e
  linhas vazias, guarda marcadores sem avaliá-los e normaliza nomes (PEP 503);
  cada recusa sai com 2 no plano, sem instalar; perfil sem `python-tools` não
  exige lock.
- Verificação: testes unitários novos com locks artificiais com marcadores e
  nomes com `_` e `-`; testes de plano com `--profile science`.

### T-204 Instalação com `--constraints` e `--no-build`
- Requisitos: R-021
- Objetivo: incluir o arquivo e `--no-build` nos comandos do plano e em
  `install_python`.
- Arquivos: `tests/setup.bats` (asserção do stub de uv, antes),
  `lib/artifacts.py`, `lib/uv.sh`
- Dependências: T-203
- Critério de aceite: a asserção nova do stub falha antes da mudança; o plano
  mostra os argumentos; o stub registra `--constraints` e `--no-build`; alterar
  um lock muda o hash de aprovação; `check()` recusa uv abaixo de 0.13.5 com
  ferramentas no plano (D-010), com teste do piso.
- Verificação: `bats tests/setup.bats` e teste de hash em `test_boundaries`.

### T-205 Doctor compara o ambiente com o lock
- Requisitos: R-023
- Objetivo: ler os `METADATA` das distribuições do ambiente de cada ferramenta
  e comparar nome e versão com o lock.
- Arquivos: `tests/test_boundaries.py` (antes), `lib/artifacts.py`
- Dependências: T-203
- Critério de aceite: compara cada distribuição instalada com o lock, por nome
  normalizado; versão diferente ou distribuição ausente do lock gera o
  diagnóstico de R-023 e saída 3; linha do lock sem distribuição instalada não
  gera alerta; nenhuma execução de código da ferramenta, nenhuma reinstalação.
- Verificação: teste com ambiente de ferramenta artificial em HOME temporária.

### T-206 Smoke online e documentação do bloco C
- Requisitos: R-024, R-030
- Objetivo: o smoke instala com os locks e confere o doctor; SECURITY, ADR 004
  (status adotada), ARCHITECTURE, CHANGELOG e VALIDATION.
- Arquivos: `scripts/online-smoke.sh`, `scripts/ci-setup.sh`, `docs/SECURITY.md`,
  `docs/ADR/004-lock-ferramentas-uv.md`, `docs/ADR/README.md`,
  `docs/ARCHITECTURE.md`, `CHANGELOG.md`, `docs/VALIDATION.md`
- Dependências: T-204, T-205
- Critério de aceite: o smoke roda `doctor --profile science` e confere que a
  saída não contém "fora do lock"; `ci-setup.sh` instala o Ruff com
  `manifests/python-tools/ruff.txt`; a lacuna das transitivas sai do SECURITY,
  com os limites que restam (confiança no PyPI e no uv, pacote fora do lock sem
  hash, piso do uv) e a recuperação `uv tool uninstall NOME` seguida de
  `install --component python` aprovado.
- Verificação: remota, `workflow_dispatch` na branch com `online-smoke` verde;
  local, `bash scripts/check.sh`.

## Encerramento

### T-900 Verificação final e revisão independente
- Requisitos: R-001, R-002, R-003, R-004, R-005, R-006, R-010, R-020, R-021, R-022, R-023, R-024, R-030
- Objetivo: fechar cada bloco com evidência.
- Arquivos: `docs/spec.md` (estados e evidências), `docs/VALIDATION.md`
- Dependências: T-006, T-101, T-206
- Critério de aceite: `bash scripts/check.sh` verde sem skips;
  `spec_check.py --stage a3` limpo (ferramenta da pre-code-pipeline, fora do
  repositório, rodada com `--root .`); revisão independente sem P0/P1 abertos;
  cada requisito com evidência ou pendência justificada.
- Verificação: comandos acima, registrados em VALIDATION.

## Efeitos externos previstos

| Efeito | Tarefa | Destino |
|---|---|---|
| Consulta ao PyPI com cache temporário | T-202 | pypi.org, via `uv pip compile` |
| Commit na branch de trabalho | cada bloco | repositório local |
| Push da branch e PR | cada bloco | `origin` (talesgomes27/data-lab-dotfiles) |
| `workflow_dispatch` na branch, com downloads reais de apt, GitHub e PyPI nos runners | T-101, T-206 | GitHub Actions do repositório |
| Execução semanal após o merge, sem prazo, com os mesmos downloads e notificação de falha para quem editou o cron | T-101 | GitHub Actions; desativada após 60 dias sem atividade |

Aceitar este plano não autoriza nenhum desses efeitos: cada um pede autorização
própria na execution-pipeline, no momento em que for executado. Nenhum instala
nada na HOME real; o merge na `main` fica com você.
