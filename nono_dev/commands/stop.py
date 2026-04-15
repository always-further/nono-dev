"""Stop a running nono session."""

import subprocess
import sys

from nono_dev import nono
from nono_dev.session_targets import named_matches


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "stop", help="Stop a running nono session",
    )
    parser.add_argument(
        "target",
        help="Session ID, issue/PR number, or session name (e.g. review-530)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force stop (SIGKILL instead of SIGTERM)",
    )
    parser.set_defaults(func=run)


def _resolve_session_id(target, sessions):
    """Resolve a target to a session ID."""
    import re

    # Try by session name
    by_name = named_matches(target, sessions)
    if len(by_name) == 1:
        return by_name[0]["session_id"]
    if len(by_name) > 1:
        print(f"Multiple sessions match '{target}':")
        for s in by_name:
            sid = s.get("session_id", "?")[:6]
            name = s.get("name", "?")
            print(f"  {sid}  {name}")
        print("\nUse the full session name or ID.")
        sys.exit(1)

    # Try by worktree branch name (e.g. issue-123 -> fix-123)
    m = re.match(r"^issue-(\d+)$", target)
    if m:
        fix_name = f"fix-{m.group(1)}"
        by_fix = [s for s in sessions if s.get("name") == fix_name]
        if len(by_fix) == 1:
            return by_fix[0]["session_id"]

    # Try by issue/PR number
    if target.isdigit():
        matches = [
            s for s in sessions
            if s.get("name", "").endswith(f"-{target}")
        ]
        if len(matches) == 1:
            return matches[0]["session_id"]
        if len(matches) > 1:
            print(f"Multiple sessions match '#{target}':")
            for s in matches:
                sid = s.get("session_id", "?")[:6]
                name = s.get("name", "?")
                print(f"  {sid}  {name}")
            print("\nUse the session name (e.g. fix-{0}) or ID.".format(target))
            sys.exit(1)

    # Try as session ID or prefix
    exact = [s for s in sessions if s.get("session_id") == target]
    if exact:
        return target

    prefix = [
        s for s in sessions
        if s.get("session_id", "").startswith(target)
    ]
    if len(prefix) == 1:
        return prefix[0]["session_id"]

    return None


def run(args):
    nono.check_installed()

    sessions = nono.ps_json(include_all=False)
    if not sessions:
        print("No active nono sessions found.")
        sys.exit(1)

    session_id = _resolve_session_id(args.target, sessions)
    if not session_id:
        print(f"No active session found matching '{args.target}'.")
        sys.exit(1)

    cmd = ["nono", "stop", session_id]
    if args.force:
        cmd.append("--force")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)
