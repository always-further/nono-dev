"""Generate completion candidates for shell tab completion."""

import json
import subprocess


def get_completions(words):
    """Return completion candidates based on the current command line words.

    words is the command line after 'nono-dev', e.g. ['sb', 'attach'] when
    the user has typed 'nono-dev sb attach <TAB>'.
    """
    if not words:
        return _top_level()

    cmd = words[0]

    # Completing the first word
    if len(words) == 1:
        return [c for c in _top_level() if c.startswith(cmd)]

    # Group subcommands -- len 2 means completing the subcommand
    if cmd == "sb":
        subs = ["list", "inspect", "attach", "stop", "prune"]
        if len(words) <= 2:
            prefix = words[1] if len(words) == 2 else ""
            return [s for s in subs if s.startswith(prefix)]
        if words[1] in ("attach", "stop", "inspect"):
            return _session_names()

    if cmd == "wt":
        subs = ["list", "cd", "start", "cleanup"]
        if len(words) <= 2:
            prefix = words[1] if len(words) == 2 else ""
            return [s for s in subs if s.startswith(prefix)]
        if words[1] in ("cd", "start", "cleanup"):
            return _worktree_names()

    if cmd == "vm":
        subs = ["create", "connect", "exec", "status", "mount", "destroy", "recreate"]
        if len(words) <= 2:
            prefix = words[1] if len(words) == 2 else ""
            return [s for s in subs if s.startswith(prefix)]
        if words[1] in ("connect", "destroy", "recreate", "mount", "exec"):
            return _vm_names()

    if cmd == "git":
        subs = ["commit"]
        if len(words) <= 2:
            prefix = words[1] if len(words) == 2 else ""
            return [s for s in subs if s.startswith(prefix)]

    if cmd == "graph":
        subs = ["build", "update", "query", "explain", "path", "status"]
        if len(words) <= 2:
            prefix = words[1] if len(words) == 2 else ""
            return [s for s in subs if s.startswith(prefix)]
        if words[1] in ("build", "update"):
            prefix = words[2] if len(words) >= 3 else ""
            return [t for t in _graph_targets() if t.startswith(prefix)]
        # -t <TAB> for query/explain/path
        last_flag = None
        for i, w in enumerate(words[:-1]):
            if w in ("-t", "--target"):
                last_flag = i
        if last_flag is not None and last_flag == len(words) - 2:
            prefix = words[-1]
            return [t for t in _graph_targets() if t.startswith(prefix)]

    if cmd in ("fix", "triage", "review"):
        return _issue_numbers()

    if cmd == "feature":
        return _worktree_names()

    return []


def _top_level():
    return [
        "triage", "fix", "review", "feature", "bare",
        "vm", "sb", "wt", "git", "graph", "shell-init", "dotfiles",
    ]


def _graph_targets():
    """Read configured graph target names from nono-dev.toml."""
    try:
        from nono_dev import project_config
        config = project_config.load()
        return sorted(project_config.get_graph_targets(config).keys())
    except Exception:
        return []


def _session_names():
    """Get active session names and IDs."""
    try:
        result = subprocess.run(
            ["nono", "ps", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        sessions = json.loads(result.stdout)
        names = []
        for s in sessions:
            if s.get("name"):
                names.append(s["name"])
            if s.get("session_id"):
                names.append(s["session_id"][:6])
        return names
    except Exception:
        return []


def _vm_names():
    """Get Lima VM names."""
    try:
        result = subprocess.run(
            ["limactl", "list", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        names = []
        for line in result.stdout.strip().splitlines():
            vm = json.loads(line)
            if vm.get("name"):
                names.append(vm["name"])
        return names
    except Exception:
        return []


def _worktree_names():
    """Get managed worktree branch names."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        names = []
        for line in result.stdout.splitlines():
            if line.startswith("branch refs/heads/"):
                branch = line.replace("refs/heads/", "").split()[-1]
                if branch not in ("main", "master"):
                    names.append(branch)
        return names
    except Exception:
        return []


def _issue_numbers():
    """Get issue/PR numbers from active sessions."""
    try:
        result = subprocess.run(
            ["nono", "ps", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        sessions = json.loads(result.stdout)
        numbers = set()
        for s in sessions:
            name = s.get("name", "")
            parts = name.rsplit("-", 1)
            if len(parts) == 2 and parts[1].isdigit():
                numbers.add(parts[1])
        return sorted(numbers)
    except Exception:
        return []
