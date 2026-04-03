"""Review a GitHub pull request using a sandboxed Claude agent."""

import os

from nono_dev import nono, project_config


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "review", help="Review a GitHub PR with a sandboxed agent",
    )
    parser.add_argument(
        "pr_number", help="GitHub PR number or URL",
    )
    parser.set_defaults(func=run)


def run(args):
    nono.check_installed()
    config = project_config.load()
    pr_number = project_config.parse_github_ref(args.pr_number)
    repo = project_config.get_repo(config)
    prompt_path = project_config.get_prompt_path("review", config)
    rollback = project_config.get_rollback(config)

    session_name = f"review-{pr_number}"

    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(f"Session '{session_name}' is already running.")
            print(f"  Attach: nono attach {s.get('session_id', session_name)}")
            return

    session_id = nono.run_detached(
        session_name,
        allows=[os.getcwd()],
        allow_cwd=True,
        system_prompt=prompt_path,
        user_prompt=str(pr_number),
        rollback=rollback,
    )

    print(f"Review session started for PR #{pr_number} ({repo})")
    print(f"  Session: {session_id}")
    print(f"  Attach:  nono attach {session_id}")
