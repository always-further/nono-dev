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
    "graphs": {},
}

# Default per-dev store root for Graphify outputs.
DEFAULT_GRAPH_STORE_ROOT = "~/.local/share/nono-dev/graphs"


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


def get_graph_targets(config):
    """Return configured graph targets.

    Parses `[graphs.<name>]` sections from nono-dev.toml, excluding reserved
    subsections like `[graphs.cache_sync]`. Returns a dict mapping target
    name -> {"path": absolute repo path, "store": absolute store dir,
    "extra_args": list of extra args for graphify}.
    """
    reserved = {"cache_sync"}
    graphs = config.get("graphs", {}) or {}
    config_dir = config.get("_config_dir") or os.getcwd()

    targets = {}
    for name, raw in graphs.items():
        if name in reserved:
            continue
        if not isinstance(raw, dict):
            continue
        path = raw.get("path")
        if not path:
            print(
                f"Warning: [graphs.{name}] missing required 'path' key; skipping.",
                file=sys.stderr,
            )
            continue
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.join(config_dir, path)

        store = raw.get("store")
        if store:
            store = os.path.expanduser(store)
            if not os.path.isabs(store):
                store = os.path.join(config_dir, store)
        else:
            store = os.path.join(
                os.path.expanduser(DEFAULT_GRAPH_STORE_ROOT), name,
            )

        extra_args = list(raw.get("extra_args", []) or [])

        targets[name] = {
            "path": os.path.abspath(path),
            "store": os.path.abspath(store),
            "extra_args": extra_args,
        }
    return targets


def resolve_graph_target(config, name=None):
    """Resolve a target by name, or the sole target if none given.

    Returns (name, target_dict). Exits with an error if the selection is
    ambiguous or the name is unknown.
    """
    targets = get_graph_targets(config)
    if not targets:
        print(
            "Error: no graph targets configured. Add a [graphs.<name>] "
            f"section to {CONFIG_FILENAME}.",
            file=sys.stderr,
        )
        sys.exit(1)

    if name is None:
        if len(targets) == 1:
            only = next(iter(targets))
            return only, targets[only]
        names = ", ".join(sorted(targets))
        print(
            f"Error: multiple graph targets configured ({names}); "
            "pass -t <name> to choose one.",
            file=sys.stderr,
        )
        sys.exit(1)

    if name not in targets:
        names = ", ".join(sorted(targets)) or "(none)"
        print(
            f"Error: unknown graph target '{name}'. Configured: {names}.",
            file=sys.stderr,
        )
        sys.exit(1)
    return name, targets[name]


def graph_store_root():
    """Absolute path to the default per-dev graph store root."""
    return os.path.abspath(os.path.expanduser(DEFAULT_GRAPH_STORE_ROOT))


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


def get_rendered_prompt_path(name, config, substitutions=None):
    """Return a path to a prompt file with {{placeholders}} substituted.

    Reads the prompt (override or shipped), applies literal `{{key}}`
    replacements, and writes the result to a temp file. Returns that path.
    If no substitutions are provided, falls back to get_prompt_path.
    """
    if not substitutions:
        return get_prompt_path(name, config)

    src_path = get_prompt_path(name, config)
    try:
        with open(src_path, encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        print(f"Error: could not read prompt {src_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    for key, val in substitutions.items():
        content = content.replace("{{" + key + "}}", str(val))

    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".md", prefix=f"nono-prompt-{name}-")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return tmp_path


def _canonical_repo_root(path):
    """Resolve `path` to its main-repo root via git, or None.

    Works from a worktree, a subdirectory of a worktree, or the main repo
    itself. Uses `git rev-parse --git-common-dir` which points at the
    shared .git directory (the main worktree's .git), regardless of where
    we're called from.
    """
    import subprocess
    if not path or not os.path.isdir(path):
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=path, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    common_git = result.stdout.strip()
    if not common_git:
        return None
    # --git-common-dir returns <main-repo>/.git (or a bare path). Parent is
    # the main repo root for the common non-bare case.
    root = os.path.dirname(common_git) if common_git.endswith("/.git") or os.path.basename(common_git) == ".git" else common_git
    if not os.path.isdir(root):
        return None
    return os.path.realpath(root)


def _match_target(config, repo_hint):
    """Resolve a repo hint to a (name, target) pair, or (None, None).

    Matches the canonical main-repo root (via git) against the `path`
    value of each configured `[graphs.<name>]` section. Never falls
    back to "the only configured target" -- silent guessing masks
    misconfiguration and can inject the wrong graph in multi-target
    setups.
    """
    if not repo_hint:
        return None, None
    targets = get_graph_targets(config)
    if not targets:
        return None, None
    canonical = _canonical_repo_root(repo_hint) or os.path.realpath(repo_hint)
    for name, t in targets.items():
        if os.path.realpath(t["path"]) == canonical:
            return name, t
    return None, None


def graph_path_for_prompt(config, repo_hint=None):
    """Return a human-readable line describing the graph for a target repo.

    repo_hint can be any path inside the caller's repo (worktree,
    subdirectory, or the repo root). It's resolved to the main-repo root
    via git and matched against configured `[graphs.<name>].path` values.
    If no match is found the prompt degrades gracefully.
    """
    if not get_graph_targets(config):
        return "(no graph configured for this repo)"

    _, match = _match_target(config, repo_hint)
    if match is None:
        return "(no graph configured for this repo)"

    # graphify writes its payload under <store>/graphify-out/.
    graph_json = os.path.join(match["store"], "graphify-out", "graph.json")
    if not os.path.isfile(graph_json):
        return f"(graph not built yet; run `nd graph build` to create {graph_json})"
    return graph_json


# Staleness thresholds for the session-launch warning.
_GRAPH_STALE_BEHIND_COMMITS = 5
_GRAPH_STALE_DAYS = 7


def graph_staleness_warning(config, repo_hint=None):
    """Return a one-line staleness warning for the configured graph, or None.

    Designed for session-launch callers (fix/feature/review/wt start) that
    inject the graph path into the system prompt. Returns None when there
    is nothing to say -- either no configured target matches the caller's
    repo, or the graph is fresh enough. The caller prints to stderr.

    Triggers a warning when:
      - the target matches but no graph has been built yet, or
      - BEHIND >= 5 commits on the target repo, or
      - the graph was built more than 7 days ago.
    """
    name, target = _match_target(config, repo_hint)
    if target is None:
        return None

    store = target["store"]
    graph_json = os.path.join(store, "graphify-out", "graph.json")
    if not os.path.isfile(graph_json):
        return (
            f"graph for '{name}' is not built -- agent prompt has a "
            f"placeholder instead of a real graph path. "
            f"Run `nd graph build {name}` to create it."
        )

    manifest = _read_graph_manifest(store)
    built_head = manifest.get("built_head")
    built_at = manifest.get("built_at")

    behind = _graph_commits_behind(target["path"], built_head)
    age_days = _graph_age_days(built_at)

    reasons = []
    if behind is not None and behind >= _GRAPH_STALE_BEHIND_COMMITS:
        reasons.append(f"{behind} commits behind")
    if age_days is not None and age_days > _GRAPH_STALE_DAYS:
        reasons.append(f"last built {age_days} days ago")

    if not reasons:
        return None

    return (
        f"graph for '{name}' is stale ({'; '.join(reasons)}). "
        f"Run `nd graph update {name}` to refresh."
    )


def _read_graph_manifest(store):
    """Read <store>/manifest.json; return {} on any failure."""
    import json
    path = os.path.join(store, "manifest.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _graph_commits_behind(repo_path, base_sha):
    """Commits from base_sha to HEAD of repo_path, or None."""
    import subprocess
    if not base_sha or not repo_path or not os.path.isdir(repo_path):
        return None
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{base_sha}..HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip() or 0)
    except ValueError:
        return None


def _graph_age_days(built_at):
    """Days since the ISO timestamp in built_at, or None."""
    if not built_at:
        return None
    from datetime import datetime, timezone
    try:
        # Support "Z" suffix and "+00:00" forms.
        raw = built_at.replace("Z", "+00:00")
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - ts
    return max(0, delta.days)


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
