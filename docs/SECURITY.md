# Segurança, backups e recuperação

[Início](../README.md) · [Diagnóstico](TROUBLESHOOTING.md) · [Validação](VALIDATION.md)

## Escopo e downloads

Toda inspeção é local e sem privilégios. A CLI não chama chsh, git pull/push,
direnv allow, remoção de .venv ou instalador shell baixado. Os comandos
individuais apenas apresentam os pacotes administrativos. O setup guiado pode
executar o comando de pacotes exibido com sudo após confirmação específica;
sem essa autorização, não há execução administrativa. Confie no conteúdo do clone antes de executá-lo: um hash de plano não
protege contra código malicioso no próprio projeto.

O instalador explícito aceita apenas URLs HTTPS de fontes GitHub declaradas,
versões exatas e SHA-256. O manifesto registra o digest do asset da release;
os plugins fixados têm checksum obtido da fonte oficial. Não há busca de
latest durante a operação. Arquivos tar são lidos sem extração arbitrária:
paths absolutos, `..`, links executáveis e arquivos especiais são recusados.
Links README de documentação dos plugins oficiais são ignorados, nunca extraídos. O cache é
revalidado antes do uso. Uma atualização de tag cujo conteúdo mudou falha no
checksum, em vez de executar conteúdo novo silenciosamente.

O gerador `pyinit` usa o mesmo fluxo: fonte pública fixada por commit e
SHA-256, correspondente ao submódulo versionado. Sua instalação não executa o
script. Criar um projeto exige um comando explícito; autorizar o `.envrc`
continua manual e exige revisar todo o conteúdo.

A instalação de interpretadores é delegada a uv com versões fixadas e sem
`--force`. Cada CLI Python (Ruff, pre-commit, IPython) tem um lock em
`manifests/python-tools/` com a versão e o SHA-256 de todas as dependências,
inclusive as transitivas. Ela é instalada numa venv própria em
`$XDG_DATA_HOME/devshell/tools/NOME`, com o CPython gerenciado de
`tool_python`, por `uv pip install --require-hashes --no-build`: um hash
divergente, uma dependência ausente do lock ou um pacote que exigiria
compilação interrompem a instalação. O executável fica num symlink em
`$UV_TOOL_BIN_DIR` (por padrão `~/.local/bin`). Depois da instalação, a CLI tira
a escrita de grupo e outros dos arquivos da venv que acabou de criar, porque o
uv copia os modos do próprio cache. A instalação roda sem a venv
ativa nem as variáveis `UV_*` do usuário além dos diretórios do Data Lab.
O `uv tool install` não é usado porque não aplica os hashes (ADR 004).
O uv precisa estar na versão 0.13.5 ou superior, a versão em que esse
comportamento foi testado.

Se a instalação de uma ferramenta falhar, a CLI remove só a venv que ela criou
naquela execução e não cria o symlink; as ferramentas anteriores do mesmo plano
ficam. Uma interrupção por sinal pode deixar uma venv parcial: o plano seguinte
a classifica como divergente e pede revisão manual, sem apagá-la.

Instalações anteriores feitas pelo `uv tool` bloqueiam o plano até você as
remover, porque a CLI nunca chama `uv tool` (isso afetaria outras ferramentas
suas). A migração é:

```bash
uv tool uninstall ruff
uv tool uninstall pre-commit
uv tool uninstall ipython
./bin/devshell install --component python --profile science --json
# Revise o plano, então:
./bin/devshell install --component python --profile science --approve HASH
```

Os hashes protegem contra troca de arquivo no transporte ou no índice depois da
revisão do lock; não auditam o que o PyPI publicou nessa revisão. O lock
científico, por outro lado, fixa a resolução do projeto. O lock do exemplo científico contém os hashes de
artefatos de dependências resolvidos. Fontes oficiais e checksums reduzem o
risco de transporte/substituição, mas não equivalem a auditoria do fornecedor.

O lançador local `install --component devshell` não usa download nem altera
manifestos de ferramentas. O hash aprovado abrange caminho do checkout,
conteúdo proposto, modos, snapshots dos destinos e fontes da implementação.
Conflitos exigem `--replace-existing`; symlinks, hardlinks e caminhos inseguros
são recusados pelas mesmas guardas dos arquivos gerenciados. Ele referencia
um checkout confiável, acompanha suas atualizações e não faz sandbox do código
executado. Não mantenha no PATH lançadores para cópias em que não confia.

## Aplicação e caminhos

`apply` exige o SHA-256 do plano atual. Arquivos existentes diferentes e não
reconhecidos como versão gerenciada exigem `--replace-existing`. Symlinks em
alvos/ancestrais, hardlinks, arquivos especiais, permissões inseguras e
proprietário inesperado são recusados. Use diretórios sob seu controle; não
execute em diretórios compartilhados hostis.

Diretórios adicionados automaticamente ao PATH são recusados se contiverem
`:`: nesse contexto o caractere dividiria um caminho em entradas separadas.
O instalador uv também recusa `UV_TOOL_BIN_DIR` com `:` antes de gravar.

## Backups e recuperação

A instalação do lançador tem journal próprio em `launcher-backups/UUID`, sob
o diretório de estado do Data Lab, e registro atual em `launcher.json`. Antes
de substituir cada arquivo, grava cópia privada dos bytes anteriores; o
manifesto registra hashes, modos, caminhos e etapas concluídas. Falha de backup
impede a substituição. Falha parcial posterior mantém as etapas concluídas e
o registro `partial`: confira os backups antes de restaurar manualmente ou
replanejar a instalação. Não restaure um modo inseguro automaticamente.
Rollback de dotfiles preserva lançador, registro e backups da instalação.

Antes da escrita, Chezmoi renderiza numa HOME temporária, a CLI confere os
bytes e obtém um lock exclusivo. Cada arquivo existente é copiado com seus
metadados para uma transação em `$XDG_STATE_HOME/devshell/transactions/ID`.
O registro de perfis (`$XDG_STATE_HOME/devshell/profiles`) só escolhe perfis
válidos de `profiles/`: é lido sem seguir symlink e recusado com outro dono ou
hardlink, e qualquer escrita continua exigindo o hash aprovado.
O journal é escrito antes de alterar os alvos; arquivos novos usam modo 600,
backups/estado ficam em diretórios privados. Arquivos preexistentes conservam
modo, UID e GID. Substituições são atômicas por arquivo, não por diretório.

Uma falha capturada durante aplicação tenta restaurar os arquivos já escritos.
Se o processo for morto ou a máquina cair, um journal pending impede a próxima
aplicação. `rollback` pode recuperar os alvos registrados, verificando se estão
no estado anterior ou no estado aplicado. Um disco que permaneça cheio ou
falha de hardware pode impedir a recuperação automática; preserve o backup e
resolva o armazenamento antes de tentar novamente.

Antes de restaurar, rollback registra o estado `rolling-back`. Uma nova
revisão pode retomar a operação, aceitando somente arquivos que ainda estejam
no estado aplicado ou no estado anterior registrado. Cada alvo é conferido
novamente imediatamente antes de sua restauração; edição detectada interrompe
a operação. O lock coordena processos devshell, não impede escritores externos.
Backups ausentes ou com hash incorreto são recusados com diagnóstico específico.

O reparo `project fix-permissions` exige revisão e confirmação ou hash explícito,
limita-se a diretórios próprios sob HOME na cadeia até `.venv/bin` e remove
somente bits de escrita de grupo/outros. O Python é `/usr/bin/python3 -I -B`,
isolando PYTHONPATH, PYTHONHOME e site de usuário. Inspeção não importa código do
projeto, executa seu interpretador nem lê conteúdo de `.envrc`/pacotes.

Antes de alterar modos, a CLI valida o caminho seguro do registro, revalida o
plano e grava metadados privados dos modos anteriores. Os reparos compartilham
as guardas por descritor do setup. O registro permanece disponível mesmo se uma
etapa posterior falhar; arquivos não são copiados, alterados ou removidos.
O reparo não segue symlinks, não é recursivo e não modifica interpretadores
externos. Seus modos não entram no rollback de dotfiles. Root e escritores do
mesmo UID continuam fora da garantia contra alterações concorrentes.

Personalizações Zsh ficam no arquivo opcional `zsh/.zshenv.local` do XDG_CONFIG_HOME.
O bootstrap `.zshenv` permanece integralmente gerenciado, sem ignorar trechos ou
aceitar hashes de modificações locais automaticamente. Antes de carregar a
extensão, Zsh confere por builtins o arquivo regular, proprietário atual, link
único, ausência de symlinks e escrita por grupo/outros em todo o caminho. Apenas
diretórios sticky do sistema recebem a exceção de escrita compartilhada.
Doctor reutiliza as guardas de caminhos/metadados sem executar o código pessoal;
setup inclui o arquivo na revisão de permissões. Seu conteúdo não é auditado,
versionado ou alterado pelo Data Lab: pode executar código e deve ser confiável.

Zsh pode preferir um `.zwc` mais novo ao texto. O bootstrap recusa a extensão se
seu `.zwc` estiver presente, inclusive symlink quebrado. Doctor e setup sinalizam
os compilados correspondentes a `.zshenv`, `.zprofile`, `.zshrc` e à extensão;
a inspeção nunca os executa. Um compilado da própria `.zshenv` pode impedir o
carregamento do bootstrap antes que ele se proteja: mantenha esses caches ausentes
e use doctor para detectá-los. Essas verificações não impedem alterações
concorrentes por root ou processos do mesmo UID. Rollback preserva a extensão.

O `doctor` verifica arquivos esperados, presença e hashes de arquivos essenciais
dos plugins e da fonte e, para cada ferramenta Python, a venv, o interpretador
dela, as distribuições instaladas contra o lock e o RECORD do executável e dos
módulos essenciais, sem executá-la. Distribuições com marcador de plataforma
ausentes não geram alerta, porque o doctor não avalia marcadores. Para CPython,
verifica caminho executável e a versão declarada no cabeçalho instalado: isso
não prova integridade do binário. O RECORD também não é uma assinatura contra
um invasor capaz de alterar tanto o executável quanto os metadados locais.
As versões mínimas de uv, Chezmoi, Zsh e Nushell continuam sendo consultadas
por `--version` com HOME e diretórios XDG temporários. Isso reduz efeitos
normais de inicialização, mas não é sandbox: os binários ainda precisam ser
confiáveis e podem acessar caminhos absolutos. Interpretadores e ferramentas
uv de science são conferidos por arquivos e metadados, sem executá-los.
O checksum e a permissão executável de `pyinit` também são conferidos sem
executar o gerador.

```bash
./bin/devshell rollback --json
# Revise o plano, então:
./bin/devshell rollback --approve HASH_DO_ROLLBACK
```

Rollback só atua sobre caminhos reconhecidos e registrados. Backups corrompidos
ou edições posteriores são recusados antes da restauração. Se um arquivo foi
editado manualmente, copie-o para um local privado, faça a mesclagem necessária
e só então decida como recuperar. Não edite o journal para forçar uma operação.
A restauração recupera conteúdo, modo, UID/GID e timestamps do backup. Não há
garantia de preservar ACLs/capabilities/xattrs em todos os filesystems; o escopo
suportado é arquivo regular do usuário. Diretórios vazios podem permanecer.

### Histórico e poda de backups

`rollback --list` mostra cada transação com status, posição na cadeia
(`cadeia 0` é a atual) e data de criação, sem gravar nada. Transações criadas
antes desta versão não têm data. Entradas inválidas aparecem com o motivo.

```bash
./bin/devshell rollback --list
./bin/devshell rollback --prune --keep 2 --json
# Revise ids, bytes e avisos, então:
./bin/devshell rollback --prune --keep 2 --approve HASH_DA_PODA
```

A poda mantém a transação atual e as N-1 anteriores da cadeia e remove as
demais, inclusive as que ficaram fora da cadeia depois de um rollback. A
remoção é irreversível. O plano avisa quando remove a primeira transação da
cadeia, que guarda os dotfiles de antes do primeiro `apply`, e quando remove
uma transação que substituiu com `--replace-existing` um arquivo que você
tinha editado: nos dois casos ela guarda a única cópia do original. Copie esses
backups para um local privado antes, se quiser conservá-los. Depois da poda, o
rollback só volta até a transação mais antiga mantida; desfeita essa, não há
transação para restaurar. Sem transação atual (depois de desfazer todas), não
há o que manter: o plano avisa que remove todas as listadas.

A aprovação cobre `latest`, N e o hash de cada arquivo; qualquer mudança exige
novo plano. Sob o lock, cada transação sai de `transactions/` por renomeação
para `pruning/` antes de ser apagada, sem seguir symlinks. Uma interrupção
deixa resto apenas em `pruning/`, e a poda seguinte o remove.

A poda recusa o histórico inteiro quando encontra:

| Situação | O que fazer |
|---|---|
| Transação `pending` ou `rolling-back` que é a atual | Execute `rollback` e conclua a recuperação antes de podar. |
| Transação `pending` ou `rolling-back` fora da cadeia (interrupção depois de mover `latest`) | `rollback` não a alcança e desfaria outra transação. Confira com `rollback --list` e `diff` se os dotfiles estão como esperado, preserve os backups dela num local privado e mova o diretório para fora do estado. |
| Diretório sem `manifest.json` ou com manifesto ilegível (interrupção entre a criação e o journal) | Confira em `rollback --list` que não é `latest`; revise e mova o diretório para um local privado fora do estado. |
| Arquivo `.devshell-*` dentro de uma transação (gravação interrompida) | Com o manifesto legível, o arquivo é temporário: remova só ele. |
| Nome fora do padrão, symlink ou item inesperado | Não foi criado pela CLI: revise e mova para fora de `transactions/`. |
| Status desconhecido | Não edite o manifesto; preserve o diretório e abra uma issue. |
| `latest` aponta para transação inexistente | Não crie a transação: confira `rollback --list`, preserve o estado e abra uma issue. |
| Resto inesperado em `pruning/` | O conteúdo não veio de uma poda: revise e mova para fora do estado. |

| Alteração | Recuperação |
|---|---|
| Dotfile preexistente aplicado | rollback do backup, se não houve edição posterior |
| Dotfile criado pela transação | remoção pelo rollback, se ainda corresponde ao aplicado |
| Transação removida pela poda | irreversível; rollback só alcança as transações mantidas |
| Diretórios criados | podem permanecer vazios |
| Binários/plugins instalados | preservar/remover manualmente os paths revistos |
| uv Python/tools/cache | manutenção manual por uv; sem remoção automática |
| Ambiente pessoal `geral` | criação/manutenção explícita por uv; fora do rollback dos dotfiles |
| Pacotes do sistema via setup | comando exibido e confirmado separadamente; recuperação manual |
| Drivers e login shell | nunca alterados pela CLI |
| Projetos e .venv externos | fora do escopo, nunca removidos |

O setup oferece correções de permissões somente após exibir cada caminho e
seu modo anterior/proposto. Ele não usa chmod recursivo, recusa alvos
redirecionados, donos inesperados e arquivos com múltiplos hardlinks e não
corrige ancestrais fora do escopo declarado. A revisão é revalidada antes da
primeira correção, e cada descritor é conferido antes de fchmod. Ajustes de
modo explicitamente autorizados não são parte do rollback dos dotfiles.
Mudanças concorrentes ou falhas podem interromper uma sequência de reparos já
iniciada; o setup não promete uma transação global para permissões/pacotes.

Instalações não são uma transação de configuração. Uma interrupção pode deixar
parte dos binários/plugins instalada; repetir a mesma versão completa os
arquivos ausentes e recusa divergências. Nenhum binário preexistente diferente
é substituído. Para atualização de versões, mantenha a anterior e faça a
substituição manual após revisar as fontes. O rollback nunca desinstala
pacotes nem apaga interpretadores.

## Dados privados

Não versione histórico, kernelspecs pessoais, SSH, credenciais ou `.env`.
Os relatórios contêm caminhos/hashes e não armazenam os conteúdos originais;
os backups contêm o dotfile original e devem permanecer privados. `diff` exibe
conteúdo local por solicitação: não envie esse resultado a serviços externos
sem revisão. Não redirecione logs de comandos sensíveis para o repositório.

Histórico das shells é local; começar uma linha com espaço evita registro no
Zsh/Bash configurados. Isso não deve ser usado como controle para segredos:
use entrada interativa ou armazenamento apropriado. direnv só carrega `.envrc`
após autorização individual; o projeto nunca a concede automaticamente.

`use devshell_python` seleciona uma `.venv` existente por PATH/VIRTUAL_ENV,
sem executar `activate` nem sincronizar dependências. A seleção confere
diretórios e ancestrais, recusa symlinks nos diretórios e exige pyvenv.cfg
regular e python/python3 executáveis. Isso não autentica os executáveis ou os
pacotes: autorize somente repositórios confiáveis. Symlinks dos próprios
executáveis Python são normais em venvs e podem apontar ao interpretador uv.
Sem `.venv` válida, o helper retira o ambiente anterior do PATH e avisa,
retornando sucesso para o direnv aplicar essa retirada. `.envrc` não autorizado
continua bloqueado e não provoca troca. Em projetos ainda não preparados,
`uv pip install` pode atingir o ambiente pessoal que permaneceu ativo; prefira
os comandos de projeto ou um destino explícito.
Conda ativo é uma exceção: o helper avisa e o preserva integralmente até sua
desativação explícita, sem tentar reconstituir seu estado de shell.


## Relatar uma vulnerabilidade

A versão atual é experimental, sem uma série de releases estáveis mantidas.
Correções são destinadas à versão em desenvolvimento; versões antigas não têm
um compromisso de backport. A [validação](VALIDATION.md) delimita as plataformas
e operações verificadas e não constitui garantia geral de segurança.

No repositório publicado, use **Security > Report a vulnerability** se o canal
privado estiver habilitado. Se essa opção não estiver disponível, abra uma issue
apenas solicitando um canal privado, sem divulgar detalhes exploráveis,
credenciais ou dados pessoais. Não há um endereço privado de contato declarado
nesta cópia local; o mantenedor deve definir esse canal ao preparar a publicação.

Em contato privado, forneça a versão/revisão, comando e perfis envolvidos,
impacto observado e uma reprodução com dados artificiais. O mantenedor deve
confirmar recebimento e combinar a divulgação da correção; não há prazo de
resposta garantido nesta fase. Problemas comuns de instalação podem usar issues
públicas após revisão dos dados compartilhados.
