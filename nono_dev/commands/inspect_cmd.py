"""Inspect a nono session with worktree details."""

import json
import os
import re
import sys

from nono_dev import nono, project_config, style, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "inspect", help="Show detailed session and worktree info",
    )
    parser.add_argument(
        "target",
        help="Session ID, name, or issue/PR number",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output as JSON",
    )
    parser.set_defaults(func=run)


def _resolve_session(target, sessions):
    """Find a session by name, branch name, number, or ID."""
    # By name
    for s in sessions:
        if s.get("name") == target:
            return s

    # By branch name (issue-123 -> fix-123)
    m = re.match(r"^issue-(\d+)$", target)
    if m:
        fix_name = f"fix-{m.group(1)}"
        for s in sessions:
            if s.get("name") == fix_name:
                return s

    # By number
    if target.isdigit():
        matches = [s for s in sessions if s.get("name", "").endswith(f"-{target}")]
        if len(matches) == 1:
            return matches[0]

    # By session ID or prefix
    for s in sessions:
        sid = s.get("session_id", "")
        if sid == target or sid.startswith(target):
            return s

    return None


def _get_worktree_info(session, config):
    """Get worktree details for a session."""
    name = session.get("name", "")

    m = re.match(r"^fix-(\d+)$", name)
    if m:
        branch = f"issue-{m.group(1)}"
    elif name.startswith("feat-"):
        branch = name[5:]
    else:
        return None

    project_root = config["_config_dir"]
    all_wts = worktree.list_worktrees(cwd=project_root)

    for wt in all_wts:
        if wt.get("branch") == branch:
            path = wt["path"]
            info = {"branch": branch, "path": path}
            if os.path.isdir(path):
                info["has_changes"] = worktree.has_changes(path)
                adds, dels = worktree.diff_stat(path)
                info["additions"] = adds
                info["deletions"] = dels
            return info

    return None


def run(args):
    nono.check_installed()

    sessions = nono.ps_json(include_all=True)
    session = _resolve_session(args.target, sessions)

    if not session:
        print(style.error(f"No session found matching '{args.target}'."), file=sys.stderr)
        sys.exit(1)

    config = project_config.load()
    wt_info = _get_worktree_info(session, config)

    if args.as_json:
        output = dict(session)
        if wt_info:
            output["worktree"] = wt_info
        print(json.dumps(output, indent=2))
        return

    # Styled output
    name = session.get("name", "-")
    sid = session.get("session_id", "-")
    status = session.get("status", "-")
    attachment = session.get("attachment", "-")
    profile = session.get("profile", "-")
    workdir = session.get("workdir", "-")
    started = session.get("started", "-")
    exit_code = session.get("exit_code")
    rollback = session.get("rollback_session")
    command = session.get("command", [])
    network = session.get("network", "-")

    print()
    print(style.banner(f"  Session: {name}"))
    print()

    _row("ID", sid)
    _row("Status", _styled_status(status))
    _row("Attach", _styled_attach(attachment))
    _row("Profile", profile)
    _row("Started", started)
    if exit_code is not None:
        _row("Exit Code", str(exit_code))
    _row("Network", network)
    _row("Workdir", workdir)
    _row("Command", " ".join(command[:3]) + (" ..." if len(command) > 3 else ""))

    if rollback:
        _row("Rollback", rollback)

    if wt_info:
        print()
        print(style.header("  Worktree"))
        print()
        _row("Branch", wt_info["branch"])
        _row("Path", wt_info["path"])
        if "has_changes" in wt_info:
            if wt_info["has_changes"]:
                changes = style.format_changes(wt_info["additions"], wt_info["deletions"])
                _row("Changes", changes)
            else:
                _row("Changes", style.dim("clean"))

    print()


def _row(label, value):
    print(f"    {style.label(label + ':'):<30} {value}")


def _styled_status(status):
    if status == "running":
        return style.status_running(status)
    if status == "exited":
        return style.muted(status)
    return status


def _styled_attach(attachment):
    if attachment == "attached":
        return style.status_attached(attachment)
    if attachment == "detached":
        return style.status_detached(attachment)
    return attachment
