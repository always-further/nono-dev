"""Interactive wizard to create nono-dev.toml."""

import os
import re
import shutil
import subprocess
import sys

from nono_dev import style
from nono_dev.commands.graph import _ensure_git_excluded
from nono_dev.project_config import CONFIG_FILENAME


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "init", help=f"Create {CONFIG_FILENAME} at the repository root",
    )
    parser.add_argument(
        "--force", action="store_true",
        help=f"Overwrite an existing {CONFIG_FILENAME}",
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Accept all defaults without prompting",
    )
    parser.set_defaults(func=run)


def _ask(prompt, default="", auto=False):
    """Prompt the user; return default if auto mode or empty input."""
    if auto:
        return default
    try:
        answer = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    return answer or default


def _ask_yn(prompt, default=True, auto=False):
    """Yes/no prompt. Returns bool."""
    hint = "Y/n" if default else "y/N"
    raw = _ask(f"{prompt} [{hint}] ", default="y" if default else "n", auto=auto)
    return raw.lower() in ("y", "yes")


def _detect_repo():
    """Derive org/repo from git remote, preferring upstream over origin."""
    for remote in ("upstream", "origin"):
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", remote],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                continue
            url = result.stdout.strip()
            m = re.match(r"git@[^:]+:(.+?)(?:\.git)?$", url)
            if m:
                return m.group(1)
            m = re.match(r"https?://[^/]+/(.+?)(?:\.git)?$", url)
            if m:
                return m.group(1)
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def _repo_short_name(repo):
    """Extract the repo name portion from org/repo."""
    if not repo:
        return os.path.basename(os.path.abspath(_git_toplevel() or os.getcwd()))
    return repo.split("/")[-1] if "/" in repo else repo


def _build_toml(repo, worktree_dir, rollback, graph_name, graph_repo=None):
    """Build the toml content from wizard answers."""
    lines = ["# nono-dev configuration", ""]

    lines.append("[project]")
    if repo:
        lines.append(f'repo = "{repo}"')
    else:
        lines.append('# repo = "org/repo"  # set manually or add a git remote')
    lines.append("")

    lines.append("[worktree]")
    lines.append(f'dir = "{worktree_dir}"')
    lines.append("")

    lines.append("[rollback]")
    lines.append(f"enabled = {'true' if rollback else 'false'}")
    if rollback:
        lines.append('dest = "~/.nono/rollbacks"')
        lines.append('exclude = [".git", "node_modules", ".worktrees", "graphify-out", ".nono-dev"]')
    lines.append("")

    lines.append("[prompts]")
    lines.append("# triage = \"prompts/triage.md\"")
    lines.append("# fix = \"prompts/fix.md\"")
    lines.append("# review = \"prompts/review.md\"")
    lines.append("# feature = \"prompts/feature.md\"")
    lines.append("# bare = \"prompts/bare.md\"")
    lines.append("")

    if graph_name:
        lines.append(f"[graphs.{graph_name}]")
        lines.append('path = "."')
        if graph_repo:
            lines.append(f'repo = "{graph_repo}"')
        lines.append("ingest = true")
        lines.append("")

    return "\n".join(lines) + "\n"


def _git_toplevel():
    """Return the git repo root, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def run(args):
    repo_root = _git_toplevel()
    if not repo_root:
        print(style.error("not inside a git repository — run nd init from a repo root"), file=sys.stderr)
        sys.exit(1)

    dest = os.path.join(repo_root, CONFIG_FILENAME)
    auto = args.yes

    if os.path.exists(dest) and not args.force:
        print(style.warning(f"{dest} already exists (use --force to overwrite)"))
        sys.exit(1)

    overwriting = os.path.exists(dest)

    print()
    print(style.header("  nono-dev init"))
    print()

    # 1. Repo
    detected_repo = _detect_repo()
    if detected_repo:
        if auto:
            repo = detected_repo
        else:
            print(f"  {style.label('repo:')}      {style.value(detected_repo)} (from git remote)")
            if not _ask_yn("  Use this?", default=True, auto=auto):
                repo = _ask("  repo (org/repo): ", auto=auto) or None
            else:
                repo = detected_repo
    else:
        print(f"  {style.warning('repo:')}      no git remote found")
        repo = _ask("  repo (org/repo, or enter to skip): ", auto=auto) or None

    # 2. Worktree dir
    if _ask_yn(f"  {style.label('worktree dir')} .worktrees?", default=True, auto=auto):
        wt_dir = ".worktrees"
    else:
        wt_dir = _ask(f"  {style.label('worktree dir:')} ", default=".worktrees", auto=auto)

    # 3. Rollback
    rollback = _ask_yn(f"  {style.label('enable rollback?')}", default=False, auto=auto)

    # 4. Graph
    graph_name = None
    if _ask_yn(f"  {style.label('enable knowledge graph?')}", default=False, auto=auto):
        graph_name = _repo_short_name(repo)

    # Preview
    toml_content = _build_toml(repo, wt_dir, rollback, graph_name, graph_repo=repo)
    print()
    print(style.dim("  --- preview ---"))
    for line in toml_content.splitlines():
        print(style.dim(f"  {line}"))
    print(style.dim("  --- end ---"))
    print()

    if not auto:
        if not _ask_yn(f"  Write to {CONFIG_FILENAME}?", default=True):
            print("  Aborted.")
            sys.exit(0)

    with open(dest, "w") as f:
        f.write(toml_content)

    _ensure_git_excluded(repo_root, CONFIG_FILENAME)
    excluded = _is_already_excluded(repo_root, CONFIG_FILENAME)

    # Create .graphifyignore to keep worktrees and other noise out of the graph
    if graph_name:
        ignore_path = os.path.join(repo_root, ".graphifyignore")
        if not os.path.exists(ignore_path):
            with open(ignore_path, "w") as f:
                f.write("# Directories to exclude from the knowledge graph\n")
                f.write(".worktrees/\n")
            _ensure_git_excluded(repo_root, ".graphifyignore")

    # Summary
    print()
    print(style.success(f"{'overwrote' if overwriting else 'created'} {dest}"))
    if graph_name:
        print(f"  {style.label('graph:')}     [graphs.{graph_name}] -> .")
        ignore_path = os.path.join(repo_root, ".graphifyignore")
        if os.path.isfile(ignore_path):
            print(f"  {style.label('ignore:')}    .graphifyignore (excludes .worktrees/)")
    if excluded:
        print(f"  {style.label('git:')}       added '{CONFIG_FILENAME}' to .git/info/exclude")
    next_cmd = f"nd graph build {graph_name}" if graph_name else "nd <command>"
    print(f"  {style.label('next:')}      edit {CONFIG_FILENAME}, then try {style.value(next_cmd)}")
    print()


def _is_already_excluded(repo, entry):
    """Return True if `entry` is on a non-comment line in .git/info/exclude."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repo, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    exclude_path = os.path.join(result.stdout.strip(), "info", "exclude")
    if not os.path.isfile(exclude_path):
        return False
    with open(exclude_path, encoding="utf-8") as f:
        for line in f:
            if line.strip() == entry:
                return True
    return False
