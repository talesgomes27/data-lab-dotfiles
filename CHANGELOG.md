# Histórico de alterações

## Não publicado

- `rollback --list` mostra o histórico de transações com status, posição na
  cadeia e data de criação, que passa a ser gravada nas transações novas.
  `rollback --prune --keep N` remove backups antigos com plano, hash aprovado,
  lock e renomeação para `pruning/` antes da remoção; recusa transações
  interrompidas ou inválidas e avisa ao remover os backups anteriores ao
  primeiro `apply`. O rollback da transação mais antiga mantida deixa de
  apontar `latest` para uma transação podada.

- `scripts/check.sh` roda Ruff com regras de defeitos fixadas em `ruff.toml`
  (pyflakes, erros de sintaxe/importação, bugbear e `subprocess.run` sem
  `check`), sem regras de estilo. A versão exigida é a de `manifests/python.json`;
  `scripts/ci-setup.sh` instala essa mesma versão nos runners e containers.

- Segurança: a guarda de fontes estáticas do Chezmoi passa a ser uma lista
  permitida, recusando antes da renderização prefixos de atributo como
  `modify_` (script executado pelo Chezmoi), `create_`, `symlink_` e `exact_`.
  CLI, setup, instalação e helpers de Bash/Zsh/Nushell/direnv usam
  `/usr/bin/python3 -I`, sem carregar `.pth` de `.venv` ativa nem PYTHONPATH.

- Pin de `pyinit` atualizado para as correções A1–A6/A2-LF-01 e F1/P3:
  preservação de configurações, criação isolada, composição Ruff/pytest,
  seleção minor na migração, inferência do alvo Ruff e JupyterLab no grupo
  `notebook` do arquétipo `ds`. Gitlink, URL e checksum avançam juntos;
  a reinstalação do gerador continua explícita e separada dos dotfiles.

- `pyinit --migrate` para projetos legados: detecção conservadora, dry-run sem
  estado, backup/rollback e autorização direnv manual. O submódulo e o artefato
  são atualizados juntos por commit, URL e SHA-256; a instalação continua
  exigindo aprovação separada, sem alteração automática da HOME.

- Componente local `install --component devshell`: lançador em `~/.local/bin`
  para o checkout, com aprovação por hash, conflitos explícitos, backups
  privados e diagnóstico sem execução. Funciona offline e permite ao pyinit
  encontrar a CLI pelo PATH; a instalação continua separada dos dotfiles.

- Aliases eza `l`/`la` para grade, `ll`/`lla` para detalhes com Git e datas
  relativas e `lt`/`lta` para árvore de dois níveis, compartilhados por Bash/Zsh.
  Ícones sempre visíveis nesses seis atalhos; `l` substitui o atalho padrão do
  Ubuntu. O alias `ls` continua com ícones automáticos.

- Reparo de permissões lê somente a própria resposta, preservando confirmações
  posteriores quando chamado por pipe; EOF sem Enter cancela. Documentação do
  modo de manutenção
  `--fix-permissions [--sync] [--allow-direnv]` no template; submódulo e
  artefato `pyinit` atualizados juntos para o commit público revisado.

- Diagnóstico de `.venv` com caminhos e motivos exatos; comando `project doctor`
  e reparo explícito `project fix-permissions`, com confirmação/hash, registro
  dos modos anteriores e verificação de inodes. Sem chmod recursivo, criação
  de ambientes, sincronização ou autorização direnv automática.

- Extensão pessoal Zsh em `.zshenv.local`, com validação de caminhos, permissões
  e proprietário. O hash integral do bootstrap continua obrigatório; doctor
  não executa conteúdo pessoal. Recusa de `.zwc` que poderia substituir o texto
  conferido e exceção sticky limitada a diretórios do sistema.

- Template Python público fixado como submódulo. Perfil science instala seu
  gerador como `pyinit`, com aprovação própria, commit e SHA-256 verificados;
  `.envrc` criado com permissões privadas e autorização direnv manual.

- Ambiente pessoal Python opcional em `devshell/venvs/geral`, com seleção
  interativa em Bash/Zsh/Nushell e troca para `.venv` via `.envrc` autorizado.
  Preparação explícita, validação de caminhos e retorno ao ambiente anterior;
  sem downloads na navegação e sem remoção de ambientes no rollback.

- Matriz executa a suíte como usuário comum; Starship verificado também nas
  imagens. Disparo manual prepara dependências reais dos testes opcionais e
  recusa skips. Manual detalha os pré-requisitos por funcionalidade.

- Validação de argumentos com `if` explícito para compatibilidade com o ShellCheck
  do runner Ubuntu 24.04, preservando as recusas de entradas inválidas.

- Preparação da publicação: exclusão de caches/estado local, job CI `checks`
  com nome estável e política revisável de proteção da main para ativação no GitHub.

- Blocos Starship para Java, Rust e Go, com detecção nativa e versão disponível
  no ambiente; sem instalar os runtimes.

- Documentação reorganizada: README com navegação e glossário, instalação guiada,
  manual por tarefas, ciência de dados e diagnóstico do jlab. Planos e relatórios
  locais obsoletos removidos após consolidação das informações úteis.
- Nome Data Lab Dotfiles nos guias públicos; licença MIT destacada, com atribuição
  atual e histórica em LICENSE. Guia de contribuição e relato de vulnerabilidades.

- Perfil opt-in extras para btop, ncdu, tealdeer e Lazygit; DuckDB opcional
  inspecionado no perfil science. Prévia fzf, atalhos seguros e jlab interativo.
- Exemplos científicos isolados de pytest, JupyterLab, DuckDB/Polars/PyArrow
  e R/renv, com lock Python atualizado e sem instalação no sistema.
- Recusa de dois-pontos em diretórios inseridos no PATH para evitar divisão em
  entradas não verificadas.
- Rollback retomável e protegido contra alterações entre etapas; doctor informa
  configuração pendente e verifica arquivos essenciais e metadados uv.
- Artefatos recebem modo final antes da publicação; cache corrompido é
  identificado e preservado para inspeção.
- CI prepara Starship fixado e verificado para testar prompt com linguagens
  simuladas; atualização manual de Chezmoi tem procedimento e teste isolado.
- Zsh interativo usa zoxide no comando cd, mantendo z e zi disponíveis.
- Prompt Starship com blocos arredondados, cores, contexto Git, Python, R,
  Node.js, Quarto e Astro, duração e código de saída em duas linhas.
- FiraCode Nerd Font no perfil personal: ZIP oficial fixado e verificado,
  instalação de usuário e atualização Fontconfig, sem mudar o emulador.
- Inventário local distingue componentes reutilizados, gerenciados por uv e
  configurações aplicadas pelo projeto.


- Expressão do parser aceita igualmente por shfmt 3.12.0 e 3.14.1.

- Setup interativo por perfil, com revisão agregada de permissões, confirmação
  administrativa separada e hashes internos; os comandos individuais permanecem.

- CLI Bash com planejamento aprovado, diagnóstico, diff, dry-run e offline.
- Perfis combináveis e adaptadores de pacotes apenas para revisão manual.
- Dotfiles XDG de Zsh, Bash, Nushell, uv e Starship renderizados por Chezmoi.
- Instalação explícita de artefatos verificados e Python/ferramentas via uv.
- Backups, journal, recuperação de falhas e rollback restrito aos dotfiles.
- Testes isolados, CI proposta, documentação e exemplo científico com lock.

Compatibilidade e limitações são registradas em docs/VALIDATION.md; esta seção
não representa uma release publicada.
