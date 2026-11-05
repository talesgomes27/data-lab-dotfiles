# Data Lab Dotfiles

CLI Bash e bootstrap POSIX sh; Chezmoi renderiza fontes estáticas de `dotfiles/`.
Python >=3.11 padrão cuida de JSON, arquivos atômicos e backups. Consulte
`docs/ARCHITECTURE.md`, `CONTRIBUTING.md` e os ADRs antes de mudar contratos.

- Preserve perfis declarativos e manifestos fixados. Não transforme dados em código.
- Não instale no sistema, use sudo, mude a shell de login, altere HOME real,
  faça commit, push ou publique sem instrução explícita do usuário.
- Teste com HOME/XDG/cache temporários. Nunca use fixtures reais com segredos.
- Toda mudança de comportamento deve ter teste pertinente; não enfraqueça guardas.
- `bash scripts/check.sh`: ShellCheck, shfmt, Bats e unittest offline.
- `bash scripts/containers.sh`: matriz isolada; requer Docker acessível e downloads.
- Antes da entrega: executar checks, conferir ajuda/exemplos, revisão de segurança
  e registrar resultados/limitações em `docs/VALIDATION.md`.
- `setup` coordena os comandos atuais com confirmações; nunca adicione --yes
  ou reaproveite respostas de uma etapa para aprovar outra.
- `plan`, `diff`, `status`, `doctor` e dry-run não podem criar estado persistente.
  Escritas exigem hash aprovado, conflitos explícitos, backup e escopo restrito.
- `update` atualiza só configuração. Versões/checksums mudam por revisão de
  manifestos, com fonte oficial e nova validação. Rollback nunca remove pacotes
  do sistema, interpretadores ou ambientes externos.
- Não declarar distribuição/arquitetura suportada por fixtures ou CI não executada.
