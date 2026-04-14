"""Create a Lima VM with Rust build dependencies."""

import os
import sys
import tempfile

from nono_dev import lima, template
from nono_dev.config import DEFAULT_OS, DEFAULT_VM_NAME, SUPPORTED_OS


def add_parser(subparsers):
    parser = subparsers.add_parser("create", help="Create a development VM")
    parser.add_argument(
        "--os", dest="os_name", default=DEFAULT_OS,
        choices=SUPPORTED_OS,
        help=f"Operating system (default: {DEFAULT_OS})",
    )
    parser.add_argument(
        "name", nargs="?", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "--extras", default="",
        help="Comma-separated list of additional packages",
    )
    parser.add_argument(
        "--mount", default=None,
        help="Host directory to sync into the VM (default: current directory)",
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
    lima.check_installed()
    lima.check_mutagen_installed()

    username = args.user or os.environ.get("USER", "dev")
    mount_path = os.path.abspath(args.mount) if args.mount else os.getcwd()
    extra_packages = [p.strip() for p in args.extras.split(",") if p.strip()]

    if lima.vm_exists(args.name):
        print(f"VM '{args.name}' already exists.")
        choice = input("[r]ecreate / [c]onnect / [a]bort? ").strip().lower()
        if choice == "c":
            os.execvp("limactl", ["limactl", "shell", args.name])
        elif choice == "r":
            print(f"Deleting VM '{args.name}'...")
            lima.stop_sync(args.name)
            lima.stop_vm(args.name)
            lima.delete_vm(args.name)
        else:
            print("Aborted.")
            sys.exit(0)

    lima_config = template.build_lima_config(
        username=username,
        os_name=args.os_name,
        extra_packages=extra_packages,
        install_rust=not args.no_rust,
        shell_setup=args.shell_setup,
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False,
    ) as f:
        f.write(lima_config)
        config_path = f.name

    try:
        print(f"Creating VM '{args.name}' ({args.os_name})...")
        lima.create_vm(args.name, config_path)
    finally:
        os.unlink(config_path)

    print(f"Starting VM '{args.name}'...")
    lima.start_vm(args.name)

    guest_project = f"/home/{username}.guest/project"

    print("Starting mutagen sync...")
    lima.start_sync(args.name, mount_path, guest_project)

    print(f"""
VM '{args.name}' created successfully.

  Connect:    nono-dev vm connect
  Project:    ~/project (synced from {mount_path})
  Sync:       mutagen (continuous)
""")
