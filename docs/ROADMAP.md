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
- **Em observação:** R-010 depende da primeira execução agendada na `main`
  (segunda, 2026-11-16, 09:17 UTC).

## Próximos itens

Em ordem de prioridade. O tamanho é uma estimativa.

| # | Item | Origem | Tamanho | Depende de |
|---|---|---|---|---|
| 1 | Migrações declarativas | N-009, D-013 | médio a grande | — |
| 2 | Desinstalação de componentes | N-005, N-009 | médio | 1 |
| 3 | Revisão assistida de manifestos | N-005 | médio | — |
| 4 | Poda dos demais diretórios de estado | N-001 | pequeno a médio | — |
| 5 | Quarto como componente | N-005 | médio | 3 (recomendado) |
| 6 | Configuração Git gerenciada | N-005 | médio | — |

### 1. Migrações declarativas

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

### 2. Desinstalação de componentes

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

**Depende de 1:** a desinstalação precisa saber em que formato cada
instalação foi registrada.

### 3. Revisão assistida de manifestos

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

- **Pin do `actions/checkout`:** a v4.2.2 ainda declara Node.js 20, e o runner
  força Node.js 24. Atualizar exige revisão do SHA na fonte oficial.
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
