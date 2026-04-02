"""Remove worktrees and their branches."""

import os
import sys

from nono_dev import project_config, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "cleanup", help="Remove worktrees and their branches",
    )
    parser.add_argument(
        "name", nargs="?", default=None,
        help="Worktree name to remove (e.g. issue-42)",
    )
    parser.add_argument(
        "--all", action="store_true", dest="remove_all",
        help="Remove all managed worktrees",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompts",
    )
    parser.set_defaults(func=run)


def run(args):
    config = project_config.load()
    wt_dir = project_config.get_worktree_dir(config)
    project_root = config["_config_dir"]
    abs_wt_dir = os.path.abspath(wt_dir)

    all_worktrees = worktree.list_worktrees(cwd=project_root)
    managed = [
        wt for wt in all_worktrees
        if wt.get("path", "").startswith(abs_wt_dir)
    ]

    if args.name:
        name = args.name.rstrip("/")
        # Match by branch name, directory basename, or relative path
        abs_name = os.path.abspath(os.path.join(project_root, name))
        targets = [
            wt for wt in managed
            if wt.get("branch") == name
            or os.path.basename(wt.get("path", "")) == name
            or os.path.basename(wt.get("path", "")) == os.path.basename(name)
            or wt.get("path") == abs_name
        ]
        if not targets:
            print(f"Worktree '{args.name}' not found.")
            sys.exit(1)
    elif args.remove_all:
        targets = managed
    else:
        print("Specify a worktree name or use --all.")
        sys.exit(1)

    if not targets:
        print("No worktrees to clean up.")
        return

    for wt in targets:
        path = wt["path"]
        branch = wt.get("branch", os.path.basename(path))

        if worktree.has_changes(path):
            adds, dels = worktree.diff_stat(path)
            if not args.force:
                answer = input(
                    f"Worktree '{branch}' has uncommitted changes "
                    f"(+{adds} -{dels}). Delete anyway? [y/N] "
                ).strip().lower()
                if answer != "y":
                    print(f"  Skipped '{branch}'.")
                    continue

        worktree.remove(path, force=True, cwd=project_root)
        worktree.delete_branch(branch, cwd=project_root)
        print(f"  Removed '{branch}'.")
