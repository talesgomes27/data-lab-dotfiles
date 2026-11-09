# ADR 004 — Lock com hash para as ferramentas uv

Status: proposta em 2026-11-09; depende de R-022 da `docs/spec.md`.

As CLI Python do perfil `science` (ruff, pre-commit, ipython) fixam a versão
raiz, mas o uv resolve as dependências transitivas a cada instalação. Duas
instalações da mesma versão podem ter dependências diferentes, e nenhum hash
das distribuições baixadas é conferido.

Decisão: cada ferramenta ganha `manifests/python-tools/NOME.txt`, gerado por
`uv pip compile --universal --python-version 3.13 --generate-hashes` a partir
de `NOME==VERSÃO` e revisado como os demais manifestos. A instalação passa
`--constraints NOME.txt --no-build` ao `uv tool install`. Um arquivo por
ferramenta evita conflitos entre elas; `--no-build` evita dependências de build
sem hash. `doctor` compara as distribuições instaladas com o arquivo e aponta
divergência, sem reinstalar: o ADR 003 continua vedando `--force`.

Custo: atualizar uma ferramenta exige regenerar o arquivo com rede, numa
revisão própria. Ferramentas já instaladas antes do lock aparecem no doctor até
serem reinstaladas manualmente, com `uv tool uninstall NOME` seguido de
`install --component python` aprovado.

Limites: constraints com hash não equivalem a `--require-hashes`. Uma
distribuição resolvida que não esteja no arquivo instala sem hash, e o doctor
só a aponta depois. A verificação depende do uv; por isso o piso de versão
sobe para a versão em que o teste offline a provou.

Alternativa considerada: `uv venv` com `uv pip install --require-hashes`, que
garante a política de hash por flag, mas troca os recibos do `uv tool`, o
diagnóstico atual e o fluxo documentado. Fica como plano B se o uv não aplicar
os hashes das constraints.
