"""Lima instance YAML configuration builder."""

import importlib.resources
import os

from nono_dev.config import (
    DEFAULT_CPUS,
    DEFAULT_DISK,
    DEFAULT_MEMORY,
    DISTROS,
    MOTD_TEMPLATE,
)


def _read_dotfile(name):
    """Read a dotfile from the shipped dotfiles directory."""
    ref = importlib.resources.files("nono_dev.dotfiles").joinpath(name)
    path = str(ref)
    if os.path.isfile(path):
        with open(path) as f:
            return f.read()
    return ref.read_text(encoding="utf-8")


def build_lima_config(
    username,
    os_name,
    extra_packages=None,
    install_rust=True,
    shell_setup=False,
    cpus=None,
    memory=None,
    disk=None,
):
    """Build a Lima instance YAML string."""
    cpus = cpus or DEFAULT_CPUS
    memory = memory or DEFAULT_MEMORY
    disk = disk or DEFAULT_DISK

    distro = DISTROS[os_name]

    all_packages = list(distro["base_packages"])
    if extra_packages:
        all_packages.extend(extra_packages)
    if shell_setup:
        all_packages.extend(distro["shell_packages"])

    # -- Build system provision script --
    # Lima auto-creates a user matching the macOS username with home at
    # /home/<user>.guest.  We use that user rather than creating our own.
    system_lines = [
        "#!/bin/bash",
        "set -eux",
        "",
        "# Install packages",
        distro["update_cmd"],
        f"{distro['install_cmd']} {' '.join(all_packages)}",
        "",
        "# MOTD",
        f"cat > /etc/motd << 'MOTD_EOF'",
        MOTD_TEMPLATE.format(os=os_name).rstrip(),
        "MOTD_EOF",
    ]

    if shell_setup:
        system_lines.extend(_shell_setup_system_lines(username, distro))

    system_script = "\n".join(system_lines) + "\n"

    # -- Build user provision script --
    # Runs as Lima's default user (matches macOS username).
    # $HOME is /home/<user>.guest -- all paths use $HOME.
    user_lines = [
        "#!/bin/bash",
        "set -eux",
        "",
        "# Cargo target directory for cross-compilation",
        "mkdir -p $HOME/.cargo_target_linux",
        "",
        "# Project directory (mutagen syncs here)",
        "mkdir -p $HOME/project",
        "",
        "# Cargo target dir in shell profile",
        "cat >> $HOME/.bashrc << 'BASHRC_EOF'",
        "",
        "# Keep Linux cargo builds on local disk, separate from macOS shared mount",
        'export CARGO_TARGET_DIR="$HOME/.cargo_target_linux"',
        "BASHRC_EOF",
    ]

    if install_rust:
        user_lines.extend([
            "",
            "# Install Rust toolchain",
            "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
            "source $HOME/.cargo/env",
            "",
            "# Install cargo-audit",
            "cargo install cargo-audit",
        ])

    user_script = "\n".join(user_lines) + "\n"

    # -- Build the Lima YAML --
    config = {
        "vmType": "vz",
        "vmOpts": {
            "vz": {
                "rosetta": {
                    "enabled": True,
                    "binfmt": True,
                },
            },
        },
        "cpus": cpus,
        "memory": memory,
        "disk": disk,
        "images": _images_for_os(os_name),
        "mounts": [],
        "provision": [
            {"mode": "system", "script": system_script},
            {"mode": "user", "script": user_script},
        ],
    }
    if shell_setup:
        config["user"] = {"shell": "/bin/zsh"}
    return _yaml_dump(config)


def _images_for_os(os_name):
    """Return Lima image entries for the given OS."""
    distro = DISTROS[os_name]
    images = []
    for arch, url in distro["images"].items():
        images.append({"location": url, "arch": arch})
    return images


def _shell_setup_system_lines(username, distro):
    """Return provision script lines for shell tool setup.

    Lima's default user home is /home/<username>.guest.
    System-level tools go to /usr/local, dotfiles go to the user's home.
    """
    home = f"/home/{username}.guest"
    lines = [
        "",
        "# -- Shell setup --",
        "",
        "# Install starship prompt",
        "curl -fsSL https://starship.rs/install.sh | sh -s -- -y",
        "",
        "# Install z (directory jumping)",
        "mkdir -p /usr/local/share/z",
        "curl -fsSL https://raw.githubusercontent.com/rupa/z/master/z.sh "
        "-o /usr/local/share/z/z.sh",
        "",
        "# Install zsh-autosuggestions",
        "mkdir -p /usr/local/share/zsh-autosuggestions",
        "curl -fsSL https://raw.githubusercontent.com/zsh-users/zsh-autosuggestions/master/zsh-autosuggestions.zsh "
        "-o /usr/local/share/zsh-autosuggestions/zsh-autosuggestions.zsh",
    ]

    # eza: only needs extra repo setup on apt-based distros
    if distro["eza_setup"] == "apt":
        lines.extend([
            "",
            "# Install eza",
            "apt-get install -y -qq gpg",
            "mkdir -p /etc/apt/keyrings",
            "curl -fsSL https://raw.githubusercontent.com/eza-community/eza/main/deb.asc "
            "| gpg --dearmor -o /etc/apt/keyrings/gierens.gpg",
            'echo "deb [signed-by=/etc/apt/keyrings/gierens.gpg] '
            'http://deb.gierens.de stable main" '
            "> /etc/apt/sources.list.d/gierens.list",
            "apt-get update -qq",
            "apt-get install -y -qq eza",
        ])
    # For distros with eza in their repos (e.g. Fedora), it's already in shell_packages

    lines.extend([
        "",
        f"# Set default shell to zsh",
        distro["shell_change_cmd"].format(username=username),
        "",
        f"# Deploy dotfiles",
        f"mkdir -p {home}/.config",
    ])

    dotfiles_map = {
        ".zprofile": f"{home}/.zprofile",
        ".zshrc": f"{home}/.zshrc",
        ".direnvrc": f"{home}/.direnvrc",
        ".tmux.conf": f"{home}/.tmux.conf",
        "starship.toml": f"{home}/.config/starship.toml",
    }
    for src_name, dest_path in dotfiles_map.items():
        content = _read_dotfile(src_name)
        lines.extend([
            f"cat > {dest_path} << 'DOTFILE_EOF'",
            content.rstrip(),
            "DOTFILE_EOF",
        ])

    lines.extend([
        f"chown -R {username}:{username} {home}",
    ])
    return lines


def _yaml_dump(data, indent=0):
    """Minimal YAML serializer for Lima config output."""
    lines = []
    prefix = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list) and not value:
                lines.append(f"{prefix}{key}: []")
            elif isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_yaml_dump(value, indent + 1))
            elif isinstance(value, bool):
                lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
            elif isinstance(value, str) and "\n" in value:
                lines.append(f"{prefix}{key}: |")
                for line in value.splitlines():
                    lines.append(f"{prefix}  {line}")
            else:
                lines.append(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                first = True
                for key, value in item.items():
                    if first:
                        if isinstance(value, str) and "\n" in value:
                            lines.append(f"{prefix}- {key}: |")
                            for line in value.splitlines():
                                lines.append(f"{prefix}    {line}")
                        elif isinstance(value, (dict, list)):
                            lines.append(f"{prefix}- {key}:")
                            lines.append(_yaml_dump(value, indent + 2))
                        elif isinstance(value, bool):
                            lines.append(f"{prefix}- {key}: {'true' if value else 'false'}")
                        else:
                            lines.append(f"{prefix}- {key}: {value}")
                        first = False
                    else:
                        if isinstance(value, str) and "\n" in value:
                            lines.append(f"{prefix}  {key}: |")
                            for line in value.splitlines():
                                lines.append(f"{prefix}    {line}")
                        elif isinstance(value, (dict, list)):
                            lines.append(f"{prefix}  {key}:")
                            lines.append(_yaml_dump(value, indent + 2))
                        elif isinstance(value, bool):
                            lines.append(f"{prefix}  {key}: {'true' if value else 'false'}")
                        else:
                            lines.append(f"{prefix}  {key}: {value}")
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{data}")

    return "\n".join(lines)
