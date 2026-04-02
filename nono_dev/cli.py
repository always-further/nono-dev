"""CLI entry point with argparse subcommands."""

import argparse
import sys

from nono_dev import __version__
from nono_dev.commands import (
    attach,
    cleanup,
    connect,
    create,
    destroy,
    feature,
    fix,
    prune,
    recreate,
    review,
    sandbox_status,
    stop,
    triage,
    vm_status,
    worktree_cmd,
)


def main():
    parser = argparse.ArgumentParser(
        prog="nono-dev",
        description="Development environment manager for the nono project",
    )
    parser.add_argument(
        "--version", action="version", version=f"nono-dev {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # VM commands
    create.add_parser(subparsers)
    connect.add_parser(subparsers)
    vm_status.add_parser(subparsers)
    destroy.add_parser(subparsers)
    recreate.add_parser(subparsers)

    # Sandbox workflow commands
    triage.add_parser(subparsers)
    fix.add_parser(subparsers)
    review.add_parser(subparsers)
    feature.add_parser(subparsers)
    attach.add_parser(subparsers)
    sandbox_status.add_parser(subparsers)
    stop.add_parser(subparsers)
    cleanup.add_parser(subparsers)
    prune.add_parser(subparsers)
    worktree_cmd.add_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)
