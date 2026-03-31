"""Connect to an OrbStack VM."""

import os
import sys

from nono_dev import orbstack
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser("connect", help="Connect to a VM")
    parser.add_argument(
        "name", nargs="?", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.set_defaults(func=run)


def run(args):
    orbstack.check_installed()

    if not orbstack.vm_exists(args.name):
        print(f"VM '{args.name}' does not exist.")
        print(f"Create one with: nono-dev create")
        sys.exit(1)

    user = os.environ.get("USER", "dev")
    home = f"/home/{user}"
    os.execvp("orb", ["orb", "-m", args.name, "-w", home])
