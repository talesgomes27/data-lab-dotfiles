$env.config.show_banner = false
$env.config.history.file_format = 'sqlite'
$env.config.history.max_size = 50000
$env.config.history.sync_on_enter = true
let config_dir = if (($env.XDG_CONFIG_HOME? | default '' | str starts-with '/')) { $env.XDG_CONFIG_HOME } else { $env.HOME | path join '.config' }
let components_file = ($config_dir | path join 'devshell' 'components')
let features = if ($components_file | path exists) { open --raw $components_file | str trim | split row ' ' } else { [] }
if $nu.is-interactive and ('uv' in $features) and ('direnv' in $features) and (which direnv | is-not-empty) and (which python3 | is-not-empty) and (($env.VIRTUAL_ENV? | default '') == '') and (($env.CONDA_PREFIX? | default '') == '') and (($env.DIRENV_DIR? | default '') == '') {
    let data_dir = if (($env.XDG_DATA_HOME? | default '' | str starts-with '/')) { $env.XDG_DATA_HOME } else { $env.HOME | path join '.local' 'share' }
    let general = ($data_dir | path join 'devshell' 'venvs' 'geral')
    let safe_bins = (^python3 ($config_dir | path join 'devshell' 'safe-path.py') --venv ($general | path join 'bin') | lines)
    if ($safe_bins | is-not-empty) {
        $env.VIRTUAL_ENV = $general
        $env.PATH = ($safe_bins | append $env.PATH | uniq)
        hide-env --ignore-errors PYTHONHOME
    }
}
if ('starship' in $features) and (which starship | is-not-empty) {
    $env.PROMPT_COMMAND = {|| ^starship prompt --status $env.LAST_EXIT_CODE }
    $env.PROMPT_COMMAND_RIGHT = {|| '' }
    $env.PROMPT_INDICATOR = ''
}
if ('zoxide' in $features) and (which zoxide | is-not-empty) {
    $env.config.hooks.env_change.PWD = [{|| ^zoxide add -- $env.PWD }]
}
if $nu.is-interactive and ('direnv' in $features) and (which direnv | is-not-empty) {
    # pre_prompt cobre também allow/reload e alterações da .venv sem mudar de pasta.
    $env.config.hooks.pre_prompt ++= [{||
        let exit_code = ($env.LAST_EXIT_CODE? | default 0)
        let result = (^direnv export json | complete)
        if $result.stderr != '' { print --stderr --no-newline $result.stderr }
        let changes = ($result.stdout | from json | default {})
        for item in ($changes | transpose name value) {
            if $item.value == null {
                hide-env --ignore-errors $item.name
            } else {
                let value = if $item.name == 'PATH' { $item.value | split row (char esep) } else { $item.value }
                load-env {($item.name): $value}
            }
        }
        $env.LAST_EXIT_CODE = $exit_code
    }]
}
# Navegação explícita por consulta; sem interpolação de comandos shell.
def --env z [query: string] { cd (^zoxide query -- $query | str trim) }
