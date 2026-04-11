"""Default configuration and constants."""

DEFAULT_VM_NAME = "nono-dev"
DEFAULT_OS = "ubuntu"
SUPPORTED_OS = ("debian", "ubuntu")

DEFAULT_CPUS = 4
DEFAULT_MEMORY = "8GiB"
DEFAULT_DISK = "20GiB"

BASE_PACKAGES = [
    "build-essential",
    "pkg-config",
    "libssl-dev",
    "libdbus-1-dev",
    "cmake",
    "perl",
    "git",
    "curl",
]

SHELL_PACKAGES = [
    "zsh",
    "tmux",
    "ripgrep",
    "bat",
    "fd-find",
    "direnv",
    "fzf",
]

MOTD_TEMPLATE = """\
--------------------------------------------------
Nono Development Environment ({os})
Project:      ~/project
Cargo target: ~/.cargo_target_linux (interactive)
--------------------------------------------------
"""
