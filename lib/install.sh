# shellcheck shell=bash
install_component() {
    local dry_run=$1
    if [[ "$DEVSHELL_COMPONENT" == devshell ]]; then
        if ((dry_run)) || [[ -z "$DEVSHELL_APPROVAL" ]]; then
            devshell_python "$ROOT/lib/launcher.py" plan
        else
            devshell_python "$ROOT/lib/launcher.py" apply
        fi
        return
    fi
    if ((dry_run)) || [[ -z "$DEVSHELL_APPROVAL" ]]; then
        devshell_python "$ROOT/lib/artifacts.py" plan
        return
    fi
    devshell_python "$ROOT/lib/artifacts.py" check
    if [[ "$DEVSHELL_COMPONENT" == python ]]; then
        # shellcheck source=lib/uv.sh
        source "$ROOT/lib/uv.sh"
        install_python
    else
        devshell_python "$ROOT/lib/artifacts.py" apply
    fi
}
