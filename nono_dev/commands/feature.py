"""Start a new feature in a sandboxed worktree."""

import os

from nono_dev import nono, project_config, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "feature", help="Start a new feature in a sandboxed worktree",
    )
    parser.add_argument(
        "branch_name", help="Branch name for the feature",
    )
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()
    config = project_config.load()
    prompt_path = project_config.get_prompt_path("feature", config)
    rollback = project_config.get_rollback(config)
    wt_dir = project_config.get_worktree_dir(config)

    wt_path = os.path.join(wt_dir, args.branch_name)
    session_name = f"feat-{args.branch_name}"

    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(f"Session '{session_name}' is already running.")
            print(f"  Attach: nono attach {s.get('session_id', session_name)}")
            return

    result = worktree.add(args.branch_name, wt_path)
    if result is None:
        abs_path = os.path.abspath(wt_path)
        if os.path.isdir(abs_path):
            print(f"Worktree '{args.branch_name}' already exists, reusing it.")
        else:
            print(f"Branch '{args.branch_name}' already exists. Use a different name or clean up.")
            return
    else:
        abs_path = result

    # Grant read access to the main repo so Claude's Read/Edit tools
    # can follow symlinks from the worktree back to the canonical paths.
    repo_root = os.getcwd()

    session_id = nono.run_detached(
        session_name,
        allows=[abs_path],
        reads=[repo_root],
        allow_cwd=True,
        system_prompt=prompt_path,
        rollback=rollback,
        workdir=abs_path,
    )

    print(f"Feature session started for '{args.branch_name}'")
    print(f"  Worktree: {abs_path}")
    print(f"  Branch:   {args.branch_name}")
    print(f"  Session:  {session_id}")
    print(f"  Attach:   nono attach {session_id}")
