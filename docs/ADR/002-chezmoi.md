# ADR 002 — Chezmoi com fonte dedicada e journal explícito

Status: adotada na implementação inicial, 2026-11-03.

Chezmoi oferece semântica conhecida de dotfiles e separação da fonte. A raiz
`.chezmoiroot` aponta para `dotfiles/`. O projeto aceita somente fontes estáticas
para manter o planejamento sem escrita/rede. A renderização ocorre numa HOME
temporária e é verificada antes de escrever nos destinos reais.

A CLI mantém seu próprio journal: revisão por hash, backup, aplicação atômica
por arquivo e rollback protegido. Isso também permite XDG absoluto fora da
HOME sem truques nos nomes das fontes. O custo é restringir templates/scripts
Chezmoi; uma futura adoção deles exige rever o contrato de planejamento seguro.
