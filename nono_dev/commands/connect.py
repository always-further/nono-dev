"""Connect to a Lima VM."""

import os
import sys

from nono_dev import lima, project_config
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

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    if not lima.vm_exists(args.name, lima_home=lima_home):
        print(f"VM '{args.name}' does not exist.")
        print(f"Create one with: nono-dev vm create")
        sys.exit(1)

    status = lima.vm_status(args.name, lima_home=lima_home)
    if status != "Running":
        print(f"VM '{args.name}' is not running (status: {status}). Starting...")
        lima.start_vm(args.name, lima_home=lima_home)

    if lima_home:
        os.environ["LIMA_HOME"] = lima_home
    os.execvp("limactl", ["limactl", "shell", args.name])
