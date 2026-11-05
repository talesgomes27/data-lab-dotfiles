# Exemplo R com renv

[Início](../../README.md) · [Guia científico](../../docs/SCIENCE.md)

Copie este diretório para uma nova pasta de projeto. O R e o pacote `renv`
devem estar disponíveis; verifique sua procedência e versão antes de continuar.
Na cópia, execute `Rscript --vanilla init.R` uma única vez. O comando cria
`.Rprofile`, `renv/` e `renv.lock` do projeto usando o R e o renv locais. Ele
recusa inicializar caso esses caminhos já existam. Uma interrupção pode deixar
arquivos parciais: revise-os manualmente antes de tentar novamente.

Depois, execute `Rscript analysis.R`. Para adicionar dependências, use o fluxo
normal de renv no projeto, revise as fontes e registre as versões com
`renv::snapshot()`. `renv::restore()` pode baixar e instalar pacotes na biblioteca
do projeto. Este exemplo não instala R nem bibliotecas no sistema.
