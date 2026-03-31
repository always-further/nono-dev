"""Create an OrbStack VM with Rust build dependencies."""

import os
import sys
import tempfile

from nono_dev import orbstack, template
from nono_dev.config import BASE_PACKAGES, DEFAULT_OS, DEFAULT_VM_NAME


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

    print(f"""
VM '{args.name}' created successfully.

  Connect:    nono-dev connect
  Project:    ~/project -> /mnt/mac{mount_path}
  SSH Agent:  Forwarded automatically
""")
