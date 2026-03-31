"""Destroy and recreate an OrbStack VM."""

from nono_dev import orbstack
from nono_dev.commands import create


def add_parser(subparsers):
    parser = subparsers.add_parser("recreate", help="Destroy and recreate a VM")
    parser.add_argument(
        "--os", dest="os_name", default="debian",
        choices=("debian", "ubuntu"),
        help="Operating system (default: debian)",
    )
    parser.add_argument("name", nargs="?", default="nono-dev", help="VM name")
    parser.add_argument("--extras", default="", help="Extra apt packages")
    parser.add_argument("--mount", default=None, help="Host directory to mount")
    parser.add_argument("--user", default=None, help="Username in the VM")
    parser.add_argument("--no-rust", action="store_true", help="Skip Rust installation")
    parser.set_defaults(func=run)


def run(args):
    orbstack.check_installed()

    if orbstack.vm_exists(args.name):
        print(f"Deleting VM '{args.name}'...")
        orbstack.delete_vm(args.name)

    create.run(args)
