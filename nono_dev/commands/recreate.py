"""Destroy and recreate a Lima VM."""

from nono_dev import lima
from nono_dev.commands import create
from nono_dev.config import DEFAULT_CPUS, DEFAULT_DISK, DEFAULT_MEMORY, DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser("recreate", help="Destroy and recreate a VM")
    parser.add_argument(
        "--os", dest="os_name", default="ubuntu",
        choices=("debian", "ubuntu"),
        help="Operating system (default: ubuntu)",
    )
    parser.add_argument(
        "name_pos", nargs="?", default=None, metavar="name",
        help=f"VM name (default: auto-select if one exists, else {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "-m", "--name", dest="name_flag", default=None,
        help="VM name (alias for positional)",
    )
    parser.add_argument("--extras", default="", help="Extra apt packages")
    parser.add_argument("--mount", default=None, help="Host directory to sync")
    parser.add_argument("--user", default=None, help="Username in the VM")
    parser.add_argument("--no-rust", action="store_true", help="Skip Rust installation")
    parser.add_argument("--shell-setup", action="store_true", help="Install zsh, starship, tmux, ripgrep, fzf")
    parser.add_argument("--disk", default=DEFAULT_DISK, help=f"VM disk size (default: {DEFAULT_DISK})")
    parser.add_argument("--cpus", type=int, default=DEFAULT_CPUS, help=f"VM CPU count (default: {DEFAULT_CPUS})")
    parser.add_argument("--memory", default=DEFAULT_MEMORY, help=f"VM memory (default: {DEFAULT_MEMORY})")
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    # recreate must bootstrap from nothing, so it does not use resolve_vm_name
    # (which fails closed when no VMs exist). Fall back to DEFAULT_VM_NAME
    # instead of auto-selecting a sole VM — picking "the other VM" to recreate
    # would be destructive and surprising.
    vm = args.name_flag or args.name_pos or DEFAULT_VM_NAME

    if lima.vm_exists(vm):
        print(f"Deleting VM '{vm}'...")
        lima.stop_sync(vm)
        lima.stop_vm(vm)
        lima.delete_vm(vm)

    # create.run() reads args.name
    args.name = vm
    create.run(args)
