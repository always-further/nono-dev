"""Connect to a Lima VM."""

import os
import sys

from nono_dev import lima
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser("connect", help="Connect to a VM")
    parser.add_argument(
        "name_pos", nargs="?", default=None,
        metavar="name",
        help=f"VM name (default: auto-select if one exists, else {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "-m", "--name", dest="name_flag", default=None,
        help="VM name (alias for positional)",
    )
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()
    vm = lima.resolve_vm_name(args.name_flag or args.name_pos, DEFAULT_VM_NAME)

    status = lima.vm_status(vm)
    if status != "Running":
        print(f"VM '{vm}' is not running (status: {status}). Starting...")
        lima.start_vm(vm)

    info = lima.sync_info(vm)
    if info:
        host_path, guest_url = info
        print(f"Mount: {host_path} -> {guest_url}")
    else:
        print("Mount: (no active sync)")

    os.execvp("limactl", ["limactl", "shell", vm])
