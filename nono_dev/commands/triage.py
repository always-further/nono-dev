"""Triage a GitHub issue using a sandboxed agent."""

import os

from nono_dev import nono, project_config, style


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "triage", help="Triage a GitHub issue with a sandboxed agent",
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
    project_root = project_config.get_project_root(config)
    issue_number = project_config.parse_github_ref(args.issue_number)
    repo = project_config.get_repo(config)
    prompt_path = project_config.get_prompt_path("triage", config)
    rollback = project_config.get_rollback(config)
    if args.no_rollback:
        rollback["enabled"] = False

    session_name = f"triage-{issue_number}"

    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(style.warning(f"Session '{session_name}' is already running."))
            print(f"  {style.label('Attach:')} {style.value('nono-dev sb attach ' + s.get('session_id', session_name))}")
            return

    session_id = nono.run_detached(
        session_name,
        agent_config=nono.get_agent_config(config),
        allows=[project_root],
        allow_cwd=True,
        system_prompt=prompt_path,
        user_prompt=str(issue_number),
        rollback=rollback,
        workdir=os.getcwd(),
    )

    print(style.success(f"Triage session started for issue #{issue_number}") + style.muted(f" ({repo})"))
    print(f"  {style.label('Session:')} {style.value(session_id)}")
    print(f"  {style.label('Attach:')}  {style.value('nono-dev sb attach ' + session_name)}")
