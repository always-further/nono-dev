"""Connect to a Lima VM."""

import os

from nono_dev import lima, project_config
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

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    vm = lima.resolve_vm_name(args.name_flag or args.name_pos, DEFAULT_VM_NAME, lima_home=lima_home)

    status = lima.vm_status(vm, lima_home=lima_home)
    if status != "Running":
        print(f"VM '{vm}' is not running (status: {status}). Starting...")
        lima.start_vm(vm, lima_home=lima_home)

    info = lima.sync_info(vm, lima_home=lima_home)
    if info:
        host_path, guest_url = info
        print(f"Mount: {host_path} -> {guest_url}")
    else:
        print("Mount: (no active sync)")

    if lima_home:
        os.environ["LIMA_HOME"] = lima_home
    # Launch the user's login shell inside the VM (upstream) using the
    # resolved `vm` name rather than the raw arg (ours).
    os.execvp(
        "limactl",
        [
            "limactl",
            "shell",
            vm,
            "sh",
            "-lc",
            'shell="$(getent passwd "$USER" | cut -d: -f7)"; exec "${shell:-/bin/bash}" -l',
        ],
    )
