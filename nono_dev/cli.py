"""CLI entry point with argparse subcommands."""

import argparse
import sys

from nono_dev import __version__
from nono_dev.commands import (
    attach,
    connect,
    create,
    destroy,
    feature,
    fix,
    git_cmd,
    prune,
    recreate,
    review,
    sandbox_status,
    shell_init,
    stop,
    triage,
    vm_status,
    worktree_cmd,
)


def _group_help(parser):
    """Return a function that prints help for a command group."""
    def _help(_args):
        parser.print_help()
        sys.exit(1)
    return _help


def main():
    parser = argparse.ArgumentParser(
        prog="nono-dev",
        description="Development environment manager for the nono project",
    )
    parser.add_argument(
        "--version", action="version", version=f"nono-dev {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Top-level workflow commands
    triage.add_parser(subparsers)
    fix.add_parser(subparsers)
    review.add_parser(subparsers)
    feature.add_parser(subparsers)

    # vm group -- OrbStack VM management
    vm_parser = subparsers.add_parser("vm", help="Manage OrbStack VMs")
    vm_parser.set_defaults(func=_group_help(vm_parser))
    vm_sub = vm_parser.add_subparsers(dest="vm_command")
    create.add_parser(vm_sub)
    connect.add_parser(vm_sub)
    vm_status.add_parser(vm_sub)
    destroy.add_parser(vm_sub)
    recreate.add_parser(vm_sub)

    # sb group -- sandbox session management
    sb_parser = subparsers.add_parser("sb", help="Manage sandbox sessions")
    sb_parser.set_defaults(func=_group_help(sb_parser))
    sb_sub = sb_parser.add_subparsers(dest="sb_command")
    sandbox_status.add_parser(sb_sub)
    attach.add_parser(sb_sub)
    stop.add_parser(sb_sub)
    prune.add_parser(sb_sub)

    # wt group -- worktree management
    worktree_cmd.add_parser(subparsers)

    # git group -- AI-assisted git operations
    git_cmd.add_parser(subparsers)

    # Utilities
    shell_init.add_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)
