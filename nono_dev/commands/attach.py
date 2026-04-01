"""Attach to an existing nono session."""

import sys

from nono_dev import nono


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "attach", help="Attach to a running nono session",
    )
    parser.add_argument(
        "target",
        help="Session ID, or issue/PR number to look up",
    )
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()

    target = args.target
    sessions = nono.ps_json(include_all=False)

    if not sessions:
        print("No active nono sessions found.")
        sys.exit(1)

    # If target is numeric, search by issue/PR number in session names
    if target.isdigit():
        matches = [
            s for s in sessions
            if target in (s.get("name", "").split("-")[-1:])
        ]
        if len(matches) == 1:
            session_id = matches[0].get("session_id", matches[0].get("name"))
            nono.attach(session_id)
        elif len(matches) > 1:
            print(f"Multiple sessions match '#{target}':")
            for s in matches:
                print(f"  {s.get('session_id', '?')[:6]}  {s.get('name', '?')}")
            print("\nSpecify the session ID directly.")
            sys.exit(1)
        else:
            print(f"No active session found for '#{target}'.")
            print("\nActive sessions:")
            for s in sessions:
                print(f"  {s.get('session_id', '?')[:6]}  {s.get('name', '?')}")
            sys.exit(1)
    else:
        # Treat as a session ID - try direct match first, then prefix match
        exact = [s for s in sessions if s.get("session_id") == target]
        if exact:
            nono.attach(target)

        prefix = [
            s for s in sessions
            if s.get("session_id", "").startswith(target)
        ]
        if len(prefix) == 1:
            nono.attach(prefix[0]["session"])
        elif len(prefix) > 1:
            print(f"Ambiguous session prefix '{target}':")
            for s in prefix:
                print(f"  {s.get('session_id', '?')[:6]}  {s.get('name', '?')}")
            sys.exit(1)

        # Try as a session name
        by_name = [s for s in sessions if s.get("name") == target]
        if by_name:
            nono.attach(by_name[0].get("session_id", target))

        print(f"No session found matching '{target}'.")
        sys.exit(1)
