"""Attach to an existing nono session."""

import sys

from nono_dev import nono, project_config


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "attach", help="Attach to a running nono session",
    )
    parser.add_argument(
        "target",
        help="Session ID, issue/PR number, or session name (e.g. fix-563)",
    )
    parser.set_defaults(func=run)


def _print_sessions(sessions):
    """Print a list of sessions for the user to pick from."""
    for s in sessions:
        sid = s.get("session_id", "?")[:6]
        name = s.get("name", "?")
        status = s.get("status", "?")
        print(f"  {sid}  {name:<25} {status}")


def run(args):
    nono.check_installed()

    target = args.target
    sessions = nono.ps_json(include_all=False)

    if not sessions:
        print("No active nono sessions found.")
        sys.exit(1)

    # Try matching by session name first (e.g. fix-563, review-530)
    by_name = [s for s in sessions if s.get("name") == target]
    if len(by_name) == 1:
        nono.attach(by_name[0]["session_id"])

    # Try matching by worktree branch name. Handles both `issue-N` and
    # cross-repo `<slug>-issue-N` shapes produced by `nd fix <url>`.
    fix_name = project_config.branch_to_fix_session(target)
    if fix_name:
        by_fix = [s for s in sessions if s.get("name") == fix_name]
        if len(by_fix) == 1:
            nono.attach(by_fix[0]["session_id"])

    # If target is numeric, search by issue/PR number in session names
    if target.isdigit():
        matches = [
            s for s in sessions
            if s.get("name", "").endswith(f"-{target}")
        ]
        if len(matches) == 1:
            nono.attach(matches[0]["session_id"])
        elif len(matches) > 1:
            print(f"Multiple sessions match '#{target}':")
            _print_sessions(matches)
            print("\nUse the session name (e.g. fix-{0}) or ID.".format(target))
            sys.exit(1)

    # Try as a session ID -- exact match
    exact = [s for s in sessions if s.get("session_id") == target]
    if exact:
        nono.attach(target)

    # Try as a session ID prefix
    prefix = [
        s for s in sessions
        if s.get("session_id", "").startswith(target)
    ]
    if len(prefix) == 1:
        nono.attach(prefix[0]["session_id"])
    elif len(prefix) > 1:
        print(f"Ambiguous session prefix '{target}':")
        _print_sessions(prefix)
        sys.exit(1)

    # Nothing matched
    print(f"No active session found matching '{target}'.")
    if sessions:
        print("\nActive sessions:")
        _print_sessions(sessions)
    sys.exit(1)
