---
name: bump-pyinit
description: Atualiza o pin do pyinit (submódulo python-template-linux) para um commit já revisado, movendo juntos gitlink, versão, URL e SHA-256 em manifests/artifacts.json.
disable-model-invocation: true
argument-hint: "<commit do template já mesclado>"
---

# Atualizar o pin do pyinit

Siga `CONTRIBUTING.md`, seção "Atualizar o template Python". Commit alvo: `$ARGUMENTS`.
Sem commit informado, pergunte qual é; nunca use `git submodule update --remote`
nem escolha o último commit sozinho.

1. Confirme que o commit está na `main` remota do template (PR revisado e
   mesclado): `git -C templates/python-template-linux fetch origin` e
   `git -C templates/python-template-linux branch -r --contains <commit>`.
   Se não estiver, pare e informe.
2. Selecione o commit no submódulo:
   `git -C templates/python-template-linux checkout --detach <commit>`.
3. Calcule o SHA-256 dos bytes do submódulo:
   `sha256sum templates/python-template-linux/scripts/init_project.sh`.
4. Baixe o arquivo da URL fixada no commit para um diretório novo do scratchpad
   e confira que o hash é o mesmo do passo 3. Hashes diferentes: pare e relate.
5. No item `"component": "pyinit"` de `manifests/artifacts.json`, troque juntos
   `version` (commit completo), o commit dentro de `url` e `sha256`. Não mexa em
   outros itens.
6. Rode `bats --print-output-on-failure tests/pyinit.bats` e depois
   `bash scripts/check.sh`. Relate testes pulados; não os trate como aprovados.
7. Registre a mudança em `CHANGELOG.md` ("Não publicado") e os resultados e
   limites em `docs/VALIDATION.md`, no formato das entradas existentes.
8. Mostre `git diff --stat` e `git -C templates/python-template-linux log --oneline -1`.

Não faça commit, push nem `devshell install --component pyinit`: a reinstalação
do gerador é um passo separado que o usuário aprova.
