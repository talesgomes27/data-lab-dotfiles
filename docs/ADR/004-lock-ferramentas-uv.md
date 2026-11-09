# ADR 004 — Venv com hash obrigatório para as ferramentas Python

Status: adotada em 2026-11-09, depois do teste de Q-001 da `docs/spec.md`.
Substitui, para as CLI Python, o uso de `uv tool` do ADR 003.

As CLI Python do perfil `science` (ruff, pre-commit, ipython) fixam a versão
raiz, mas o uv resolve as dependências transitivas a cada instalação. Duas
instalações da mesma versão podem ter dependências diferentes, e nenhum hash
das distribuições baixadas é conferido.

A primeira proposta passava um arquivo de constraints com hashes ao
`uv tool install`. O teste offline com dois wheels locais mostrou que o uv
0.13.5 ignora esses hashes, inclusive com `--with-requirements` e
`UV_REQUIRE_HASHES=1`. Só `uv pip install --require-hashes` recusou um hash
errado e uma dependência ausente do lock.

Decisão: cada ferramenta ganha `manifests/python-tools/NOME.txt`, gerado por
`uv pip compile --universal --python-version 3.13 --generate-hashes` a partir
de `NOME==VERSÃO` e revisado como os demais manifestos. A instalação cria uma
venv própria em `$XDG_DATA_HOME/devshell/tools/NOME` com o CPython gerenciado
de `tool_python`, roda `uv pip install --require-hashes --no-build -r NOME.txt`
e liga `$UV_TOOL_BIN_DIR/NOME` ao executável da venv por symlink. `doctor`
confere a venv, o interpretador, as distribuições contra o lock e o RECORD do
executável, sem executá-lo e sem reinstalar.

Custo: atualizar uma ferramenta exige regenerar o lock com rede, numa revisão
própria. As instalações anteriores, feitas pelo `uv tool`, bloqueiam o plano
até o usuário rodar `uv tool uninstall NOME`; a CLI não chama `uv tool`, para
não afetar outras ferramentas dele. Se uma instalação falhar, a CLI remove só
a venv que criou na mesma execução, porque o uv grava o caminho da venv nos
executáveis e ela não pode ser montada noutro lugar e movida.

Limites: a integridade vale contra troca de arquivo no transporte ou no índice
depois da revisão do lock; não substitui auditoria do que o PyPI publicou na
revisão. A verificação depende do uv, cujo piso sobe para 0.13.5, a versão
testada.

Alternativa descartada: `uv tool install --constraints`, por não aplicar os
hashes. `uv pip sync --require-hashes` também foi descartado: recusa hash
errado, mas instala sem a dependência que falta no lock.
