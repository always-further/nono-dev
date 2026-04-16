"""Execute a command in a Lima VM via SSH."""

import os
import shlex
import subprocess
import sys

from nono_dev import lima, project_config
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "exec", help="Run a command in a VM via SSH",
    )
    parser.add_argument(
        "-m", "--name", default=None,
        help=f"VM name (default: auto-select if one exists, else {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "--cwd", default="~/project",
        help="Working directory in the VM (default: ~/project)",
    )
    parser.add_argument(
        "command", nargs="+",
        help="Command and arguments to execute",
    )
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    vm = lima.resolve_vm_name(args.name, DEFAULT_VM_NAME, lima_home=lima_home)

    if lima.vm_status(vm, lima_home=lima_home) != "Running":
        print(f"VM '{vm}' is not running.", file=sys.stderr)
        sys.exit(1)

    ssh_config = lima.ssh_config_path(vm, lima_home=lima_home)
    if not os.path.isfile(ssh_config):
        print(
            f"Error: Lima SSH config not found at {ssh_config}. "
            f"Start the VM with 'nd vm connect -m {vm}' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    quoted = " ".join(shlex.quote(c) for c in args.command)
    remote = f"cd {shlex.quote(args.cwd)} && {quoted}"

    result = subprocess.run(lima.ssh_argv(vm, remote, lima_home=lima_home))
    sys.exit(result.returncode)
