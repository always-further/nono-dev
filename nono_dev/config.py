"""Default configuration and constants."""

DEFAULT_VM_NAME = "nono-dev"
DEFAULT_OS = "fedora"

DEFAULT_CPUS = 4
DEFAULT_MEMORY = "8GiB"
DEFAULT_DISK = "20GiB"

# Per-distro configuration: package manager commands, packages, images, shell setup.
# To add a new distro, add an entry here -- template.py reads from this registry.
DISTROS = {
    "fedora": {
        "update_cmd": "dnf check-update -q || true",
        "install_cmd": "dnf install -y -q",
        "images": {
            "x86_64": "https://download.fedoraproject.org/pub/fedora/linux/releases/43/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-43-1.6.x86_64.qcow2",
            "aarch64": "https://download.fedoraproject.org/pub/fedora/linux/releases/43/Cloud/aarch64/images/Fedora-Cloud-Base-Generic-43-1.6.aarch64.qcow2",
        },
        "base_packages": [
            "gcc", "gcc-c++", "make", "pkg-config",
            "openssl-devel", "dbus-devel", "cmake", "perl", "git", "curl",
            "jq", "npm",
        ],
        "shell_packages": [
            "zsh", "tmux", "ripgrep", "bat", "fd-find", "direnv", "fzf", "eza",
        ],
        "shell_change_cmd": "usermod -s /usr/bin/zsh {username}",
        "eza_setup": None,
    },
    "ubuntu": {
        "update_cmd": "apt-get update -qq",
        "install_cmd": "apt-get install -y -qq",
        "images": {
            "x86_64": "https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img",
            "aarch64": "https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-arm64.img",
        },
        "base_packages": [
            "build-essential", "pkg-config", "libssl-dev",
            "libdbus-1-dev", "cmake", "perl", "git", "curl",
            "jq", "npm",
        ],
        "shell_packages": [
            "zsh", "tmux", "ripgrep", "bat", "fd-find", "direnv", "fzf",
        ],
        "shell_change_cmd": "chsh -s /usr/bin/zsh {username}",
        "eza_setup": "apt",
    },
    "debian": {
        "update_cmd": "apt-get update -qq",
        "install_cmd": "apt-get install -y -qq",
        "images": {
            "x86_64": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2",
            "aarch64": "https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-arm64.qcow2",
        },
        "base_packages": [
            "build-essential", "pkg-config", "libssl-dev",
            "libdbus-1-dev", "cmake", "perl", "git", "curl",
            "jq", "npm",
        ],
        "shell_packages": [
            "zsh", "tmux", "ripgrep", "bat", "fd-find", "direnv", "fzf",
        ],
        "shell_change_cmd": "chsh -s /usr/bin/zsh {username}",
        "eza_setup": "apt",
    },
}

SUPPORTED_OS = tuple(DISTROS.keys())

MOTD_TEMPLATE = """\
--------------------------------------------------
Nono Development Environment ({os})
Project:      ~/project
Cargo target: ~/.cargo_target_linux (interactive)
--------------------------------------------------
"""
