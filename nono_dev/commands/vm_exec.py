"""Execute a command in a Lima VM via SSH."""

import shlex
import subprocess
import sys

from nono_dev import lima
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "exec", help="Run a command in a VM via SSH",
    )
    parser.add_argument(
        "-m", "--name", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
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
    if not lima.vm_exists(args.name):
        print(f"VM '{args.name}' does not exist.", file=sys.stderr)
        print(f"Create one with: nd vm create {args.name}", file=sys.stderr)
        sys.exit(1)

    if lima.vm_status(args.name) != "Running":
        print(f"VM '{args.name}' is not running.", file=sys.stderr)
        sys.exit(1)

    quoted = " ".join(shlex.quote(c) for c in args.command)
    remote = f"cd {shlex.quote(args.cwd)} && {quoted}"

    result = subprocess.run(["ssh", f"lima-{args.name}", remote])
    sys.exit(result.returncode)
