"""Project configuration from nono-dev.toml."""

import importlib.resources
import os
import sys
import tomllib

CONFIG_FILENAME = "nono-dev.toml"

DEFAULTS = {
    "project": {"repo": None},
    "worktree": {"dir": ".worktrees"},
    "rollback": {"enabled": False, "dest": None, "exclude": []},
    "prompts": {},
}


def load(start_dir=None):
    """Find and parse nono-dev.toml, walking up from start_dir.

    Returns a dict with defaults filled in. Returns defaults if no
    config file is found.
    """
    search_dir = os.path.abspath(start_dir or os.getcwd())
    config_path = _find_config(search_dir)

    if config_path is None:
        config = {}
    else:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

    merged = {}
    for section, defaults in DEFAULTS.items():
        merged[section] = dict(defaults)
        if section in config:
            merged[section].update(config[section])

    merged["_config_dir"] = os.path.dirname(config_path) if config_path else search_dir
    return merged


def _find_config(start_dir):
    """Walk up directories looking for nono-dev.toml."""
    current = start_dir
    while True:
        candidate = os.path.join(current, CONFIG_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def get_repo(config):
    """Return the org/repo string.

    Checks the config first, then falls back to deriving from the git
    remote origin URL.
    """
    repo = config["project"].get("repo")
    if repo:
        return repo

    repo = _repo_from_git_remote()
    if repo:
        return repo

    print(
        f"Error: could not determine repo. Set 'repo' in [project] "
        f"section of {CONFIG_FILENAME}, or add a git remote named 'origin'.",
        file=sys.stderr,
    )
    sys.exit(1)


def _repo_from_git_remote():
    """Derive org/repo from the git remote origin URL."""
    import re
    import subprocess

    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None

    url = result.stdout.strip()

    # SSH: git@github.com:org/repo.git
    m = re.match(r"git@[^:]+:(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)

    # HTTPS: https://github.com/org/repo.git
    m = re.match(r"https?://[^/]+/(.+?)(?:\.git)?$", url)
    if m:
        return m.group(1)

    return None


def parse_github_ref(value):
    """Parse a GitHub issue/PR number from a number or URL.

    Accepts:
        "576"
        "https://github.com/org/repo/issues/576"
        "https://github.com/org/repo/pull/576"

    Returns the number as an int, or exits with an error.
    """
    import re
    # Plain number
    if value.isdigit():
        return int(value)

    # GitHub URL
    m = re.match(
        r"https?://github\.com/[^/]+/[^/]+/(?:issues|pull)/(\d+)",
        value,
    )
    if m:
        return int(m.group(1))

    print(
        f"Error: '{value}' is not a valid issue/PR number or GitHub URL.",
        file=sys.stderr,
    )
    sys.exit(1)


def get_worktree_dir(config):
    """Return the absolute path to the worktree directory."""
    wt_dir = config["worktree"]["dir"]
    if os.path.isabs(wt_dir):
        return wt_dir
    return os.path.join(config["_config_dir"], wt_dir)


def get_project_root(config, start_dir=None):
    """Return the git top-level directory, or fall back to the config dir."""
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=start_dir or os.getcwd(),
    )
    if result.returncode == 0:
        root = result.stdout.strip()
        if root:
            return root
    return config["_config_dir"]


def get_rollback(config):
    """Return rollback settings dict: enabled, dest, exclude."""
    rb = dict(config["rollback"])
    if rb.get("dest"):
        rb["dest"] = os.path.expanduser(rb["dest"])
        if not os.path.isabs(rb["dest"]):
            rb["dest"] = os.path.join(config["_config_dir"], rb["dest"])
    return rb


def get_prompt_path(name, config):
    """Return the path to a system prompt file.

    If the config overrides the prompt, resolve relative to the config dir.
    Otherwise, write the shipped default to a temp location and return that path.
    """
    override = config["prompts"].get(name)
    if override:
        path = override
        if not os.path.isabs(path):
            path = os.path.join(config["_config_dir"], path)
        if not os.path.isfile(path):
            print(f"Error: prompt file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path

    return _shipped_prompt_path(name)


def _shipped_prompt_path(name):
    """Return the path to a shipped prompt file."""
    ref = importlib.resources.files("nono_dev.prompts").joinpath(f"{name}.md")
    # importlib.resources may return a traversable that is already a real path
    # on disk (editable install) or needs as_file() (wheel install).
    path = str(ref)
    if os.path.isfile(path):
        return path
    # Fallback: extract to a context-managed temp file is not ideal for
    # long-running detached processes. Instead, read and write to a temp file.
    import tempfile
    content = ref.read_text(encoding="utf-8")
    fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix=f"nono-prompt-{name}-")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return tmp_path
