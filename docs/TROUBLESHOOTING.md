# Diagnóstico

[Início](../README.md) · [Instalação](INSTALLATION.md) · [Ciência de dados](SCIENCE.md)

## Começar pela seleção aplicada

Na raiz do projeto, use a mesma combinação usada no setup:

```bash
./bin/devshell doctor --profile personal,science
./bin/devshell status --profile personal,science
./bin/devshell diff --profile personal,science
```

Se você aplicou `extras`, inclua-o nos três comandos. O plano compara a
configuração com os perfis informados; mudar a seleção pode propor mudanças
no arquivo de componentes. `--json` oferece o diagnóstico estruturado.

| Retorno | Significado |
|---|---|
| `0` | Operação/plano concluído; no doctor, sem problemas bloqueantes. Confira também avisos. |
| `1` | Cancelamento do setup ou do reparo de permissões do projeto. |
| `2` | Entrada inválida, conflito ou operação recusada. |
| `3` | Pré-requisito ausente ou problemas detectados pelo doctor. |

Ferramentas externas podem propagar outros códigos. O doctor informa problemas;
ele não os corrige automaticamente nem comprova toda a integridade dos binários.

## Jlab sem grupo notebook

Mensagem:

```text
error: Group `notebook` is not defined in the project's `dependency-groups` table
```

O atalho chama `uv run --locked --group notebook jupyter lab`. Ele exige um grupo
`notebook` em `[dependency-groups]` no `pyproject.toml`. Ter o pacote Python
`notebook` nas dependências não cria esse grupo.

Escolha conforme o estudo:

- Se JupyterLab já existe na `.venv`, use `uv run --locked --no-sync python -m
  jupyterlab` para iniciar com a instalação atual. Se o módulo não existir,
  esse comando falhará; ele não instala dependências.
- Se você pretende adaptar um projeto uv ao atalho, execute `uv add --group
  notebook jupyterlab` e depois `jlab`. Isso modifica manifesto, lock e ambiente,
  e pode baixar pacotes. Preserve o gerenciador existente de outros projetos.

`jlab` também precisa ser executado em um projeto, com lock compatível. Se o
lock estiver desatualizado, revise a alteração das dependências e gere-o
conscientemente; não remova `--locked` só para ocultar a divergência.
O [guia científico](SCIENCE.md#iniciar-e-encerrar-jupyterlab) mostra o preparo.

## Terminal, fonte e caminhos

### Ambiente Python pessoal ou do projeto

| Sintoma | Verificação e ação |
|---|---|
| `geral` não aparece | Confira perfil personal, direnv e o [preparo explícito](SCIENCE.md#ambiente-pessoal-e-troca-automática-por-projeto). O diretório precisa conter pyvenv.cfg regular e bin/python e bin/python3 executáveis; caminhos/ancestrais inseguros ou com symlinks são recusados. |
| Outra ativação continua ativa | VIRTUAL_ENV e CONDA_PREFIX herdados são preservados. Abra um terminal sem essa ativação para selecionar o ambiente pessoal. |
| Aviso de Conda ativo no projeto | Execute a desativação pelo próprio Conda antes de usar a troca uv. O helper conserva o estado Conda em vez de tentar desativá-lo parcialmente. |
| Repositório continua em `geral` | Confira `.envrc` com `use devshell_python` e a autorização individual. Só ter pyproject.toml ou `.venv` não habilita a troca. |
| Aviso de `.venv` recusada | Os motivos aparecem com os caminhos exatos. Use `project doctor --path CAMINHO` na CLI Data Lab. Se forem permissões, revise `project fix-permissions --path CAMINHO --dry-run`; se faltar ambiente, prepare-o pelo processo do projeto. `uv sync` não corrige permissões dos pais. Depois, `direnv reload`. |
| `python` usa a distribuição após o aviso | O helper retirou o ambiente anterior para evitar instalar dependências em `geral`. Prepare a `.venv` antes de trabalhar; `uv pip` sem ambiente ativo não é um substituto para essa preparação. |
| A troca só acontece no próximo comando | Hooks rodam antes do prompt. Em `cd projeto && python ...`, use `uv run` ou o caminho explícito da `.venv`. |
| Rollback não apagou `geral`/`.venv` | Ambientes são mantidos fora da transação de dotfiles. Encerre shells abertas para descartar hooks carregados. |

O [modo de manutenção do gerador](SCIENCE.md#manutenção-guiada-de-projetos-existentes)
oferece `--fix-permissions [--sync] [--allow-direnv]`, com confirmações separadas.
Se uma instalação antiga não reconhecer essas opções, revise a atualização
do componente `pyinit` pelo fluxo de instalação do guia.
Se aparecer `Data Lab CLI ausente`, confira `command -v devshell` e siga a
[instalação do lançador](INSTALLATION.md#disponibilizar-devshell-no-path).
Como alternativa, defina `DEVSHELL_BIN` com o caminho absoluto do executável
no checkout. Um symlink simples desse script não substitui o lançador, pois
a CLI localiza suas bibliotecas a partir do próprio caminho.
Se aparecer `checkout ausente`, reinstale a partir da nova cópia, revisando
o novo hash e aprovando conflitos com `--replace-existing` e backup.

### Demais integrações

| Sintoma | Verificação e ação |
|---|---|
| `.zshrc` não está na HOME | A configuração fica em `~/.config/zsh/.zshrc`, indicada por `ZDOTDIR` em `~/.zshenv`. Não crie uma segunda cópia sem revisar a migração. |
| Atalhos não aparecem | Abra nova sessão interativa, confira o perfil e a presença do executável. Bash usa a convenção `~/.bash_aliases` e seu fragmento adicional tem inclusão manual. |
| Ícones quebrados | Selecione FiraCode Nerd Font Mono no emulador; confira `fc-match 'FiraCode Nerd Font Mono'`. |
| Zsh sem prompt/plugins | Confira perfil e instalação. Há fallback nativo quando Starship não está disponível. |
| Ctrl+T sem prévia | Confira bat/batcat e uma possível `FZF_CTRL_T_OPTS` própria. fzf <0.48 não carrega a integração `--zsh`. |
| `gs` não mostra Git | O nome pode pertencer a outro programa. Use `gst`; os atalhos preservam nomes existentes. |
| `fd` ou `bat` não encontrados | No Debian/Ubuntu, tente `fdfind` e `batcat`. |
| Nu não lê configuração alternativa | Compare `$nu.config-path`; use `--env-config` e `--config` com caminhos explícitos. |
| `cd` não usa zoxide no Bash | A substituição do cd é exclusiva do Zsh interativo com o componente selecionado. |

## Instalação e aplicação

| Sintoma | Ação |
|---|---|
| Chezmoi ausente | Use o setup ou planeje/aprove `install --component chezmoi`. |
| Aprovação inválida | Gere e revise novo plano com a mesma seleção; conteúdo ou estado mudou. |
| Dotfiles em conflito | Leia o diff e preserve as edições; a substituição explícita tem backup. |
| Permissões inseguras | Use setup com dry-run para enumerar os alvos. O reparo exige confirmação e não é recursivo. |
| Symlink, hardlink ou dono inesperado | Revise os caminhos e use arquivos regulares sob seu controle; não force o journal. |
| Pacote sem mapeamento/indisponível | Confira os repositórios da sua release. Instale manualmente de fonte oficial ou retire o perfil opcional, quando apropriado. |
| Falta de sudo | Peça ao administrador a instalação dos pacotes apresentados e retome o setup. |
| Ferramenta existente incompatível | Preserve a instalação anterior e revise a [atualização manual](INSTALLATION.md#atualizar-configuração-e-versões). |
| Sem artefato para arquitetura/libc | Use instalação manual oficial; não troque por binário de outra arquitetura. |
| Checksum divergente | Não execute o arquivo; confira release, manifesto e caminho do cache informado. Preserve a cópia para inspeção. |
| Offline sem cache | Prepare os arquivos oficiais exatos e o cache uv, ou retome em modo online. |
| Ferramenta Python em conflito, divergente ou com link órfão | Leia a mensagem do `doctor`: `uv tool uninstall NOME` para a instalação antiga, ou revise e mova a venv ou o link indicado. O projeto não remove nem substitui o que não criou. |
| CPython gerenciado com caminho inseguro, fora da venv | O `doctor` aponta o diretório `cpython-*` em `UV_PYTHON_INSTALL_DIR`. Confira dono e origem; se só houver escrita de grupo/outros, `chmod -R go-w` nesse diretório e planeje de novo. Não mova a venv: o problema é do interpretador, e o setup não altera esse diretório. |
| DuckDB ausente ou inseguro | É opcional. Confira origem, dono e modos dos diretórios e do executável; não aplique chmod recursivo. O reparo genérico do setup pode não abranger sua árvore externa. |

## Recuperação e outros limites

Se houver journal pendente após interrupção, revise `./bin/devshell rollback`
antes de tentar outra aplicação. Uma revisão com `--approve HASH` pode retomar
a recuperação. Backups ausentes/corrompidos ou edição posterior exigem solução
manual. Não edite o journal para contornar uma recusa. Veja
[Backups e recuperação](SECURITY.md#backups-e-recuperação).

A mudança de perfil não apaga silenciosamente ferramentas nem arquivos antigos.
Uma falha/cancelamento de setup pode deixar etapas concluídas; retome após
resolver a causa. `--json` no setup requer `--dry-run`.

Se bibliotecas científicas não resolverem ou compilarem, confira a versão
Python, disponibilidade de wheels e dependências nativas. Não instale via pip
no Python do sistema para contornar o problema. GPU/PyTorch requer avaliação
própria. Docker inacessível não impede os testes offline; não altere permissões
do socket para tentar completar a matriz.

Ao pedir ajuda, informe o comando, os perfis, a distribuição e a mensagem de
erro. Revise qualquer saída antes de compartilhar: diff e logs podem conter
dados privados. Para vulnerabilidades, siga a [política de relato](SECURITY.md#relatar-uma-vulnerabilidade).
