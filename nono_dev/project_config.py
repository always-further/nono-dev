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

    Returns the number as an int. Use parse_github_ref_full() if you also
    need the repo (org/name) extracted from a URL.
    """
    _, number = parse_github_ref_full(value)
    return number


def parse_github_ref_full(value):
    """Parse a GitHub issue/PR ref.

    Accepts:
        "576"                                                -> (None, 576)
        "https://github.com/org/repo/issues/576"             -> ("org/repo", 576)
        "https://github.com/org/repo/pull/576"               -> ("org/repo", 576)
        "https://github.com/org/repo.git/issues/576"         -> ("org/repo", 576)

    Returns (repo, number) where `repo` is None when the input was a plain
    number. Exits with a friendly error on invalid input.
    """
    import re
    if value.isdigit():
        return (None, int(value))

    m = re.match(
        r"https?://github\.com/([^/]+/[^/]+?)(?:\.git)?/(?:issues|pull)/(\d+)",
        value,
    )
    if m:
        return (m.group(1), int(m.group(2)))

    print(
        f"Error: '{value}' is not a valid issue/PR number or GitHub URL.",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_session_name(name):
    """Parse a session name produced by the fix/triage/review/feature flows.

    Returns (kind, slug, ref):
      - kind:   "fix" | "triage" | "review" | "feature" | None
      - slug:   repo slug (e.g. "nono-py") from cross-repo sessions, or None
      - ref:    issue/PR number as int for fix/triage/review,
                branch name (str) for feature, None otherwise.

    Examples:
      "fix-42"               -> ("fix",     None,      42)
      "fix-nono-py-42"       -> ("fix",     "nono-py", 42)
      "triage-nono-go-7"     -> ("triage",  "nono-go", 7)
      "review-530"           -> ("review",  None,      530)
      "feat-my-feature"      -> ("feature", None,      "my-feature")
      "random"               -> (None,      None,      None)
    """
    import re
    for kind in ("fix", "triage", "review"):
        m = re.match(rf"^{kind}-(?:(.+)-)?(\d+)$", name)
        if m:
            slug, number = m.groups()
            return (kind, slug, int(number))

    m = re.match(r"^feat-(.+)$", name)
    if m:
        return ("feature", None, m.group(1))

    return (None, None, None)


def session_name_to_branch(name):
    """Map a fix/feature session name back to its worktree branch name.

    Mirrors the `xrepo-` reserved prefix used by `branch_to_fix_session`.
    Returns None if the session isn't associated with a worktree.
    """
    kind, slug, ref = parse_session_name(name)
    if kind == "fix":
        return f"xrepo-{slug}-issue-{ref}" if slug else f"issue-{ref}"
    if kind == "feature":
        return ref
    return None


def branch_to_fix_session(branch):
    """Map a fix-worktree branch name to its session name.

    Branch conventions produced by `nd fix`:
      issue-<N>                      -> fix-<N>             (same repo)
      xrepo-<slug>-issue-<N>         -> fix-<slug>-<N>      (cross repo)

    The `xrepo-` prefix is reserved: user-chosen feature branches that
    happen to contain "-issue-<N>" (e.g. "docs-issue-42") are NOT matched,
    so `wt start` correctly launches them as feature sessions.

    Returns None if `branch` doesn't look like a fix worktree.
    """
    import re
    m = re.match(r"^issue-(\d+)$", branch)
    if m:
        return f"fix-{m.group(1)}"
    m = re.match(r"^xrepo-(.+)-issue-(\d+)$", branch)
    if m:
        slug, number = m.groups()
        return f"fix-{slug}-{number}"
    return None


def namespace_slug(url_repo, current_repo):
    """Return a dash-safe slug for branch/session naming when an issue URL
    points at a different repo than the current worktree, or "" otherwise.

    Examples:
        ("always-further/nono-py", "always-further/nono") -> "nono-py"
        (None, "always-further/nono")                     -> ""
        ("always-further/nono", "always-further/nono")    -> ""
    """
    if not url_repo or url_repo == current_repo:
        return ""
    return url_repo.split("/", 1)[1]


def get_worktree_dir(config):
    """Return the absolute path to the worktree directory."""
    wt_dir = config["worktree"]["dir"]
    if os.path.isabs(wt_dir):
        return wt_dir
    return os.path.join(config["_config_dir"], wt_dir)


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
