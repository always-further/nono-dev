"""CLI entry point with argparse subcommands."""

import argparse
import sys

from nono_dev import __version__, style
from nono_dev.commands import (
    attach,
    bare,
    connect,
    create,
    destroy,
    dotfiles,
    feature,
    fix,
    git_cmd,
    inspect_cmd,
    install,
    mount,
    prune,
    recreate,
    review,
    sandbox_status,
    shell_init,
    stop,
    triage,
    vm_list,
    vm_shutdown,
    vm_status,
    worktree_cmd,
)


def _print_main_help():
    """Print styled main help."""
    print()
    print(style.banner("  nono-dev") + style.muted(f"  v{__version__}"))
    print(style.dim("  Development environment and sandboxed workflow manager"))
    print()

    print(style.header("  Workflow Commands"))
    _help_row("triage", "<issue>", "Triage a GitHub issue with a sandboxed agent")
    _help_row("fix", "<issue>", "Fix a GitHub issue in a sandboxed worktree")
    _help_row("review", "<pr>", "Review a GitHub PR with a sandboxed agent")
    _help_row("feature", "<branch>", "Start a new feature in a sandboxed worktree")
    _help_row("bare", "[name]", "Start a sandboxed Claude session in the current checkout")
    print()

    print(style.header("  Session Management") + style.dim("  (nono-dev sb ...)"))
    _help_row("sb list", "", "Show session and worktree dashboard")
    _help_row("sb inspect", "<target>", "Show detailed session and worktree info")
    _help_row("sb attach", "<target>", "Attach to a running session")
    _help_row("sb stop", "<target>", "Stop a running session")
    _help_row("sb prune", "", "Clean up old session files")
    print()

    print(style.header("  Worktree Management") + style.dim("  (nono-dev wt ...)"))
    _help_row("wt list", "", "List managed worktrees")
    _help_row("wt cd", "<name>", "Open a shell in a worktree")
    _help_row("wt cleanup", "<name|--all>", "Remove worktrees and branches")
    print()

    print(style.header("  Git Operations") + style.dim("  (nono-dev git ...)"))
    _help_row("git commit", "", "AI-generated conventional commit")
    print()

    print(style.header("  VM Management") + style.dim("  (nono-dev vm ...)"))
    _help_row("vm create", "[name]", "Create a development VM")
    _help_row("vm connect", "[name]", "Connect to a VM")
    _help_row("vm list", "", "List VMs")
    _help_row("vm status", "", "Show VM status")
    _help_row("vm shutdown", "[name]", "Shutdown a VM")
    _help_row("vm mount", "[path]", "Show or switch the synced project directory")
    _help_row("vm destroy", "[name]", "Delete a VM")
    _help_row("vm recreate", "[name]", "Destroy and recreate a VM")
    print()

    print(style.header("  Utilities"))
    _help_row("install", "[--force]", "Install nono-dev globally via uv tool")
    _help_row("shell-init", "", "Print shell functions for .zshrc")
    _help_row("dotfiles", "[--force]", "Deploy shipped dotfiles to local machine")
    print()

    print(style.dim("  Run ") + style.info("nono-dev <command> --help") + style.dim(" for details"))
    print()


def _help_row(cmd, args, desc):
    """Print a styled help row."""
    cmd_str = style.value(cmd)
    args_str = style.muted(args) if args else ""
    full_cmd = f"{cmd_str} {args_str}".ljust(45 + 20)  # pad accounting for ANSI codes
    print(f"    {full_cmd}{style.dim(desc)}")


def _print_group_help(group_name, commands):
    """Return a function that prints styled group help."""
    def _help(_args):
        print()
        print(style.banner(f"  nono-dev {group_name}"))
        print()
        for cmd, args, desc in commands:
            _help_row(f"{group_name} {cmd}", args, desc)
        print()
        sys.exit(0)
    return _help


def main():
    # Handle --complete before argparse to avoid interference
    if "--complete" in sys.argv:
        from nono_dev.completions import get_completions
        idx = sys.argv.index("--complete")
        words = sys.argv[idx + 1:]
        for c in get_completions(words):
            print(c)
        sys.exit(0)

    parser = argparse.ArgumentParser(
        prog="nono-dev",
        description="Development environment manager for the nono project",
        add_help=False,
    )
    parser.add_argument(
        "--version", action="version", version=f"nono-dev {__version__}",
    )
    parser.add_argument(
        "-h", "--help", action="store_true", dest="show_help",
    )

    subparsers = parser.add_subparsers(dest="command")

    # Top-level workflow commands
    triage.add_parser(subparsers)
    fix.add_parser(subparsers)
    review.add_parser(subparsers)
    feature.add_parser(subparsers)
    bare.add_parser(subparsers)

    # vm group
    vm_parser = subparsers.add_parser("vm", help="Manage Lima VMs")
    vm_parser.set_defaults(func=_print_group_help("vm", [
        ("create", "[name]", "Create a development VM"),
        ("connect", "[name]", "Connect to a VM"),
        ("list", "", "List VMs"),
        ("status", "", "Show VM status"),
        ("shutdown", "[name]", "Shutdown a VM"),
        ("mount", "[path]", "Show or switch the synced project directory"),
        ("destroy", "[name]", "Delete a VM"),
        ("recreate", "[name]", "Destroy and recreate a VM"),
    ]))
    vm_sub = vm_parser.add_subparsers(dest="vm_command")
    create.add_parser(vm_sub)
    connect.add_parser(vm_sub)
    vm_list.add_parser(vm_sub)
    vm_status.add_parser(vm_sub)
    vm_shutdown.add_parser(vm_sub)
    mount.add_parser(vm_sub)
    destroy.add_parser(vm_sub)
    recreate.add_parser(vm_sub)

    # sb group
    sb_parser = subparsers.add_parser("sb", help="Manage sandbox sessions")
    sb_parser.set_defaults(func=_print_group_help("sb", [
        ("list", "", "Show session and worktree dashboard"),
        ("inspect", "<target>", "Show detailed session and worktree info"),
        ("attach", "<target>", "Attach to a running session"),
        ("stop", "<target>", "Stop a running session"),
        ("prune", "", "Clean up old session files"),
    ]))
    sb_sub = sb_parser.add_subparsers(dest="sb_command")
    sandbox_status.add_parser(sb_sub)
    inspect_cmd.add_parser(sb_sub)
    attach.add_parser(sb_sub)
    stop.add_parser(sb_sub)
    prune.add_parser(sb_sub)

    # wt group
    worktree_cmd.add_parser(subparsers)

    # git group
    git_cmd.add_parser(subparsers)

    # Utilities
    install.add_parser(subparsers)
    shell_init.add_parser(subparsers)
    dotfiles.add_parser(subparsers)

    args = parser.parse_args()

    if args.show_help or not args.command:
        _print_main_help()
        sys.exit(0)

    args.func(args)
