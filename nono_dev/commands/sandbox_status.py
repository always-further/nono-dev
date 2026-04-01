"""Dashboard showing worktrees, nono sessions, and change stats."""

import os
import re

from nono_dev import nono, project_config, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "status", help="Show worktree and session status dashboard",
    )
    parser.set_defaults(func=run)


def _parse_session_name(name):
    """Parse a session name into (type, ref, worktree_branch).

    Returns (type_str, ref_str, expected_branch_or_None).
    """
    m = re.match(r"^fix-(\d+)$", name)
    if m:
        return "fix", f"#{m.group(1)}", f"issue-{m.group(1)}"

    m = re.match(r"^triage-(\d+)$", name)
    if m:
        return "triage", f"#{m.group(1)}", None

    m = re.match(r"^review-(\d+)$", name)
    if m:
        return "review", f"#{m.group(1)}", None

    m = re.match(r"^feat-(.+)$", name)
    if m:
        return "feature", m.group(1), m.group(1)

    return "session", "-", None


def _find_worktree(branch, all_worktrees):
    """Find a worktree by branch name."""
    if not branch:
        return None
    for wt in all_worktrees:
        if wt.get("branch") == branch:
            return wt
    return None


def _relative_path(path, project_root):
    """Return a path relative to the project root."""
    try:
        return os.path.relpath(path, project_root)
    except ValueError:
        return path


def run(_args):
    nono.check_installed()
    config = project_config.load()
    wt_dir = project_config.get_worktree_dir(config)
    project_root = config["_config_dir"]

    sessions = nono.ps_json(include_all=False)
    all_worktrees = worktree.list_worktrees(cwd=project_root)

    # Managed worktrees under the configured dir
    abs_wt_dir = os.path.abspath(wt_dir)
    managed_wts = [
        wt for wt in all_worktrees
        if wt.get("path", "").startswith(abs_wt_dir)
    ]

    if not managed_wts and not sessions:
        print("No worktrees or sessions found.")
        return

    # Header
    print(
        f"{'WORKTREE':<30} {'TYPE':<10} {'ISSUE/PR':<12} "
        f"{'SESSION':<10} {'STATUS':<12} {'CHANGES'}"
    )

    # Track which worktree branches have been shown
    shown_branches = set()

    # Show all active sessions
    for s in sessions:
        name = s.get("name", "")
        session_type, ref, expected_branch = _parse_session_name(name)
        session_id = s.get("session_id", "-")[:6]
        status = s.get("status", "?")

        # Find worktree by expected branch name derived from session name
        wt = _find_worktree(expected_branch, all_worktrees)

        if wt:
            wt_display = _relative_path(wt["path"], project_root)
            shown_branches.add(wt.get("branch"))
            if os.path.isdir(wt["path"]):
                adds, dels = worktree.diff_stat(wt["path"])
                changes = f"+{adds} -{dels}"
            else:
                changes = "?"
        else:
            wt_display = "-"
            changes = "-"

        print(
            f"{wt_display:<30} {session_type:<10} {ref:<12} "
            f"{session_id:<10} {status:<12} {changes}"
        )

    # Show managed worktrees without a running session
    for wt in managed_wts:
        branch = wt.get("branch", os.path.basename(wt["path"]))
        if branch in shown_branches:
            continue

        wt_display = _relative_path(wt["path"], project_root)

        m = re.match(r"^issue-(\d+)$", branch)
        if m:
            wt_type, ref = "fix", f"#{m.group(1)}"
        else:
            wt_type, ref = "feature", "-"

        if os.path.isdir(wt["path"]):
            adds, dels = worktree.diff_stat(wt["path"])
            changes = f"+{adds} -{dels}"
        else:
            changes = "?"

        print(
            f"{wt_display:<30} {wt_type:<10} {ref:<12} "
            f"{'-':<10} {'no session':<12} {changes}"
        )
