setup() {
    umask 077
    chmod go-w "$BATS_TEST_TMPDIR" "$BATS_TEST_TMPDIR/.."
    export FOUNDRY_ROOT="$BATS_TEST_DIRNAME/.."
    export HOME="$BATS_TEST_TMPDIR/home"
    export XDG_CONFIG_HOME="$HOME/.config" XDG_STATE_HOME="$HOME/.local/state"
    export XDG_CACHE_HOME="$HOME/.cache" XDG_DATA_HOME="$HOME/.local/share"
    export UV_CACHE_DIR="$HOME/.cache/uv" UV_PYTHON_INSTALL_DIR="$HOME/.local/share/uv/python"
    export UV_TOOL_DIR="$HOME/.local/share/uv/tools" UV_TOOL_BIN_DIR="$HOME/.local/bin"
    mkdir -p "$HOME"
    export DEVSHELL_OS_RELEASE="$BATS_TEST_DIRNAME/fixtures/os-release/ubuntu"
    export DEVSHELL_ARCH=x86_64
}
