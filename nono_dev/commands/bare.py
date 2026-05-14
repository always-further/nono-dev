"""Start a sandboxed Claude session in the current checkout."""

import os
import re
import sys

from nono_dev import nono, project_config, style


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "bare", help="Start a sandboxed Claude session in the current checkout",
    )
    parser.add_argument(
        "name", nargs="?", help="Optional session name suffix",
    )
    parser.add_argument(
        "--no-rollback", action="store_true",
        help="Disable rollback snapshots for this session",
    )
    nono.add_sandbox_pass_through_args(parser)
    parser.set_defaults(func=run)


def _slugify(value):
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower())
    return slug.strip("._-") or "cwd"


def _default_suffix(config):
    project_root = project_config.get_project_root(config)
    cwd = os.getcwd()
    try:
        relative = os.path.relpath(cwd, project_root)
    except ValueError:
        relative = os.path.basename(cwd)

    label = os.path.basename(project_root) if relative == "." else relative
    return _slugify(label)


def _session_name(raw_name, config):
    suffix = _slugify(raw_name) if raw_name else _default_suffix(config)
    if suffix == "bare":
        return "bare"
    if suffix.startswith("bare-"):
        return suffix
    return f"bare-{suffix}"


def run(args):
    nono.check_installed()
    config = project_config.load()
    project_root = project_config.get_project_root(config)
    graph_line = project_config.graph_path_for_prompt(config, repo_hint=project_root)
    staleness = project_config.graph_staleness_warning(config, repo_hint=project_root)
    if staleness:
        print(style.warning(staleness), file=sys.stderr)
    prompt_path = project_config.get_rendered_prompt_path(
        "bare", config, substitutions={"graph_path": graph_line},
    )
    rollback = project_config.get_rollback(config)
    if args.no_rollback:
        rollback["enabled"] = False

    workdir = os.getcwd()
    git_dir = os.path.join(project_root, ".git")
    session_name = _session_name(args.name, config)

    sessions = nono.ps_json(include_all=False)
    for session in sessions:
        if session.get("name") == session_name:
            print(style.warning(f"Session '{session_name}' is already running."))
            print(
                f"  {style.label('Attach:')} "
                f"{style.value('nono-dev sb attach ' + session.get('session_id', session_name))}"
            )
            return

    extra_allows, extra_reads = nono.normalize_sandbox_paths(args)
    session_id = nono.run_detached(
        session_name,
        allows=[project_root, git_dir] + extra_allows,
        reads=extra_reads,
        allow_cwd=True,
        system_prompt=prompt_path,
        rollback=rollback,
        workdir=workdir,
        agent_args=nono.get_agent_args(args),
    )

    print(style.success("Bare session started"))
    print(f"  {style.label('Workspace:')} {style.value(workdir)}")
    print(f"  {style.label('Session:')}   {style.value(session_id)}")
    print(f"  {style.label('Attach:')}    {style.value('nono-dev sb attach ' + session_name)}")
