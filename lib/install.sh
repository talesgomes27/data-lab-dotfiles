# shellcheck shell=bash
install_component() {
    local dry_run=$1
    if ((dry_run)) || [[ -z "$DEVSHELL_APPROVAL" ]]; then
        python3 "$ROOT/lib/artifacts.py" plan
        return
    fi
    python3 "$ROOT/lib/artifacts.py" check
    if [[ "$DEVSHELL_COMPONENT" == python ]]; then
        # shellcheck source=lib/uv.sh
        source "$ROOT/lib/uv.sh"
        install_python
    else
        python3 "$ROOT/lib/artifacts.py" apply
    fi
}
