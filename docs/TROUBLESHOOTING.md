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
| `1` | Cancelamento do setup. |
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
| Ferramenta uv em outra versão | Confira `uv tool list`; o projeto não força substituição. |
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
