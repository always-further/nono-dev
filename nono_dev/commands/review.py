"""Review a GitHub pull request using a sandboxed agent."""

import os
import sys

from nono_dev import nono, project_config, style


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "review", help="Review a GitHub PR with a sandboxed agent",
    )
    parser.add_argument(
        "pr_number", help="GitHub PR number or URL",
    )
    parser.add_argument(
        "--no-rollback", action="store_true",
        help="Disable rollback snapshots for this session",
    )
    nono.add_sandbox_pass_through_args(parser)
    nono.add_agent_select_args(parser)
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()
    config = project_config.load()
    project_root = project_config.get_project_root(config)
    url_repo, pr_number = project_config.parse_github_ref_full(args.pr_number)
    repo = project_config.get_repo(config)
    graph_line = project_config.graph_path_for_prompt(config, repo_hint=project_root)
    staleness = project_config.graph_staleness_warning(config, repo_hint=project_root)
    if staleness:
        print(style.warning(staleness), file=sys.stderr)
    prompt_path = project_config.get_rendered_prompt_path(
        "review", config, substitutions={"graph_path": graph_line},
    )
    rollback = project_config.get_rollback(config)
    if args.no_rollback:
        rollback["enabled"] = False

    slug = project_config.namespace_slug(url_repo, repo)
    session_name = f"review-{slug}-{pr_number}" if slug else f"review-{pr_number}"
    session_name += nono.agent_name_suffix(config, args.agent)

    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(style.warning(f"Session '{session_name}' is already running."))
            print(f"  {style.label('Attach:')} {style.value('nono-dev sb attach ' + s.get('session_id', session_name))}")
            return

    extra_allows, extra_reads = nono.normalize_sandbox_paths(args)
    session_id = nono.run_detached(
        session_name,
        agent_config=nono.get_agent_config(config, override_binary=args.agent),
        allows=[project_root] + extra_allows,
        reads=extra_reads,
        allow_cwd=True,
        system_prompt=prompt_path,
        user_prompt=args.pr_number,
        rollback=rollback,
        workdir=os.getcwd(),
        agent_args=nono.get_agent_args(args),
    )

    print(style.success(f"Review session started for PR #{pr_number}") + style.muted(f" ({repo})"))
    print(f"  {style.label('Session:')} {style.value(session_id)}")
    print(f"  {style.label('Attach:')}  {style.value('nono-dev sb attach ' + session_name)}")
