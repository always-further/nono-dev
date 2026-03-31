"""Default configuration and constants."""

DEFAULT_VM_NAME = "nono-dev"
DEFAULT_OS = "debian"
SUPPORTED_OS = ("debian", "ubuntu")

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

MOTD_TEMPLATE = """\
--------------------------------------------------
Nono Development Environment ({os})
Project:      ~/project
Cargo config: ~/.cargo/config.toml
--------------------------------------------------
"""
