"""Start a new feature in a sandboxed worktree."""

import os
import sys

from nono_dev import nono, project_config, style, worktree


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "feature", help="Start a new feature in a sandboxed worktree",
    )
    parser.add_argument(
        "branch_name", help="Branch name for the feature",
    )
    parser.add_argument(
        "--no-rollback", action="store_true",
        help="Disable rollback snapshots for this session",
    )
    nono.add_sandbox_pass_through_args(parser)
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()
    config = project_config.load()
    project_root = project_config.get_project_root(config)
    graph_line = project_config.graph_path_for_prompt(config, repo_hint=project_root)
    staleness = project_config.graph_staleness_warning(config, repo_hint=project_root)
    if staleness:
        print(style.warning(staleness), file=sys.stderr)
    prompt_path = project_config.get_rendered_prompt_path(
        "feature", config, substitutions={"graph_path": graph_line},
    )
    rollback = project_config.get_rollback(config)
    if args.no_rollback:
        rollback["enabled"] = False
    wt_dir = project_config.get_worktree_dir(config)

    wt_path = os.path.join(wt_dir, args.branch_name)
    session_name = f"feat-{args.branch_name}"

    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(style.warning(f"Session '{session_name}' is already running."))
            print(f"  {style.label('Attach:')} {style.value('nono-dev sb attach ' + s.get('session_id', session_name))}")
            return

    result = worktree.add(args.branch_name, wt_path, cwd=project_root)
    if result is None:
        abs_path = os.path.abspath(wt_path)
        if os.path.isdir(abs_path):
            print(style.muted(f"Worktree '{args.branch_name}' already exists, reusing it."))
        else:
            print(style.error(f"Branch '{args.branch_name}' already exists. Use a different name or clean up."))
            return
    else:
        abs_path = result

    # Grant read access to the main repo so Claude's Read/Edit tools
    # can follow symlinks from the worktree back to the canonical paths.
    # Grant write access to .git/ for commits, index, refs, objects.
    git_dir = os.path.join(project_root, ".git")

    extra_allows, extra_reads = nono.normalize_sandbox_paths(args)
    session_id = nono.run_detached(
        session_name,
        allows=[abs_path, git_dir] + extra_allows,
        reads=[project_root] + extra_reads,
        allow_cwd=True,
        system_prompt=prompt_path,
        rollback=rollback,
        workdir=abs_path,
    )

    print(style.success(f"Feature session started for '{args.branch_name}'"))
    print(f"  {style.label('Worktree:')} {style.value(abs_path)}")
    print(f"  {style.label('Branch:')}   {style.value(args.branch_name)}")
    print(f"  {style.label('Session:')}  {style.value(session_id)}")
    print(f"  {style.label('Attach:')}   {style.value('nono-dev sb attach ' + session_name)}")
