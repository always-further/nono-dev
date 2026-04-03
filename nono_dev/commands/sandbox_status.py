"""Dashboard showing worktrees, nono sessions, and change stats."""

import os
import re
import time

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


def _relative_path(path, base):
    """Return a path relative to base, or the original if not under base."""
    try:
        rel = os.path.relpath(path, base)
        if rel.startswith(".."):
            return path
        return rel
    except ValueError:
        return path


def _format_uptime(started_epoch):
    """Format an epoch timestamp as a human-readable age."""
    if not started_epoch:
        return "-"
    # started_epoch from nono is in microseconds
    started_sec = started_epoch / 1_000_000
    elapsed = time.time() - started_sec
    if elapsed < 0:
        return "-"
    if elapsed < 60:
        return f"{int(elapsed)}s"
    if elapsed < 3600:
        return f"{int(elapsed / 60)}m"
    if elapsed < 86400:
        hours = int(elapsed / 3600)
        mins = int((elapsed % 3600) / 60)
        return f"{hours}h{mins}m"
    days = int(elapsed / 86400)
    hours = int((elapsed % 86400) / 3600)
    return f"{days}d{hours}h"


def _collect_worktrees(sessions, config):
    """Collect worktrees from all repos referenced by sessions and config."""
    all_wts = []
    seen_roots = set()

    project_root = config["_config_dir"]
    wts = worktree.list_worktrees(cwd=project_root)
    all_wts.extend(wts)
    for wt in wts:
        if wt.get("branch") in ("main", "master"):
            seen_roots.add(wt.get("path"))

    for s in sessions:
        workdir = s.get("workdir", "")
        if not workdir or workdir in seen_roots:
            continue
        seen_roots.add(workdir)
        wts = worktree.list_worktrees(cwd=workdir)
        for wt in wts:
            if not any(existing.get("path") == wt.get("path") for existing in all_wts):
                all_wts.append(wt)

    return all_wts


def _print_table(headers, rows):
    """Print a table with dynamic column widths."""
    if not rows:
        return

    # Calculate width for each column based on content
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    # Add padding
    widths = [w + 2 for w in widths]

    # Print header
    header_line = "".join(h.ljust(w) for h, w in zip(headers, widths))
    print(header_line)

    # Print rows
    for row in rows:
        line = "".join(cell.ljust(w) for cell, w in zip(row, widths))
        print(line)


def run(_args):
    nono.check_installed()
    config = project_config.load()
    wt_dir = project_config.get_worktree_dir(config)

    sessions = nono.ps_json(include_all=False)
    all_worktrees = _collect_worktrees(sessions, config)

    abs_wt_dir = os.path.abspath(wt_dir)
    managed_wts = [
        wt for wt in all_worktrees
        if wt.get("path", "").startswith(abs_wt_dir)
    ]

    if not managed_wts and not sessions:
        print("No worktrees or sessions found.")
        return

    headers = ["NAME", "PATH", "TYPE", "ISSUE/PR", "SESSION", "STATUS", "ATTACH", "AGE", "CHANGES"]
    rows = []

    shown_branches = set()

    for s in sessions:
        name = s.get("name", "")
        session_type, ref, expected_branch = _parse_session_name(name)
        session_id = s.get("session_id", "-")[:6]
        status = s.get("status", "?")
        attachment = s.get("attachment", "-")
        age = _format_uptime(s.get("started_epoch"))

        wt = _find_worktree(expected_branch, all_worktrees)

        if wt:
            wt_name = wt.get("branch", os.path.basename(wt["path"]))
            wt_path = _relative_path(wt["path"], s.get("workdir") or config["_config_dir"])
            shown_branches.add(wt.get("branch"))
            if os.path.isdir(wt["path"]):
                adds, dels = worktree.diff_stat(wt["path"])
                changes = f"+{adds} -{dels}"
            else:
                changes = "?"
        else:
            wt_name = name
            wt_path = "-"
            changes = "-"

        rows.append([wt_name, wt_path, session_type, ref, session_id, status, attachment, age, changes])

    for wt in managed_wts:
        branch = wt.get("branch", os.path.basename(wt["path"]))
        if branch in shown_branches:
            continue

        wt_path = _relative_path(wt["path"], config["_config_dir"])

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

        rows.append([branch, wt_path, wt_type, ref, "-", "-", "-", "-", changes])

    _print_table(headers, rows)
