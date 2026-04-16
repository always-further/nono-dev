"""Destroy and recreate a Lima VM."""

from nono_dev import lima, project_config
from nono_dev.commands import create
from nono_dev.config import DEFAULT_OS, DEFAULT_VM_NAME, SUPPORTED_OS


def add_parser(subparsers):
    parser = subparsers.add_parser("recreate", help="Destroy and recreate a VM")
    parser.add_argument(
        "--os", dest="os_name", default=DEFAULT_OS,
        choices=SUPPORTED_OS,
        help=f"Operating system (default: {DEFAULT_OS})",
    )
    parser.add_argument("name", nargs="?", default=DEFAULT_VM_NAME, help="VM name")
    parser.add_argument("--extras", default="", help="Extra packages")
    parser.add_argument("--mount", default=None, help="Host directory to sync")
    parser.add_argument("--user", default=None, help="Username in the VM")
    parser.add_argument("--no-rust", action="store_true", help="Skip Rust installation")
    parser.add_argument("--shell-setup", action="store_true", help="Install zsh, starship, tmux, ripgrep, fzf")
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    if lima.vm_exists(args.name, lima_home=lima_home):
        print(f"Deleting VM '{args.name}'...")
        lima.stop_sync(args.name)
        lima.stop_vm(args.name, lima_home=lima_home)
        lima.delete_vm(args.name, lima_home=lima_home)

    create.run(args)
