# Roadmap

[Início](../README.md) · [Arquitetura](ARCHITECTURE.md) · [Validação](VALIDATION.md)

Lista o que vem depois dos Blocos A a D do [plano](plan.md). Não é um
compromisso de datas. Cada item só começa com o próprio desenho: spec, plano
revisado e aprovação, como nos blocos anteriores. Os identificadores `N-*` e
`D-*` são os da [spec](spec.md).

Atualizado em 2026-11-12.

## Estado atual

- **Blocos A a D concluídos** (T-900 fechado, #17 a #19): histórico e poda do
  rollback, CI semanal, ferramentas Python em venvs com hash obrigatório e
  setup com perfis lembrados.
- **Nenhum achado aberto da revisão independente do T-900.**
- **R-046 (#21):** na HOME do mantenedor, um registro de perfis `minimal`
  levou o `setup` a tirar 24 componentes com uma confirmação de diff comum
  (transação `c7209d5c`, que pode ser desfeita). Agora os comandos sem
  `--profile` param quando os perfis lembrados tirariam componentes
  aplicados. A causa do registro errado foi encontrada (item 0).
- **Em observação:** R-010 depende da primeira execução agendada na `main`
  (segunda, 2026-11-16, 09:17 UTC).

## Próximos itens

Em ordem de prioridade. O tamanho é uma estimativa.

| # | Item | Origem | Tamanho | Depende de |
|---|---|---|---|---|
| 0 | Estado preso à configuração (implementado) | R-046, R-047, R-048 | pequeno | — |
| 1 | Retirada de arquivos órfãos (implementado) | N-009, D-013, D-022 | médio | 0 |
| 2 | Desinstalação de componentes (implementado) | N-005, N-009 | médio | 1 |
| 2b | Saída completa (implementado) | N-016 | médio | 2 |
| 3 | Revisão assistida de manifestos (implementado) | N-005 | médio | — |
| 4 | Poda dos demais diretórios de estado | N-001 | pequeno a médio | — |
| 5 | Quarto como componente | N-005 | médio | 3 (recomendado) |
| 6 | Configuração Git gerenciada | N-005 | médio | — |

### 0. Estado preso à configuração (origem do registro de perfis errado)

**Problema:** no incidente do R-046, o registro dizia `minimal` sem nenhuma
transação que explicasse isso. A retirada de órfãos (item 1) confia nos
perfis do comando; um caminho que grava perfis errados passaria a remover
arquivos, não só componentes.

**O que já foi descartado (2026-11-12):** os testes. A suíte unittest rodada
com HOME e XDG apontando para um diretório-sentinela não gravou nada nele, e
todos os Bats carregam `tests/core_setup.bash`, que exporta HOME e XDG
temporários.

**Caminhos que gravam o registro:** o `apply` (com e sem arquivos a alterar) e
o `rollback`/caminho de falha (que restauram `previous_profiles`). O `apply`
sem arquivos a alterar grava o registro **sem transação**, então não deixa
rastro. Hipótese principal: um comando rodado com `XDG_CONFIG_HOME` ou HOME
diferentes, mas o mesmo `XDG_STATE_HOME`. Nesse contexto, a configuração
correspondia a `minimal`, e o `apply` sem mudanças gravou `minimal` no estado
compartilhado.

**Causa encontrada (2026-11-12):** na HOME afetada, o registro passou a
`minimal` entre a transação `49dd88de` (anterior ao Bloco D) e a `c7209d5c`
(`previous_profiles: minimal`), sem nenhuma transação entre elas. O caso foi
reproduzido numa HOME simulada: com a HOME e o estado reais, mas com
`XDG_CONFIG_HOME` apontando para um diretório já em `minimal`, `plan` e
`apply` sem `--profile` gravam `minimal` no registro real pelo caminho sem
mudanças. Esse registro tira os mesmos 24 componentes. O comando exato não foi
identificado sem o histórico da shell, mas o mecanismo está demonstrado.

**Correção:** Bloco E0 (R-047 e R-048), implementado. O estado passa a ser
recusado quando pertence a outra configuração, e toda mudança do registro de
perfis abre uma transação.

### 1. Retirada de arquivos órfãos (implementado)

Escopo reduzido das migrações declarativas (R-050 a R-055, D-022 a D-027): o
registro `current.json` é a fonte, sem manifesto de migrações (D-022). A remoção de arquivos pede uma confirmação digitada à parte
no `setup`, por causa do incidente do R-046.

Texto original do item, mantido como referência para um manifesto futuro
(N-010):

#### Migrações declarativas

**Problema:** mudar o formato do estado exige passos manuais do usuário. A
D-013, por exemplo, obriga a rodar `uv tool uninstall NOME` antes de instalar
as ferramentas em venvs.

**Proposta:** migrações descritas como dados em `manifests/`, não como código
solto. O `setup` mostra cada migração pendente num plano próprio, com hash de
aprovação, backup e escopo restrito, e confirmação separada das outras etapas.

**Limites:**
- só altera o que a CLI criou;
- nunca remove pacotes do sistema, interpretadores ou ambientes externos;
- não há `--yes` (N-008).

**Pronto quando:** a migração da D-013 puder ser refeita por esse mecanismo,
com teste de interrupção e de rollback.

### 2. Desinstalação de componentes (implementado)

Feito no Bloco F (R-060 a R-065, D-030 a D-034): componentes com prova de
dono e recibo para plugins, fonte e pyinit; desfazer é reinstalar. A saída
completa virou o item 2b.

Texto original do item:

**Problema:** o rollback desfaz só os dotfiles. Não existe um caminho para
retirar o que a CLI instalou.

**Proposta:** `uninstall --component X` com plano e hash. Remove só o que a CLI
criou e registrou: as venvs em `devshell/tools`, os symlinks em
`UV_TOOL_BIN_DIR`, o launcher, os plugins e a fonte. Um modo de saída completa
combina isso com o rollback dos dotfiles.

**Limites:**
- itens que não estão no registro da CLI ficam como passo manual (N-003);
- pacotes do sistema, CPython do uv e ambientes de projeto nunca são
  removidos.

**Depende de 1:** a desinstalação reaproveita a remoção com backup e
rollback do item 1.

### 2b. Saída completa (implementado)

Feito no Bloco G (R-070 a R-074): `rollback --all` e o comando `leave` por
etapas, com `--purge-state` opcional.


**Problema:** sair do Data Lab hoje exige rodar `uninstall` por componente e
o rollback até antes do primeiro apply, à mão.

**Proposta:** um comando que mostra, num só plano, os uninstalls de cada
componente e o rollback da cadeia de transações até o estado anterior ao
primeiro apply, e que pede uma confirmação por etapa, como o `setup`. Ele não
remove o estado nem os backups: isso continua sendo da poda.

**Depende de 2.**

### 3. Revisão assistida de manifestos (implementado)

Feito no Bloco H (R-080 a R-084): `scripts/review-manifests.py`, ferramenta de
mantenedor fora da CLI.


**Problema:** atualizar versões e checksums de `manifests/artifacts.json`,
`manifests/python.json` e `manifests/python-tools/` é trabalho manual e
repetitivo.

**Proposta:** um comando só de leitura que consulta as fontes oficiais
(releases do GitHub e PyPI, com cache temporário) e gera uma proposta de diff
para revisar. Não grava manifestos nem estado. A mudança continua sendo uma
revisão de manifesto, com nova validação.

**Limites:**
- a proposta não substitui a auditoria do que foi publicado;
- `update` continua mexendo só em configuração (N-007).

### 4. Poda dos demais diretórios de estado

**Problema:** `launcher-backups` e `permission-repairs`, em
`$XDG_STATE_HOME/devshell`, crescem sem limite.

**Proposta:** aplicar a mesma mecânica do `rollback --prune --keep N`: plano,
hash, lock, renomeação antes de remover e recusa de entradas inválidas. A poda
continua sem modo automático nem por idade (N-002).

**Antes de desenhar:** conferir quais diretórios de backup ainda existem. A
N-001 cita também `manual-backups` e `user-config-backups`, que não aparecem
no código atual.

### 5. Quarto como componente

**Proposta:** Quarto com versão e SHA-256 fixados em
`manifests/artifacts.json`, por arquitetura e libc, instalado em HOME de
usuário e conferido pelo `doctor`. Hoje o Quarto só é preparado no runner do CI
para os cenários opcionais.

**Limites:** nada é declarado como suportado sem execução real em cada
combinação (AGENTS.md).

### 6. Configuração Git gerenciada

**Proposta:** um `~/.config/git/config` estático renderizado pelo Chezmoi, que
inclui um arquivo local do usuário para nome, e-mail e chaves, como a
`.zshenv.local`. Identidade e credenciais nunca vão para o repositório nem para
fixtures.

## Melhorias de manutenção

São independentes e menores; entram quando houver espaço.

- **Ambiente das sessões remotas:** um setup script com ShellCheck, shfmt, Bats
  e Zsh deixaria `bash scripts/check.sh` rodar completo fora do CI.
- **Teste Bats da D-020:** um cenário ponta a ponta em `tests/setup.bats` para
  a mensagem do CPython gerenciado inseguro, hoje coberta só por unittest.

## Fora de propósito

Ficam fora mesmo no futuro, porque contrariam os contratos do
[AGENTS.md](../AGENTS.md) ou as decisões da spec:

- `--yes` ou aprovação automática no setup (N-008);
- `git pull`, atualização do checkout ou busca de versões novas pela CLI (N-007);
- poda automática ou por idade (N-002);
- reinstalação forçada ou remoção de ferramentas que a CLI não criou (N-003);
- rollback que remova pacotes do sistema, interpretadores ou ambientes externos.
