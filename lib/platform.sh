# shellcheck shell=bash
# os-release contém dados; nunca é executado como código.
detect_platform() {
    local key value id=unknown like='' arch adapter=manual libc=unknown
    while IFS='=' read -r key value; do
        value=${value%\"}
        value=${value#\"}
        value=${value%\'}
        value=${value#\'}
        case "$key" in
            ID) [[ "$value" =~ ^[a-zA-Z0-9._-]+$ ]] && id=$value ;;
            ID_LIKE) [[ "$value" =~ ^[a-zA-Z0-9._\ -]+$ ]] && like=$value ;;
        esac
    done <"${DEVSHELL_OS_RELEASE:-/etc/os-release}"
    case " $id $like " in
        *' debian '* | *' ubuntu '*) adapter=apt ;;
        *' fedora '* | *' rhel '*) adapter=dnf ;;
        *' arch '*) adapter=pacman ;;
        *' opensuse '* | *' opensuse-leap '* | *' opensuse-tumbleweed '* | *' suse '*) adapter=zypper ;;
    esac
    arch=${DEVSHELL_ARCH:-$(uname -m)}
    case "$arch" in amd64) arch=x86_64 ;; arm64) arch=aarch64 ;; esac
    if getconf GNU_LIBC_VERSION >/dev/null 2>&1; then
        libc=gnu
    elif ldd --version 2>&1 | grep -qi musl; then
        libc=musl
    fi
    export DEVSHELL_DISTRO="$id" DEVSHELL_ADAPTER="$adapter" DEVSHELL_MACHINE="$arch" DEVSHELL_LIBC="$libc"
}
