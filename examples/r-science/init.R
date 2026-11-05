# Inicialização explícita em uma cópia deste exemplo; não substitui projeto existente.
project <- normalizePath(getwd(), mustWork = TRUE)
if (!file.exists(file.path(project, "analysis.R"))) {
  stop("Execute este comando na cópia do diretório r-science.")
}
existing <- file.path(project, c(".Rprofile", "renv.lock", "renv"))
links <- Sys.readlink(existing)
if (any(file.exists(existing) | (!is.na(links) & nzchar(links)))) {
  stop("Projeto renv ou .Rprofile existente: revise manualmente antes de continuar.")
}
if (!requireNamespace("renv", quietly = TRUE)) {
  stop("O pacote renv não está disponível neste R; instale-o antes de inicializar.")
}
renv::init(project = project, bare = TRUE, restart = FALSE)
renv::snapshot(project = project, packages = "renv", prompt = FALSE)
