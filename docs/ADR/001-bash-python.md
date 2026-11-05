# ADR 001 — Bash na orquestração e Python padrão na escrita

Status: adotada na implementação inicial, 2026-11-03.

Bash facilita a composição das ferramentas Linux sem framework. Bootstrap é
POSIX sh; a CLI requer Bash >=4.4. Serializar JSON e validar backup/metadados
em shell exigiria parsers frágeis e mais dependências. Python >=3.11 padrão é
usado exclusivamente como helper dessas fronteiras e dos artefatos verificados.
Não instalamos bibliotecas pip para executar a CLI. O custo é exigir Python
prévio da distribuição; uma instalação Linux sem ele precisa de etapa manual.
