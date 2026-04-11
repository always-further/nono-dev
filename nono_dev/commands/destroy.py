"""Delete a Lima VM."""

import sys

from nono_dev import lima
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser("destroy", help="Delete a VM")
    parser.add_argument(
        "name", nargs="?", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompt",
    )
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    if not lima.vm_exists(args.name):
        print(f"VM '{args.name}' does not exist.")
        sys.exit(1)

    if not args.force:
        confirm = input(
            f"Delete VM '{args.name}'? All data will be lost. [y/N] "
        ).strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    lima.stop_sync(args.name)
    lima.stop_vm(args.name)
    lima.delete_vm(args.name)
    print(f"VM '{args.name}' deleted.")
