"""Shutdown a Lima VM."""

import sys

from nono_dev import lima, project_config
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "shutdown",
        aliases=["stop"],
        help="Shutdown a VM",
    )
    parser.add_argument(
        "name", nargs="?", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force stop the VM",
    )
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    if not lima.vm_exists(args.name, lima_home=lima_home):
        print(f"VM '{args.name}' does not exist.")
        sys.exit(1)

    print(f"Stopping sync for VM '{args.name}'...")
    lima.stop_sync(args.name)

    status = lima.vm_status(args.name, lima_home=lima_home)
    if status == "Stopped":
        print(f"VM '{args.name}' is already stopped.")
        return

    print(f"Shutting down VM '{args.name}'...")
    if args.force:
        lima.force_stop_vm(args.name, lima_home=lima_home)
    else:
        lima.stop_vm(args.name, lima_home=lima_home)

    status = lima.vm_status(args.name, lima_home=lima_home)
    if status != "Stopped":
        print(f"VM '{args.name}' did not stop cleanly (status: {status}).")
        sys.exit(1)

    print(f"VM '{args.name}' stopped.")
