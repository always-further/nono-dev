"""Delete a Lima VM."""

import sys

from nono_dev import lima
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser("destroy", help="Delete a VM")
    parser.add_argument(
        "name_pos", nargs="?", default=None, metavar="name",
        help=f"VM name (default: auto-select if one exists, else {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "-m", "--name", dest="name_flag", default=None,
        help="VM name (alias for positional)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompt",
    )
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()
    vm = lima.resolve_vm_name(args.name_flag or args.name_pos, DEFAULT_VM_NAME)

    if not args.force:
        confirm = input(
            f"Delete VM '{vm}'? All data will be lost. [y/N] "
        ).strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    lima.stop_sync(vm)
    lima.stop_vm(vm)
    lima.delete_vm(vm)
    print(f"VM '{vm}' deleted.")
