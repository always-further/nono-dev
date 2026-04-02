"""Switch to a worktree directory by name."""

import os
import sys

from nono_dev import nono, project_config, worktree
from nono_dev.commands.sandbox_status import _parse_session_name


def add_parser(subparsers):
    for name in ("worktree", "wt"):
        parser = subparsers.add_parser(
            name,
            help="Print the path to a worktree (use with cd)",
        )
        parser.add_argument(
            "name",
            help="Worktree branch name, session name, or issue number",
        )
        parser.add_argument(
            "--cd", action="store_true", dest="print_cd",
            help="Print a 'cd <path>' command (for shell eval)",
        )
        parser.set_defaults(func=run)


def _find_worktree_path(target, all_worktrees, sessions):
    """Resolve a target name to a worktree path.

    Matches against:
    - Exact branch name (e.g. issue-123, my-feature)
    - Session name (e.g. fix-123, feat-my-feature)
    - Bare issue number (e.g. 123 -> issue-123 branch)
    """
    # Direct branch match
    for wt in all_worktrees:
        if wt.get("branch") == target:
            return wt["path"]

    # Session name match -> derive expected branch
    for s in sessions:
        if s.get("name") == target:
            _, _, expected_branch = _parse_session_name(target)
            if expected_branch:
                for wt in all_worktrees:
                    if wt.get("branch") == expected_branch:
                        return wt["path"]
            # Session has a workdir even without a worktree
            workdir = s.get("workdir")
            if workdir and os.path.isdir(workdir):
                return workdir

    # Numeric target -> try issue-N branch
    if target.isdigit():
        branch = f"issue-{target}"
        for wt in all_worktrees:
            if wt.get("branch") == branch:
                return wt["path"]

    # Partial match on branch name
    matches = [wt for wt in all_worktrees if target in wt.get("branch", "")]
    if len(matches) == 1:
        return matches[0]["path"]

    return None


def run(args):
    config = project_config.load()
    wt_dir = project_config.get_worktree_dir(config)

    all_worktrees = worktree.list_worktrees(cwd=config["_config_dir"])

    # Only consider managed worktrees under the configured dir
    abs_wt_dir = os.path.abspath(wt_dir)
    managed = [
        wt for wt in all_worktrees
        if wt.get("path", "").startswith(abs_wt_dir)
    ]

    # Also include the main worktree for completeness
    main_wt = [wt for wt in all_worktrees if not wt.get("path", "").startswith(abs_wt_dir)]
    all_candidates = managed + main_wt

    try:
        sessions = nono.ps_json(include_all=False)
    except Exception:
        sessions = []

    path = _find_worktree_path(args.name, all_candidates, sessions)

    if not path:
        print(f"No worktree found matching '{args.name}'.", file=sys.stderr)
        if managed:
            print("\nAvailable worktrees:", file=sys.stderr)
            for wt in managed:
                branch = wt.get("branch", os.path.basename(wt["path"]))
                print(f"  {branch:<25} {wt['path']}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(path):
        print(f"Worktree path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    if args.print_cd:
        print(f"cd {path}")
    else:
        print(path)
