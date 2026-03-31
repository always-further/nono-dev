"""Cloud-init configuration builder."""

from nono_dev.config import MOTD_TEMPLATE


def build_cloud_init(username, os_name, mount_path=None):
    """Build a cloud-init YAML string from the given parameters."""
    users = [
        {
            "name": username,
            "shell": "/bin/bash",
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

    cargo_config = (
        "[build]\n"
        f'target-dir = "/home/{username}/.cargo_target_linux"\n'
    )

    config = {
        "users": users,
        "runcmd": runcmd,
        "write_files": [
            {"path": "/etc/motd", "content": motd},
            {
                "path": f"/home/{username}/.cargo/config.toml",
                "owner": f"{username}:{username}",
                "content": cargo_config,
            },
        ],
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
