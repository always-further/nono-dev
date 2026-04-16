"""Destroy and recreate a Lima VM."""

from nono_dev import lima, project_config
from nono_dev.commands import create
from nono_dev.config import (
    DEFAULT_CPUS,
    DEFAULT_DISK,
    DEFAULT_MEMORY,
    DEFAULT_OS,
    DEFAULT_VM_NAME,
    SUPPORTED_OS,
)


def add_parser(subparsers):
    parser = subparsers.add_parser("recreate", help="Destroy and recreate a VM")
    parser.add_argument(
        "--os", dest="os_name", default=DEFAULT_OS,
        choices=SUPPORTED_OS,
        help=f"Operating system (default: {DEFAULT_OS})",
    )
    parser.add_argument(
        "name_pos", nargs="?", default=None, metavar="name",
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "-m", "--name", dest="name_flag", default=None,
        help="VM name (alias for positional)",
    )
    parser.add_argument("--extras", default="", help="Extra packages")
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

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    # recreate must bootstrap from nothing, so it does not use resolve_vm_name
    # (which fails closed when no VMs exist). Fall back to DEFAULT_VM_NAME
    # instead of auto-selecting a sole VM — picking "the other VM" to recreate
    # would be destructive and surprising.
    vm = args.name_flag or args.name_pos or DEFAULT_VM_NAME

    if lima.vm_exists(vm, lima_home=lima_home):
        # Preserve the existing mount unless --mount was given explicitly,
        # so that recreate doesn't silently retarget the VM at whatever
        # directory the user happens to be in.
        if args.mount is None:
            existing = lima.sync_info(vm, lima_home=lima_home)
            if existing:
                args.mount = existing[0]

        print(f"Deleting VM '{vm}'...")
        lima.stop_sync(vm, lima_home=lima_home)
        lima.stop_vm(vm, lima_home=lima_home)
        lima.delete_vm(vm, lima_home=lima_home)

    # create.run() reads args.name
    args.name = vm
    create.run(args)
