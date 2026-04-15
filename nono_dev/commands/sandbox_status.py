"""Dashboard showing worktrees, nono sessions, and change stats."""

import os
import re
import subprocess
import time

from nono_dev import nono, project_config, style, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "list", help="Show worktree and session status dashboard",
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

    m = re.match(r"^bare(?:-(.+))?$", name)
    if m:
        return "bare", m.group(1) or "-", None

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


def _repo_from_workdir(workdir):
    """Derive org/repo from a directory's git remote origin URL."""
    if not workdir or not os.path.isdir(workdir):
        return None
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True, cwd=workdir,
    )
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    m = re.match(r"git@[^:]+:(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    m = re.match(r"https?://[^/]+/(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)
    return None


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


def _style_cell(header, cell):
    """Apply color to a cell based on its column."""
    if header == "NAME":
        return style.value(cell) if cell != "-" else style.dim(cell)
    if header == "PATH":
        return style.muted(cell)
    if header == "TYPE":
        type_colors = {
            "fix": style.info, "review": style.label,
            "triage": style.warning, "feature": style.value,
            "bare": style.warning,
        }
        fn = type_colors.get(cell, style.muted)
        return fn(cell)
    if header == "STATUS":
        if cell == "running":
            return style.status_running(cell)
        return style.status_stopped(cell) if cell != "-" else style.dim(cell)
    if header == "ATTACH":
        if cell == "attached":
            return style.status_attached(cell)
        if cell == "detached":
            return style.status_detached(cell)
        return style.dim(cell)
    if header == "CHANGES":
        if cell.startswith("+") and " -" in cell:
            parts = cell.split(" ")
            return style.changes_positive(parts[0]) + " " + style.changes_negative(parts[1])
        return style.dim(cell)
    if header == "SESSION":
        return style.label(cell) if cell != "-" else style.dim(cell)
    if header == "ISSUE/PR":
        return style.header(cell) if cell != "-" else style.dim(cell)
    if header == "AGE":
        return style.muted(cell)
    if header == "PROJECT":
        return style.muted(cell) if cell != "-" else style.dim(cell)
    return cell


def _print_table(headers, rows):
    """Print a table with dynamic column widths and colors."""
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
    header_line = "".join(
        style.table_header(h.ljust(w)) for h, w in zip(headers, widths)
    )
    print(header_line)

    # Print rows with per-cell coloring
    for row in rows:
        parts = []
        for h, cell, w in zip(headers, row, widths):
            colored = _style_cell(h, cell)
            # Pad based on raw cell length, not ANSI-colored length
            padding = w - len(cell)
            parts.append(colored + " " * padding)
        print("".join(parts))


def run(_args):
    nono.check_installed()
    config = project_config.load()

    sessions = nono.ps_json(include_all=False)
    all_worktrees = _collect_worktrees(sessions, config)

    if not sessions:
        print("No sandboxes found.")
        return

    # Cache repo lookups by workdir to avoid repeated git calls
    repo_cache = {}

    def _get_project(workdir):
        if not workdir:
            return "-"
        if workdir not in repo_cache:
            repo_cache[workdir] = _repo_from_workdir(workdir) or "-"
        return repo_cache[workdir]

    headers = ["PROJECT", "NAME", "PATH", "TYPE", "ISSUE/PR", "SESSION", "STATUS", "ATTACH", "AGE", "CHANGES"]
    rows = []

    for s in sessions:
        name = s.get("name", "")
        session_type, ref, expected_branch = _parse_session_name(name)
        session_id = s.get("session_id", "-")[:6]
        status = s.get("status", "?")
        attachment = s.get("attachment", "-")
        age = _format_uptime(s.get("started_epoch"))
        project = _get_project(s.get("workdir"))

        wt = _find_worktree(expected_branch, all_worktrees)

        if wt:
            wt_name = wt.get("branch", os.path.basename(wt["path"]))
            wt_path = _relative_path(wt["path"], s.get("workdir") or config["_config_dir"])
            if os.path.isdir(wt["path"]):
                adds, dels = worktree.diff_stat(wt["path"])
                changes = f"+{adds} -{dels}"
            else:
                changes = "?"
        elif session_type == "bare" and s.get("workdir") and os.path.isdir(s["workdir"]):
            wt_name = name
            wt_path = _relative_path(s["workdir"], config["_config_dir"])
            adds, dels = worktree.diff_stat(s["workdir"])
            changes = f"+{adds} -{dels}"
        else:
            wt_name = name
            wt_path = "-"
            changes = "-"

        rows.append([project, wt_name, wt_path, session_type, ref, session_id, status, attachment, age, changes])

    _print_table(headers, rows)
