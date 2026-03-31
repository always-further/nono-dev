"""CLI entry point with argparse subcommands."""

import argparse
import sys

from nono_dev import __version__
from nono_dev.commands import connect, create, destroy, recreate, status


def main():
    parser = argparse.ArgumentParser(
        prog="nono-dev",
        description="Development environment manager for the nono project",
    )
    parser.add_argument(
        "--version", action="version", version=f"nono-dev {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")
    create.add_parser(subparsers)
    connect.add_parser(subparsers)
    status.add_parser(subparsers)
    destroy.add_parser(subparsers)
    recreate.add_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)
