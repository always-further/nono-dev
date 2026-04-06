"""Create an OrbStack VM with Rust build dependencies."""

import importlib.resources
import os
import sys
import tempfile

from nono_dev import orbstack, template
from nono_dev.config import BASE_PACKAGES, DEFAULT_OS, DEFAULT_VM_NAME, SHELL_PACKAGES


def _write_file_in_vm(vm_name, dest_path, content, owner):
    """Write a file into the VM using a base64-encoded transfer."""
    import base64
    encoded = base64.b64encode(content.encode()).decode()
    orbstack.run_in_vm(
        vm_name,
        f"echo '{encoded}' | base64 -d > {dest_path} && "
        f"chown {owner}:{owner} {dest_path}",
    )


def add_parser(subparsers):
    parser = subparsers.add_parser("create", help="Create a development VM")
    parser.add_argument(
        "--os", dest="os_name", default=DEFAULT_OS,
        choices=("debian", "ubuntu"),
        help=f"Operating system (default: {DEFAULT_OS})",
    )
    parser.add_argument(
        "name", nargs="?", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "--extras", default="",
        help="Comma-separated list of additional apt packages",
    )
    parser.add_argument(
        "--mount", default=None,
        help="Host directory to mount (default: current directory)",
    )
    parser.add_argument(
        "--user", default=None,
        help="Username in the VM (default: current macOS user)",
    )
    parser.add_argument(
        "--no-rust", action="store_true",
        help="Skip Rust/Cargo installation",
    )
    parser.add_argument(
        "--shell-setup", action="store_true",
        help="Install zsh, starship, tmux, ripgrep, fzf, zsh-autosuggestions and configure dotfiles",
    )
    parser.set_defaults(func=run)


def run(args):
    orbstack.check_installed()

    username = args.user or os.environ.get("USER", "dev")
    mount_path = os.path.abspath(args.mount) if args.mount else os.getcwd()
    extra_packages = [p.strip() for p in args.extras.split(",") if p.strip()]

    if orbstack.vm_exists(args.name):
        print(f"VM '{args.name}' already exists.")
        choice = input("[r]ecreate / [c]onnect / [a]bort? ").strip().lower()
        if choice == "c":
            os.execvp("orb", ["orb", "-m", args.name, "-w", f"/home/{username}"])
        elif choice == "r":
            print(f"Deleting VM '{args.name}'...")
            orbstack.delete_vm(args.name)
        else:
            print("Aborted.")
            sys.exit(0)

    cloud_init = template.build_cloud_init(
        username=username,
        os_name=args.os_name,
        mount_path=mount_path,
        shell_setup=args.shell_setup,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False,
    ) as f:
        f.write(cloud_init)
        cloud_init_path = f.name

    try:
        print(f"Creating VM '{args.name}' ({args.os_name})...")
        orbstack.create_vm(args.os_name, args.name, cloud_init_path)
    finally:
        os.unlink(cloud_init_path)

    all_packages = list(BASE_PACKAGES) + extra_packages
    if args.shell_setup:
        all_packages.extend(SHELL_PACKAGES)
    pkg_list = " ".join(all_packages)

    print("Waiting for apt to be available...")
    orbstack.run_in_vm(
        args.name,
        "while fuser /var/lib/apt/lists/lock /var/lib/dpkg/lock "
        "/var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 1; done",
    )

    print(f"Installing packages...")
    orbstack.run_in_vm(
        args.name,
        f"apt-get update -qq && apt-get install -y -qq {pkg_list}",
    )

    print("Setting up home directory...")
    orbstack.run_in_vm(
        args.name,
        f"mkdir -p /home/{username} && "
        f"chown -R {username}:{username} /home/{username}",
    )

    if not args.no_rust:
        print("Installing Rust toolchain...")
        orbstack.run_in_vm_as_user(
            args.name, username,
            "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs "
            "| sh -s -- -y",
        )

        print("Installing cargo-audit...")
        orbstack.run_in_vm_as_user(
            args.name, username,
            "source ~/.cargo/env && cargo install cargo-audit",
        )

    if args.shell_setup:
        print("Installing starship prompt...")
        orbstack.run_in_vm(
            args.name,
            "curl -fsSL https://starship.rs/install.sh | sh -s -- -y",
        )

        print("Installing z (directory jumping)...")
        orbstack.run_in_vm(
            args.name,
            "mkdir -p /usr/local/share/z && "
            "curl -fsSL https://raw.githubusercontent.com/rupa/z/master/z.sh "
            "-o /usr/local/share/z/z.sh",
        )

        print("Installing zsh-autosuggestions...")
        orbstack.run_in_vm(
            args.name,
            "mkdir -p /usr/local/share/zsh-autosuggestions && "
            "curl -fsSL https://raw.githubusercontent.com/zsh-users/zsh-autosuggestions/master/zsh-autosuggestions.zsh "
            "-o /usr/local/share/zsh-autosuggestions/zsh-autosuggestions.zsh",
        )

        print("Installing eza...")
        orbstack.run_in_vm(
            args.name,
            "apt-get install -y -qq gpg && "
            "mkdir -p /etc/apt/keyrings && "
            "curl -fsSL https://raw.githubusercontent.com/eza-community/eza/main/deb.asc "
            "| gpg --dearmor -o /etc/apt/keyrings/gierens.gpg && "
            'echo "deb [signed-by=/etc/apt/keyrings/gierens.gpg] '
            'http://deb.gierens.de stable main" '
            "> /etc/apt/sources.list.d/gierens.list && "
            "apt-get update -qq && "
            "apt-get install -y -qq eza",
        )

        print("Setting default shell to zsh...")
        orbstack.run_in_vm(
            args.name,
            f"chsh -s /usr/bin/zsh {username}",
        )

        print("Deploying dotfiles...")
        orbstack.run_in_vm(
            args.name,
            f"mkdir -p /home/{username}/.config",
        )

        dotfiles_map = {
            ".zprofile": f"/home/{username}/.zprofile",
            ".zshrc": f"/home/{username}/.zshrc",
            ".tmux.conf": f"/home/{username}/.tmux.conf",
            "starship.toml": f"/home/{username}/.config/starship.toml",
        }
        for src_name, dest_path in dotfiles_map.items():
            ref = importlib.resources.files("nono_dev.dotfiles").joinpath(src_name)
            content = ref.read_text(encoding="utf-8")
            _write_file_in_vm(args.name, dest_path, content, username)

        orbstack.run_in_vm(
            args.name,
            f"chown -R {username}:{username} /home/{username}",
        )

    print(f"""
VM '{args.name}' created successfully.

  Connect:    nono-dev connect
  Project:    ~/project -> /mnt/mac{mount_path}
  SSH Agent:  Forwarded automatically
""")
