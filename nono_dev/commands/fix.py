"""Fix a GitHub issue using a sandboxed Claude agent in a worktree."""

import os
import sys

from nono_dev import nono, project_config, style, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "fix", help="Fix a GitHub issue in a sandboxed worktree",
    )
    parser.add_argument(
        "issue_number", help="GitHub issue number or URL",
    )
    parser.add_argument(
        "--no-rollback", action="store_true",
        help="Disable rollback snapshots for this session",
    )
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()
    config = project_config.load()
    url_repo, issue_number = project_config.parse_github_ref_full(args.issue_number)
    repo = project_config.get_repo(config)
    repo_root = os.getcwd()
    graph_line = project_config.graph_path_for_prompt(config, repo_hint=repo_root)
    staleness = project_config.graph_staleness_warning(config, repo_hint=repo_root)
    if staleness:
        print(style.warning(staleness), file=sys.stderr)
    prompt_path = project_config.get_rendered_prompt_path(
        "fix", config, substitutions={"graph_path": graph_line},
    )
    rollback = project_config.get_rollback(config)
    if args.no_rollback:
        rollback["enabled"] = False
    wt_dir = project_config.get_worktree_dir(config)

    # When a URL points at a sibling repo, namespace branch/worktree/session
    # so that e.g. nono#42 and nono-py#42 don't collide. Cross-repo branches
    # use the reserved `xrepo-` prefix so user-chosen branches like
    # `docs-issue-42` stay classified as feature branches.
    slug = project_config.namespace_slug(url_repo, repo)
    if slug:
        branch = f"xrepo-{slug}-issue-{issue_number}"
        session_name = f"fix-{slug}-{issue_number}"
    else:
        branch = f"issue-{issue_number}"
        session_name = f"fix-{issue_number}"
    wt_path = os.path.join(wt_dir, branch)

    if slug:
        print(style.warning(
            f"Issue is in '{url_repo}' but this worktree lives in '{repo}'. "
            f"Creating branch '{branch}' here — you may want to cd into "
            f"the '{url_repo}' checkout instead."
        ))

    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(style.warning(f"Session '{session_name}' is already running."))
            print(f"  {style.label('Attach:')} {style.value('nono-dev sb attach ' + s.get('session_id', session_name))}")
            return

    result = worktree.add(branch, wt_path)
    if result is None:
        abs_path = os.path.abspath(wt_path)
        if os.path.isdir(abs_path):
            print(style.muted(f"Worktree '{branch}' already exists, reusing it."))
        else:
            print(style.error(f"Branch '{branch}' already exists. Use a different name or clean up."))
            return
    else:
        abs_path = result

    # Grant read access to the main repo so Claude's Read/Edit tools
    # can follow symlinks from the worktree back to the canonical paths.
    # Grant write access to .git/ for commits, index, refs, objects.
    git_dir = os.path.join(repo_root, ".git")

    session_id = nono.run_detached(
        session_name,
        allows=[abs_path, git_dir],
        reads=[repo_root],
        allow_cwd=True,
        system_prompt=prompt_path,
        user_prompt=args.issue_number,
        rollback=rollback,
        workdir=abs_path,
    )

    print(style.success(f"Fix session started for issue #{issue_number}") + style.muted(f" ({repo})"))
    print(f"  {style.label('Worktree:')} {style.value(abs_path)}")
    print(f"  {style.label('Branch:')}   {style.value(branch)}")
    print(f"  {style.label('Session:')}  {style.value(session_id)}")
    print(f"  {style.label('Attach:')}   {style.value('nono-dev sb attach ' + session_name)}")
