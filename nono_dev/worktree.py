"""Git worktree operations."""

import os
import subprocess
import sys


def add(branch, path, cwd=None):
    """Create a new git worktree with a new branch.

    Returns the absolute path to the created worktree.
    """
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    result = subprocess.run(
        ["git", "worktree", "add", "-b", branch, abs_path],
        capture_output=True, text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        msg = result.stderr.strip()
        if "already exists" in msg:
            return None
        print(f"Error creating worktree: {msg}", file=sys.stderr)
        sys.exit(1)

    return abs_path


def list_worktrees(cwd=None):
    """List all git worktrees, returning a list of dicts.

    Each dict has keys: path, branch, head.

    Returns an empty list if ``cwd`` is provided but no longer exists on
    disk (e.g. a session whose project directory has been deleted).
    """
    # subprocess.run raises FileNotFoundError if cwd is missing, which
    # would otherwise crash callers like `nd sb list`. Treat a missing
    # cwd the same as "no worktrees here".
    if cwd is not None and not os.path.isdir(cwd):
        return []

    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        return []

    worktrees = []
    current = {}
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[len("worktree "):]}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            ref = line[len("branch "):]
            current["branch"] = ref.replace("refs/heads/", "")
        elif line == "":
            if current:
                worktrees.append(current)
                current = {}

    if current:
        worktrees.append(current)

    return worktrees


def remove(path, force=False, cwd=None):
    """Remove a git worktree."""
    cmd = ["git", "worktree", "remove", path]
    if force:
        cmd.append("--force")

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        msg = result.stderr.strip()
        print(f"Error removing worktree: {msg}", file=sys.stderr)
        sys.exit(1)


def diff_stat(path):
    """Return (additions, deletions) line counts for uncommitted changes."""
    result = subprocess.run(
        ["git", "-C", path, "diff", "--numstat", "HEAD"],
        capture_output=True, text=True,
    )
    additions = 0
    deletions = 0
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            try:
                additions += int(parts[0])
                deletions += int(parts[1])
            except ValueError:
                continue

    return additions, deletions


def has_changes(path):
    """Check if a worktree has uncommitted changes."""
    result = subprocess.run(
        ["git", "-C", path, "status", "--porcelain"],
        capture_output=True, text=True,
    )
    return bool(result.stdout.strip())


def delete_branch(branch, cwd=None):
    """Delete a local git branch."""
    subprocess.run(
        ["git", "branch", "-d", branch],
        capture_output=True, text=True,
        cwd=cwd,
    )
