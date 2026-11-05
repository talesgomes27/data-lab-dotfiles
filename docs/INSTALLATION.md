# Instalação e manutenção

[Início](../README.md) · [Uso](USAGE.md) · [Diagnóstico](TROUBLESHOOTING.md)

## Antes de começar

Você precisa de Linux, Bash >=4.4, Python >=3.11 e utilitários GNU básicos.
O Python do sistema executa a CLI; bibliotecas do estudo ficam em sua própria
`.venv`. Rede é necessária para downloads não presentes em cache. Pacotes da
distribuição podem exigir sudo, mas inspeção e aplicação de dotfiles não.

Consulte a [matriz de evidências](VALIDATION.md). Pacotes mapeados podem não
existir em todas as releases. O setup não habilita COPR, AUR ou repositórios
extras, não atualiza índices nem instala drivers.

## Obter o projeto e escolher perfis

Na página do repositório no GitHub, abra **Code** e copie a URL de clone, ou
baixe o ZIP e extraia. Abra um terminal na pasta que contém `bootstrap.sh`.
Não execute comandos de uma cópia cujo conteúdo você não revisou.

A [tabela de perfis](../README.md#perfis) descreve as combinações. Os exemplos
abaixo usam `personal,science`. Se escolher `personal,science,extras`, use essa
mesma seleção em setup, plan, diff, status, doctor e update.

## Instalação guiada

```bash
./bin/devshell setup --profile personal,science --dry-run
./bin/devshell setup --profile personal,science
```

O dry-run inspeciona permissões, ferramentas, pacotes e bloqueios, sem gravar
estado nem baixar arquivos. Para JSON, acrescente `--json` ao dry-run.
A execução efetiva percorre estas etapas:

1. Apresenta caminhos com permissões problemáticas. Após confirmação, remove
   apenas escrita de grupo/outros dos alvos permitidos, sem recursão. Symlinks,
   hardlinks, donos inesperados e ancestrais inseguros fora do escopo exigem
   correção manual.
2. Apresenta pacotes ausentes e mapeados. A execução administrativa tem uma
   confirmação própria; o gerenciador de pacotes pode perguntar novamente.
   Um pacote sem mapeamento bloqueia a tentativa administrativa parcial.
3. Mantém uv >=0.9.0, Chezmoi >=2.62.0, Nushell >=0.116.1 e Zsh >=5.9
   compatíveis já disponíveis. Versões antigas exigem atualização manual.
   Cada componente ausente de usuário tem plano e confirmação próprios.
   Plugins, fonte e Python passam por verificação idempotente.
4. Mostra o plano e o diff dos dotfiles. Responda `s` ou `sim` para aplicar.
   Conflitos exigem também a palavra `substituir`. Há backup dos arquivos
   preexistentes alterados.
5. Executa `doctor`. Código zero indica que as verificações do perfil passaram;
   seus limites estão em [Segurança](SECURITY.md).

Resposta vazia, `n` ou EOF cancelam a etapa. As etapas concluídas permanecem;
execute novamente para retomar. Reparos de permissões e instalações não fazem
parte do rollback dos dotfiles. O setup não aceita `--yes` ou `--approve` para
dispensar suas confirmações. `setup --json` exige `--dry-run`.

O componente DuckDB CLI de science é opcional: ausência ou caminho inseguro gera
aviso, sem instalação automática. O pacote Python DuckDB é uma dependência
independente do exemplo científico. Os pacotes de `extras` também variam por
release; omita o perfil se eles não estiverem disponíveis e você não desejar
instalá-los manualmente. `tldr --update` é uma operação manual de rede/cache.

## Primeiro acesso

```bash
zsh
./bin/devshell doctor --profile personal,science
```

Na sessão Zsh, confira `ls`, `la` e Ctrl+R. Selecione **FiraCode Nerd Font Mono**
no emulador; a instalação registra a fonte, mas não muda as preferências visuais.
Confira a família disponível com `fc-match 'FiraCode Nerd Font Mono'`.

Zsh lê `~/.config/zsh/.zshrc` por meio de `ZDOTDIR` em `~/.zshenv`; por isso não
é necessário criar outra cópia de `.zshrc` na HOME. Antes de aprovar `.zshenv`,
revise como migrar uma configuração Zsh anterior, pois não há mesclagem automática.

A troca da shell de login é opcional e manual. Confira o caminho de Zsh em
`/etc/shells`; se `/usr/bin/zsh` for o caminho válido da máquina, execute
`chsh -s /usr/bin/zsh` e autentique-se no seu terminal. Encerre e reabra a sessão
do usuário. Se a política exigir administrador, peça sua intervenção. Bash
continua disponível para scripts; não altere `/bin/sh` nem os shebangs.

## Bash e Nushell

O `~/.bash_aliases` gerenciado inclui os aliases compartilhados. O Bash padrão
do Ubuntu já o carrega; em outras configurações, isso precisa ser conferido.
O `~/.bashrc` não é sobrescrito. Para as integrações adicionais do fragmento
Bash, revise-o e inclua manualmente no seu `~/.bashrc`:

```bash
source "${XDG_CONFIG_HOME:-$HOME/.config}/devshell/bashrc"
```

Use XDG_CONFIG_HOME absoluto ou seu default `~/.config`. O atalho `l='ls -CF'`
do Ubuntu é preservado com GNU ls quando o alias `ls` passa a usar eza.
No Bash, o projeto não substitui `cd` por zoxide.

Nushell é complementar. Inicie com `nu`; ela lê os arquivos `env.nu` e
`config.nu` em sua configuração XDG. Para diagnosticar uma configuração
alternativa, use `nu --env-config CAMINHO/env.nu --config CAMINHO/config.nu`.
O prompt Nu recebe o código de saída, mas não a duração do comando.

## Operação manual com hashes

Use esta sequência quando desejar controlar a aplicação separadamente:

```bash
./bin/devshell plan --profile personal,science --json
./bin/devshell diff --profile personal,science
# Revise o plano e copie o valor approval, usando exatamente o mesmo perfil.
./bin/devshell apply --profile personal,science --approve HASH_REVISADO
./bin/devshell doctor --profile personal,science
```

`HASH_REVISADO` é um marcador: substitua-o pelo hash exibido. Uma mudança no
conteúdo ou no estado invalida a aprovação. Conflitos exigem ainda
`--replace-existing`, após ler o diff. `apply` não instala ferramentas.

Se Chezmoi ou uv faltarem, planeje cada instalação e repita com o hash revisado:

```bash
./bin/devshell install --component chezmoi
./bin/devshell install --component chezmoi --approve HASH_DA_INSTALACAO
```

O mesmo fluxo atende `uv`, `nu`, `plugins`, `firacode` e `python`. Para Python,
use também `--profile science` se quiser as ferramentas CLI declaradas. Se
`~/.local/bin` ainda não estiver no PATH, confira sua segurança e use
`PATH="$HOME/.local/bin:$PATH" ./bin/devshell ...` nessa sessão.
`sh bootstrap.sh` sem argumentos apenas planeja; com argumentos delega à CLI.

## Atualizar configuração e versões

Para dotfiles, revise as fontes em `dotfiles/` e o plano:

```bash
./bin/devshell update --profile personal,science
./bin/devshell diff --profile personal,science
./bin/devshell update --profile personal,science --approve HASH_REVISADO
```

`update` não executa git pull nem atualiza ferramentas. Versões e checksums
mudam por revisão de manifestos. O instalador recusa substituir arquivos de
artefatos com conteúdo diferente. Leia os destinos exatos do plano de install;
preserve o executável anterior em backup privado, confira-o e mova-o para essa
área antes de gerar um novo plano de instalação. Para uv, trate uv e uvx juntos.
Só restaure ao destino depois de conferir que não sobrescreverá outra alteração.

Esse procedimento foi testado para Chezmoi com executáveis artificiais; troca
de plugins, fontes e ferramentas uv exige avaliação própria. A troca de vários
arquivos não é atômica. Não a faça durante operações das ferramentas afetadas.
O [rollback](SECURITY.md#backups-e-recuperação) cobre dotfiles, não instalações.

## Offline e caminhos de usuário

`--offline` proíbe downloads e a execução administrativa de pacotes pelo setup.
Para artefatos, prepare o arquivo oficial exato no cache
`$XDG_CACHE_HOME/devshell/artifacts/SHA256`; conteúdo divergente é recusado.
Python usa o cache próprio de uv e interpretadores disponíveis.

Os defaults de configuração, dados e estado seguem XDG. Valores XDG relativos
usam os defaults da CLI. UV_PYTHON_INSTALL_DIR, UV_TOOL_DIR, UV_TOOL_BIN_DIR e
UV_CACHE_DIR absolutos podem ser definidos explicitamente; o projeto não os
exporta globalmente. A fonte fica em `$XDG_DATA_HOME/fonts/FiraCodeNerdFont`.
Confira mais opções em `./bin/devshell --help`.
