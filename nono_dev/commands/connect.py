"""Connect to a Lima VM."""

import os
import sys

from nono_dev import lima
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser("connect", help="Connect to a VM")
    parser.add_argument(
        "name", nargs="?", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    if not lima.vm_exists(args.name):
        print(f"VM '{args.name}' does not exist.")
        print(f"Create one with: nono-dev vm create")
        sys.exit(1)

    status = lima.vm_status(args.name)
    if status != "Running":
        print(f"VM '{args.name}' is not running (status: {status}). Starting...")
        lima.start_vm(args.name)

    info = lima.sync_info(args.name)
    if info:
        host_path, guest_url = info
        print(f"Mount: {host_path} -> {guest_url}")
    else:
        print("Mount: (no active sync)")

    os.execvp("limactl", ["limactl", "shell", args.name])
