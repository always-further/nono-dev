"""Fix a GitHub issue using a sandboxed Claude agent in a worktree."""

import os

from nono_dev import nono, project_config, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "fix", help="Fix a GitHub issue in a sandboxed worktree",
    )
    parser.add_argument(
        "issue_number", help="GitHub issue number or URL",
    )
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()
    config = project_config.load()
    issue_number = project_config.parse_github_ref(args.issue_number)
    repo = project_config.get_repo(config)
    prompt_path = project_config.get_prompt_path("fix", config)
    rollback = project_config.get_rollback(config)
    wt_dir = project_config.get_worktree_dir(config)

    branch = f"issue-{issue_number}"
    wt_path = os.path.join(wt_dir, branch)
    session_name = f"fix-{issue_number}"

    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(f"Session '{session_name}' is already running.")
            print(f"  Attach: nono attach {s.get('session_id', session_name)}")
            return

    result = worktree.add(branch, wt_path)
    if result is None:
        abs_path = os.path.abspath(wt_path)
        if os.path.isdir(abs_path):
            print(f"Worktree '{branch}' already exists, reusing it.")
        else:
            print(f"Branch '{branch}' already exists. Use a different name or clean up.")
            return
    else:
        abs_path = result

    # Grant read access to the main repo so Claude's Read/Edit tools
    # can follow symlinks from the worktree back to the canonical paths.
    # Grant write access to .git/ for commits, index, refs, objects.
    repo_root = os.getcwd()
    git_dir = os.path.join(repo_root, ".git")

    session_id = nono.run_detached(
        session_name,
        allows=[abs_path, git_dir],
        reads=[repo_root],
        allow_cwd=True,
        system_prompt=prompt_path,
        user_prompt=str(issue_number),
        rollback=rollback,
        workdir=abs_path,
    )

    print(f"Fix session started for issue #{issue_number} ({repo})")
    print(f"  Worktree: {abs_path}")
    print(f"  Branch:   {branch}")
    print(f"  Session:  {session_id}")
    print(f"  Attach:   nono attach {session_id}")
