# Histórico de alterações

## Não publicado

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

- Aliases ls/la para eza compartilhados entre Bash e Zsh no perfil personal;
  bootstrap bash_aliases com preservação do atalho l padrão do Ubuntu.

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
