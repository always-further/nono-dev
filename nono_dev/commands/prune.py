"""Clean up old nono session files."""

import subprocess
import sys

from nono_dev import nono


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "prune", help="Clean up old nono session files",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be removed without deleting",
    )
    parser.add_argument(
        "--older-than", type=int, metavar="DAYS",
        help="Remove sessions older than N days",
    )
    parser.add_argument(
        "--keep", type=int, metavar="N",
        help="Keep only the N most recent sessions",
    )
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()

    cmd = ["nono", "prune"]

    if args.dry_run:
        cmd.append("--dry-run")
    if args.older_than is not None:
        cmd.extend(["--older-than", str(args.older_than)])
    if args.keep is not None:
        cmd.extend(["--keep", str(args.keep)])

    result = subprocess.run(cmd)
    sys.exit(result.returncode)
