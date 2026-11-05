# Nushell mantém seu próprio código; nunca source de scripts Bash.
let config_dir = if (($env.XDG_CONFIG_HOME? | default '' | str starts-with '/')) { $env.XDG_CONFIG_HOME } else { $env.HOME | path join '.config' }
$env.STARSHIP_CONFIG = ($config_dir | path join 'starship.toml')
let user_bin = ($env.HOME | path join '.local' 'bin')
let uv_default = if (($env.XDG_DATA_HOME? | default '' | str starts-with '/')) { $env.XDG_DATA_HOME | path dirname | path join 'bin' } else { $user_bin }
let uv_bin = ($env.UV_TOOL_BIN_DIR? | default ($env.XDG_BIN_HOME? | default $uv_default))
if (which python3 | is-not-empty) {
    let safe_paths = (^python3 ($config_dir | path join 'devshell' 'safe-path.py') $user_bin $uv_bin | lines)
    $env.PATH = ($safe_paths | append $env.PATH | uniq)
}
