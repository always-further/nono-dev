"""Destroy and recreate a Lima VM."""

from nono_dev import lima
from nono_dev.commands import create


def add_parser(subparsers):
    parser = subparsers.add_parser("recreate", help="Destroy and recreate a VM")
    parser.add_argument(
        "--os", dest="os_name", default="ubuntu",
        choices=("debian", "ubuntu"),
        help="Operating system (default: ubuntu)",
    )
    parser.add_argument("name", nargs="?", default="nono-dev", help="VM name")
    parser.add_argument("--extras", default="", help="Extra apt packages")
    parser.add_argument("--mount", default=None, help="Host directory to sync")
    parser.add_argument("--user", default=None, help="Username in the VM")
    parser.add_argument("--no-rust", action="store_true", help="Skip Rust installation")
    parser.add_argument("--shell-setup", action="store_true", help="Install zsh, starship, tmux, ripgrep, fzf")
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    if lima.vm_exists(args.name):
        print(f"Deleting VM '{args.name}'...")
        lima.stop_sync(args.name)
        lima.stop_vm(args.name)
        lima.delete_vm(args.name)

    create.run(args)
