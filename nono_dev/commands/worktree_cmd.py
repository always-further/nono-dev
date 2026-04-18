"""Worktree management commands: list, cd, cleanup."""

import os
import re
import sys

from nono_dev import lima, nono, project_config, style, worktree
from nono_dev.config import DEFAULT_VM_NAME
from nono_dev.commands.sandbox_status import (
    _format_uptime,
    _parse_session_name,
    _print_table,
    _repo_from_workdir,
)


def _wt_help(_args):
    """Print styled wt group help."""
    print()
    print(style.banner("  nono-dev wt"))
    print()
    print(style.help_row("wt list",    "",             "List managed worktrees"))
    print(style.help_row("wt cd",      "<name>",       "Open a shell in a worktree"))
    print(style.help_row("wt start",   "<name>",       "Open a shell and start a sandbox"))
    print(style.help_row("wt cleanup", "<name|--all>", "Remove worktrees and branches"))
    print()
    sys.exit(0)


def add_parser(subparsers):
    """Register the 'wt' command group with list/cd/cleanup subcommands."""
    wt_parser = subparsers.add_parser("wt", help="Manage worktrees")
    wt_sub = wt_parser.add_subparsers(dest="wt_command")
    wt_parser.set_defaults(func=_wt_help)

    # wt list
    list_parser = wt_sub.add_parser("list", help="List managed worktrees")
    list_parser.set_defaults(func=run_list)

    # wt cd
    cd_parser = wt_sub.add_parser("cd", help="Open a shell in a worktree directory")
    cd_parser.add_argument("name", help="Worktree branch name, session name, or issue number")
    cd_parser.set_defaults(func=run_cd)

    # wt start
    start_parser = wt_sub.add_parser("start", help="Open a shell in a worktree and start a sandbox")
    start_parser.add_argument("name", help="Worktree branch name, session name, or issue number")
    start_parser.add_argument(
        "--no-rollback", action="store_true",
        help="Disable rollback snapshots for this session",
    )
    start_parser.set_defaults(func=run_start)

    # wt cleanup
    cleanup_parser = wt_sub.add_parser("cleanup", help="Remove worktrees and their branches")
    cleanup_parser.add_argument(
        "name", nargs="?", default=None,
        help="Worktree name to remove (e.g. issue-42)",
    )
    cleanup_parser.add_argument(
        "--all", action="store_true", dest="remove_all",
        help="Remove all managed worktrees",
    )
    cleanup_parser.add_argument(
        "--force", action="store_true",
        help="Skip confirmation prompts",
    )
    cleanup_parser.set_defaults(func=run_cleanup)


def _get_managed_worktrees(config):
    """Return managed worktrees and the project root."""
    project_root = project_config.get_project_root(config)
    wt_dir = project_config.get_worktree_dir(config)
    abs_wt_dir = os.path.abspath(wt_dir)

    all_wts = worktree.list_worktrees(cwd=project_root)
    managed = [
        wt for wt in all_wts
        if wt.get("path", "").startswith(abs_wt_dir)
    ]
    return managed, all_wts, project_root


def _find_worktree_path(target, all_worktrees, sessions):
    """Resolve a target name to a worktree path."""
    # Direct branch match
    for wt in all_worktrees:
        if wt.get("branch") == target:
            return wt["path"]

    # Session name match
    for s in sessions:
        if s.get("name") == target:
            _, _, expected_branch = _parse_session_name(target)
            if expected_branch:
                for wt in all_worktrees:
                    if wt.get("branch") == expected_branch:
                        return wt["path"]
            workdir = s.get("workdir")
            if workdir and os.path.isdir(workdir):
                return workdir

    # Numeric target -> issue-N branch
    if target.isdigit():
        branch = f"issue-{target}"
        for wt in all_worktrees:
            if wt.get("branch") == branch:
                return wt["path"]

    # Partial match
    matches = [wt for wt in all_worktrees if target in wt.get("branch", "")]
    if len(matches) == 1:
        return matches[0]["path"]

    return None


def run_list(_args):
    """List all managed worktrees with project, type, and sandbox info."""
    config = project_config.load()
    managed, _, project_root = _get_managed_worktrees(config)

    if not managed:
        print(style.muted("No managed worktrees found."))
        return

    # Get project name
    project = _repo_from_workdir(project_root) or "-"

    # Get running sessions to match against worktrees
    try:
        sessions = nono.ps_json(include_all=False)
    except Exception:
        sessions = []

    # Index sessions by expected worktree branch
    session_by_branch = {}
    for s in sessions:
        name = s.get("name", "")
        _, _, expected_branch = _parse_session_name(name)
        if expected_branch:
            session_by_branch[expected_branch] = s

    headers = ["PROJECT", "NAME", "PATH", "TYPE", "ISSUE/PR", "SESSION", "STATUS", "AGE", "CHANGES"]
    rows = []

    for wt in managed:
        branch = wt.get("branch", os.path.basename(wt["path"]))
        rel_path = os.path.relpath(wt["path"], project_root)

        # Derive type and issue/PR from branch name.
        # Matches same-repo (`issue-N`) and cross-repo (`xrepo-<slug>-issue-N`)
        # fix branches. The reserved `xrepo-` prefix keeps user-chosen
        # branches like `docs-issue-42` from being misclassified.
        m = re.match(r"^issue-(\d+)$", branch)
        if m:
            wt_type, ref = "fix", f"#{m.group(1)}"
        elif (m := re.match(r"^xrepo-(.+)-issue-(\d+)$", branch)):
            slug, number = m.groups()
            wt_type, ref = "fix", f"{slug}#{number}"
        else:
            wt_type, ref = "feature", branch

        # Check for matching sandbox session
        s = session_by_branch.get(branch)
        if s:
            session_id = s.get("session_id", "-")[:6]
            status = s.get("status", "-")
            age = _format_uptime(s.get("started_epoch"))
        else:
            session_id, status, age = "-", "-", "-"

        # Diff stats
        if os.path.isdir(wt["path"]):
            adds, dels = worktree.diff_stat(wt["path"])
            changes = f"+{adds} -{dels}"
        else:
            changes = "?"

        rows.append([project, branch, rel_path, wt_type, ref, session_id, status, age, changes])

    _print_table(headers, rows)


def run_cd(args):
    """Print the path to a worktree (used by the wt shell function)."""
    config = project_config.load()
    managed, all_wts, _ = _get_managed_worktrees(config)
    main_wt = [wt for wt in all_wts if wt not in managed]
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
                print(f"  {branch}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(path):
        print(f"Worktree path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    print(path)


def run_start(args):
    """Resolve a worktree, start a sandbox in it, and print the path."""
    nono.check_installed()
    config = project_config.load()
    managed, all_wts, _ = _get_managed_worktrees(config)
    main_wt = [wt for wt in all_wts if wt not in managed]
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
                print(f"  {branch}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(path):
        print(f"Worktree path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    # Determine branch name from the resolved worktree
    branch = None
    for wt in all_candidates:
        if wt.get("path") == path:
            branch = wt.get("branch", os.path.basename(path))
            break
    if not branch:
        branch = os.path.basename(path)

    # Match session naming convention used by fix/feature commands,
    # including cross-repo fix branches like `nono-py-issue-42`.
    fix_session = project_config.branch_to_fix_session(branch)
    session_name = fix_session if fix_session else f"feat-{branch}"

    # Check if a session is already running for this worktree
    for s in sessions:
        if s.get("name") == session_name:
            print(style.warning(f"Session '{session_name}' is already running."), file=sys.stderr)
            print(f"  {style.label('Attach:')} {style.value('nono-dev sb attach ' + s.get('session_id', session_name))}", file=sys.stderr)
            # Still print path so the shell function can cd
            print(path)
            return

    repo_root = project_config.get_project_root(config)
    graph_line = project_config.graph_path_for_prompt(config, repo_hint=repo_root)
    staleness = project_config.graph_staleness_warning(config, repo_hint=repo_root)
    if staleness:
        print(style.warning(staleness), file=sys.stderr)
    prompt_path = project_config.get_rendered_prompt_path(
        "feature", config, substitutions={"graph_path": graph_line},
    )
    rollback = project_config.get_rollback(config)
    if args.no_rollback:
        rollback["enabled"] = False

    abs_path = os.path.abspath(path)
    git_dir = os.path.join(repo_root, ".git")
    session_id = nono.run_detached(
        session_name,
        allows=[abs_path, git_dir],
        reads=[repo_root],
        allow_cwd=True,
        system_prompt=prompt_path,
        rollback=rollback,
        workdir=abs_path,
    )

    print(style.success(f"Sandbox started in worktree '{branch}'"), file=sys.stderr)
    print(f"  {style.label('Session:')}  {style.value(session_id)}", file=sys.stderr)
    print(f"  {style.label('Attach:')}   {style.value('nono-dev sb attach ' + session_name)}", file=sys.stderr)

    _check_vm_mount(abs_path)

    # Print path to stdout for the shell function to cd
    print(path)


def _check_vm_mount(worktree_path):
    """If the VM's mount doesn't match this worktree, offer to remount."""
    try:
        vms = lima.list_vms_json()
    except Exception:
        return
    vm_names = [v["name"] for v in vms if v.get("name")]
    if DEFAULT_VM_NAME in vm_names:
        vm_name = DEFAULT_VM_NAME
    elif len(vm_names) == 1:
        vm_name = vm_names[0]
    else:
        return  # multiple or none — don't guess

    info = lima.sync_info(vm_name)
    if info is None:
        print(f"  {style.label('VM mount:')} {style.muted('(no active sync)')}", file=sys.stderr)
        return

    host_path, guest_url = info
    if os.path.realpath(host_path) == os.path.realpath(worktree_path):
        print(f"  {style.label('VM mount:')} {style.value(host_path)} {style.muted('(matches)')}", file=sys.stderr)
        return

    print(f"  {style.label('VM mount:')} {style.warning(host_path)} {style.muted('(different worktree)')}", file=sys.stderr)
    try:
        answer = input(f"  Remount VM sync to '{worktree_path}'? [y/N]: ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        return

    username = os.environ.get("USER", "dev")
    guest_project = f"/home/{username}.guest/project"
    print(f"  {style.muted('Stopping previous sync...')}", file=sys.stderr)
    lima.stop_sync(vm_name)
    print(f"  {style.muted('Starting sync of ')}{worktree_path}{style.muted(' -> ~/project...')}", file=sys.stderr)
    lima.start_sync(vm_name, worktree_path, guest_project)
    print(f"  {style.success('VM sync remounted.')}", file=sys.stderr)


def run_cleanup(args):
    """Remove worktrees and their branches."""
    config = project_config.load()
    managed, _, project_root = _get_managed_worktrees(config)

    if args.name:
        name = args.name.rstrip("/")
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
        print(f"  {style.success('Removed')} {style.value(branch)}")
