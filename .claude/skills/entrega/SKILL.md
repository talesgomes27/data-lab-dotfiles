---
name: entrega
description: "Checklist Antes da entrega do AGENTS.md: checks completos sem skips, ajuda e exemplos, revisão de segurança e registro em docs/VALIDATION.md."
disable-model-invocation: true
---

# Checklist de entrega

Aplique ao diff atual (`git status`, `git diff` e `git diff --cached`).

1. Checks. Rode `bash scripts/check.sh`. Saída 3 indica pré-requisito
   ausente: informe qual e pare. Liste qualquer linha `ok ... # skip`; teste
   pulado não comprova o cenário.
2. Ajuda e exemplos. Se o diff toca `bin/devshell`, `lib/` ou
   `scripts/`, confira `bin/devshell --help` e os comandos citados no README e
   em `docs/USAGE.md` contra o comportamento novo. Se toca `examples/`, rode os
   testes do exemplo afetado como o README dele indica, em cópia temporária.
3. Testes. Toda mudança de comportamento precisa de teste pertinente em
   `tests/`. Aponte o que faltar; não enfraqueça guardas existentes.
4. Segurança. Releia o diff contra as regras do `AGENTS.md`:
   - `plan`, `diff`, `status`, `doctor` e dry-run sem estado persistente;
   - escritas com hash aprovado, conflito explícito, backup e escopo restrito;
   - nenhuma `--yes` nem resposta reaproveitada entre etapas do `setup`;
   - testes só com HOME/XDG/cache temporários, sem segredos em fixtures;
   - versões e checksums mudando só por revisão de manifesto com fonte oficial.
5. Registro. Acrescente em `docs/VALIDATION.md` uma seção datada
   (`## <título> — AAAA-MM-DD`) com o que foi verificado, os números de testes e
   os limites. Não declare distribuição ou arquitetura sem execução real. Se a
   mudança é perceptível ao usuário, atualize `CHANGELOG.md` ("Não publicado").

Relate o resultado de cada item. Não faça commit, push nem PR.
