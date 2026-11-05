$env.config.show_banner = false
$env.config.history.file_format = 'sqlite'
$env.config.history.max_size = 50000
$env.config.history.sync_on_enter = true
let config_dir = if (($env.XDG_CONFIG_HOME? | default '' | str starts-with '/')) { $env.XDG_CONFIG_HOME } else { $env.HOME | path join '.config' }
let components_file = ($config_dir | path join 'devshell' 'components')
let features = if ($components_file | path exists) { open --raw $components_file | str trim | split row ' ' } else { [] }
if ('starship' in $features) and (which starship | is-not-empty) {
    $env.PROMPT_COMMAND = {|| ^starship prompt --status $env.LAST_EXIT_CODE }
    $env.PROMPT_COMMAND_RIGHT = {|| '' }
    $env.PROMPT_INDICATOR = ''
}
if ('zoxide' in $features) and (which zoxide | is-not-empty) {
    $env.config.hooks.env_change.PWD = [{|| ^zoxide add -- $env.PWD }]
}
# Navegação explícita por consulta; sem interpolação de comandos shell.
def --env z [query: string] { cd (^zoxide query -- $query | str trim) }
