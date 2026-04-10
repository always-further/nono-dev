"""Cloud-init configuration builder."""

import importlib.resources
import os

from nono_dev.config import MOTD_TEMPLATE


def _read_dotfile(name):
    """Read a dotfile from the shipped dotfiles directory."""
    ref = importlib.resources.files("nono_dev.dotfiles").joinpath(name)
    path = str(ref)
    if os.path.isfile(path):
        with open(path) as f:
            return f.read()
    return ref.read_text(encoding="utf-8")


def build_cloud_init(username, os_name, mount_path=None, shell_setup=False):
    """Build a cloud-init YAML string from the given parameters."""
    default_shell = "/usr/bin/zsh" if shell_setup else "/bin/bash"

    users = [
        {
            "name": username,
            "shell": default_shell,
            "sudo": "ALL=(ALL) NOPASSWD:ALL",
            "groups": "sudo",
        },
    ]

    runcmd = [
        f"mkdir -p /home/{username}/.cargo_target_linux",
        f"chown -R {username}:{username} /home/{username}/.cargo_target_linux",
    ]

    if mount_path:
        mac_path = f"/mnt/mac{mount_path}"
        runcmd.append(f"ln -sf {mac_path} /home/{username}/project")
        runcmd.append(
            f"chown -h {username}:{username} /home/{username}/project"
        )

    motd = MOTD_TEMPLATE.format(os=os_name)

    write_files = [
        {"path": "/etc/motd", "content": motd},
    ]

    config = {
        "users": users,
        "runcmd": runcmd,
        "write_files": write_files,
    }
    return "#cloud-config\n" + _yaml_dump(config)


def _yaml_dump(data, indent=0):
    """Minimal YAML serializer for cloud-init compatible output."""
    lines = []
    prefix = "  " * indent

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_yaml_dump(value, indent + 1))
            elif isinstance(value, bool):
                lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
            else:
                lines.append(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                first = True
                for key, value in item.items():
                    if first:
                        if "\n" in str(value):
                            lines.append(f"{prefix}- {key}: |")
                            for line in str(value).splitlines():
                                lines.append(f"{prefix}    {line}")
                        else:
                            lines.append(f"{prefix}- {key}: {value}")
                        first = False
                    else:
                        if "\n" in str(value):
                            lines.append(f"{prefix}  {key}: |")
                            for line in str(value).splitlines():
                                lines.append(f"{prefix}      {line}")
                        else:
                            lines.append(f"{prefix}  {key}: {value}")
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{data}")

    return "\n".join(lines)
