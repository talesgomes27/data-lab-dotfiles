# Contribuir e preparar versões

[Início](README.md) · [Arquitetura](docs/ARCHITECTURE.md) · [Validação](docs/VALIDATION.md)

## Relatar problemas e propor mudanças

Abra uma issue com objetivo, comportamento observado, resultado esperado,
distribuição/arquitetura, seleção de perfis e comando relevante. Use dados
artificiais para reproduzir. Não anexe credenciais, histórico, dotfiles privados
ou logs sem revisão. Falhas de segurança seguem a
[política de relato](docs/SECURITY.md#relatar-uma-vulnerabilidade).

Para uma contribuição, descreva o problema e a alteração proposta, inclua a
validação pertinente e atualize a documentação afetada. Preserve os contratos
de aprovação, os perfis declarativos e os manifestos fixados. Consulte as
[instruções para agentes](AGENTS.md) e os [ADRs](docs/ADR/README.md).

## Preparar o ambiente de desenvolvimento

As verificações exigem Python >=3.11, Bash, ShellCheck, shfmt, Bats, Chezmoi,
Zsh, Nushell, uv e direnv no PATH. Starship é necessário para os cenários de prompt; uma
verificação com skips não comprova esses cenários. Os
[pré-requisitos dos testes opcionais](docs/INSTALLATION.md#pré-requisitos-para-reproduzir-todos-os-testes)
incluem fzf, zoxide, R/renv, Node.js e Quarto. O disparo manual do workflow
prepara essas dependências no runner e exige execução sem skips.

Clone com `--recurse-submodules`; em uma cópia existente, execute
`git submodule update --init --recursive` antes dos testes.

Na raiz do projeto:

```bash
bash scripts/check.sh
```

O script executa ShellCheck, shfmt, sintaxe Python, Bats e unittest. Os testes
usam HOME/XDG/cache temporários. Mudanças de comportamento exigem testes
pertinentes, sem enfraquecer guardas. Não use sua HOME como fixture.

Os testes de integração são operações adicionais, com downloads:

```bash
bash scripts/containers.sh
bash scripts/online-smoke.sh
```

Containers exigem Docker acessível; o smoke usa HOME descartável e pressupõe
seus pré-requisitos nativos. Revise os scripts antes de executar. Não confunda
fixtures de adaptadores com validação da distribuição. Resultados e limites
ficam em [VALIDATION](docs/VALIDATION.md).

## Manter documentação e manifestos

Use links relativos dentro do repositório, títulos descritivos e exemplos com
pré-requisitos, efeitos e resultados esperados. O README é a entrada principal;
instalação, uso, ciência e diagnóstico têm manuais próprios. O glossário curto
fica no README. Evite inventários de máquina ou relatos de sessão como instrução
pública. Retire material obsoleto depois de incorporar a informação útil.

Versões/checksums de artefatos mudam por revisão da fonte oficial e nova
validação; não há consulta automática a latest. Dependências das ferramentas uv
e o lock científico têm escopos distintos. Atualize o changelog para mudanças
perceptíveis ao usuário. Preserve as atribuições da licença MIT e as licenças
dos componentes externos.

## Atualizar o template Python

O submódulo `templates/python-template-linux` fixa o repositório público em um
commit revisado. Não use `git submodule update --remote` no setup. Para atualizar,
revise primeiro o PR do template, selecione o commit no submódulo e atualize
juntos o gitlink, a versão, a URL e o SHA-256 de `pyinit` em
`manifests/artifacts.json`. Confira o hash do download e dos bytes do submódulo;
`tests/pyinit.bats` exige que correspondam. Execute a suíte e revise o diff antes
de publicar o PR dos dotfiles. Preserve a licença do template no submódulo.
Atualizar apenas os dotfiles com `devshell update` não reinstala `pyinit`.

## Preparar a primeira publicação

A cópia local pode ainda não ser um repositório Git. Se `git status` indicar
isso, inicialize somente após escolher e revisar o diretório a publicar.
Se já houver histórico ou remoto, preserve-os e confira a configuração.

Antes do primeiro envio:

1. Execute as verificações e revise seus resultados, inclusive skips.
2. Confira os links, os exemplos, a licença e a matriz de evidências.
3. Revise os arquivos que serão adicionados. Não publique cache, backups,
   históricos, kernelspecs pessoais, `.env` ou dados privados.
4. Defina o destino GitHub e o canal de relatos de segurança. Não apresente
   templates de URL ou selos de CI como evidência de publicação.
5. Prepare uma versão experimental, declarando as plataformas efetivamente
   verificadas e as limitações em aberto.

Em um repositório já inicializado, a revisão antes de confirmar inclui:

```bash
git status --short
git diff
git diff --cached --stat
git diff --cached --check
git remote -v
```

Os comandos acima não fazem commit ou push. Selecione conscientemente os
arquivos a adicionar, confirme a alteração e envie apenas para o destino
revisado. Não use `git clean -fdx` para preparar uma publicação.

## Proteger a main

A política versionada está em [main-ruleset.json](.github/main-ruleset.json).
Ela só é aplicada quando enviada às configurações do GitHub; versionar o JSON
não ativa a proteção. Um ruleset pode selecionar `refs/heads/main` antes de a
branch existir. O repositório público do projeto é
[talesgomes27/data-lab-dotfiles](https://github.com/talesgomes27/data-lab-dotfiles).

A política exige pull request, check `checks` aprovado, branch atualizada com a
base e conversas resolvidas. Bloqueia force push e exclusão de `main`, exige
histórico linear e não declara atores com permissão de bypass, inclusive para
administração. Integre por squash ou rebase.

São exigidas **zero aprovações externas** para permitir manutenção individual;
PR e CI continuam obrigatórios. Quando houver revisores com acesso de escrita,
altere `required_approving_review_count` para `1` ou mais, conforme a equipe.
O campo `do_not_enforce_on_create` dispensa o check na criação inicial da branch;
as atualizações posteriores precisam passar pelas verificações. Essa exceção
permite inicializar um repositório vazio e não autoriza commits ou push por si só.

Para outro repositório, o responsável precisa de permissão administrativa e
autenticação válida no GitHub CLI. Rulesets de branch estão disponíveis para
repositórios públicos no plano Free; confira o plano para repositórios privados.
Leia os rulesets existentes antes de adicionar outro para não duplicar regras.
Após revisar e trocar `OWNER/REPOSITORY` pelo destino, o POST abaixo **cria uma
regra no GitHub**:

```bash
gh api --method POST repos/OWNER/REPOSITORY/rulesets \
    --input .github/main-ruleset.json
gh api repos/OWNER/REPOSITORY/rules/branches/main
```

Para atualizar uma regra existente, use PUT em `repos/OWNER/REPOSITORY/rulesets/ID`
com o mesmo arquivo revisado. A consulta da regra pelo ID deve mostrar
`enforcement: active`, alvo main e nenhuma exceção de bypass. A consulta de regras
efetivas acima também funciona quando a branch ainda não existe. Confirme o check
`checks`, exigência de PR, resolução de conversas e bloqueios de exclusão e
force push. A configuração do servidor pode divergir do JSON local; verifique-a
antes de declarar a proteção ativa. Depois do primeiro envio, confira também a
execução real do job. O check está vinculado ao aplicativo oficial GitHub Actions
(integration_id 15368, consultado na API); uma integração diferente não satisfaz
essa exigência.

Referências: [API de rulesets](https://docs.github.com/en/rest/repos/rules)
e [regras disponíveis](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).

## CI e versões futuras

O workflow em `.github/workflows/ci.yml` prepara ferramentas em runner
Ubuntu 24.04 e executa a suíte em push/PR com o nome estável `checks`. Containers e smoke online dependem de
`workflow_dispatch`. A configuração do workflow não é prova de execução remota.
Após o envio, confira os jobs antes de declarar o resultado do CI.

Uma release deve registrar alterações, compatibilidade, instruções de migração
quando necessárias e limitações. Containers multi-distro e runtime musl/aarch64
seguem sem evidência de execução. A troca de versões de ferramentas, plugins e
fontes exige testes próprios; rollback de dotfiles não desfaz essas instalações.
