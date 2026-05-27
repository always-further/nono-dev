"""Thin wrapper around the nono sandbox CLI."""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


# GitHub repo used for the "is nono outdated?" check.
_NONO_REPO = "always-further/nono"
# How long to trust the cached "latest release" lookup before refetching.
_VERSION_CACHE_TTL = 24 * 60 * 60  # 24h on success
_NEGATIVE_CACHE_TTL = 5 * 60       # 5min after a failed fetch (don't hammer the API)


def _nono_cmd():
    """Return the nono executable to invoke.

    Honors NONO_BIN_PATH so users with a shell-level switcher (e.g. a
    `nono-use` function flipping between cargo and brew installs) get
    consistent behavior here. Subprocesses can't see shell aliases or
    functions, so without this every call would resolve via PATH and
    silently bypass the user's selection. Falls back to "nono" (PATH
    lookup) when the env var is unset or points at something missing
    or non-executable.
    """
    explicit = os.environ.get("NONO_BIN_PATH")
    if explicit and os.path.isfile(explicit) and os.access(explicit, os.X_OK):
        return explicit
    return "nono"

# Known agent CLI conventions. Any key can be overridden via [agent] config.
#
# `profile` is the nono SANDBOX profile (passed to `nono run --profile`),
# not the agent binary. Each agent has its own profile that extends the
# matching pack (nono-dev-claude extends claude, nono-dev-codex extends
# codex). This ensures each agent gets the grants its pack defines (e.g.
# ~/.codex r+w for codex) plus the shared nono-dev overlays (~/.lima,
# graphs dir). Upstream's default is "claude-code"; we override here so
# sandboxed `nd` keeps working.
#
# `subcommand` is an optional first arg between the binary and the
# prompt/flags. Used for agents whose non-interactive mode is gated
# behind a subcommand (e.g. codex 0.133+ requires `codex exec PROMPT`
# rather than `codex PROMPT`).
_AGENT_DEFAULTS = {
    "claude": {
        "profile": "nono-dev-claude",
        "subcommand": None,
        "auto_approve_flag": "--dangerously-skip-permissions",
        "extra_flags": [],
        "system_prompt_flag": "--system-prompt",
    },
    "codex": {
        "profile": "nono-dev-codex",
        # No subcommand: interactive TUI mode. `codex exec` is one-shot
        # and exits immediately; we want the session to stay open for
        # the user to attach to.
        "subcommand": None,
        # Skip codex's internal approval prompts and its own sandboxing —
        # nono is the real sandbox. Intended for exactly this use case.
        "auto_approve_flag": "--dangerously-bypass-approvals-and-sandbox",
        # nono-dev-codex extends the codex pack which grants ~/.codex r+w
        # via the codex_macos group, so --ephemeral is not needed.
        "extra_flags": [],
        # Codex has no --system-prompt flag. The system prompt content is
        # prepended to the initial user prompt and passed as a positional
        # arg, giving codex the workflow context as its opening message.
        "system_prompt_flag": None,
    },
}

_AGENT_FALLBACK = {
    "profile": "nono-dev-claude",
    "subcommand": None,
    "auto_approve_flag": None,
    "extra_flags": [],
    "system_prompt_flag": None,
}


def get_agent_config(config, override_binary=None):
    """Resolve agent settings from project config with known-agent defaults.

    `override_binary` (typically `args.agent` from a launcher's `--agent`
    flag) takes precedence over `[agent].binary` in nono-dev.toml. This
    is how the per-session override (e.g. `nd review 42 --agent codex`
    in an otherwise claude-configured repo) gets applied.
    """
    agent_cfg = config.get("agent", {})
    binary = override_binary or agent_cfg.get("binary", "claude")
    known = _AGENT_DEFAULTS.get(binary, _AGENT_FALLBACK)
    return {
        "binary": binary,
        "profile": agent_cfg.get("profile") or known["profile"],
        "subcommand": agent_cfg.get("subcommand") or known.get("subcommand"),
        "auto_approve_flag": agent_cfg.get("auto_approve_flag") or known.get("auto_approve_flag"),
        "extra_flags": agent_cfg.get("extra_flags") or known.get("extra_flags") or [],
        "system_prompt_flag": agent_cfg.get("system_prompt_flag") or known.get("system_prompt_flag"),
    }


def add_agent_select_args(parser):
    """Register `--agent NAME` on a launcher to override which CLI is invoked.

    Lets a single repo run cross-agent workflows without editing
    `nono-dev.toml`: e.g. a repo defaulting to claude can use
    `nd review 42 --agent codex` to have codex review a PR claude
    worked on. Falls back to `[agent].binary` config when omitted,
    then to "claude". Unknown agent names fall through to the
    minimal fallback profile (no auto-approve / no system-prompt
    flag) and will fail at exec if the binary isn't installed --
    that's intentional, so new agents can be tried without code
    changes.
    """
    parser.add_argument(
        "--agent", default=None, metavar="NAME",
        help="Override the inner agent CLI for this session "
             "(e.g. claude, codex). Defaults to [agent].binary "
             "in nono-dev.toml, then 'claude'.",
    )


def agent_name_suffix(config, override_binary):
    """Return `-<agent>` suffix when override differs from the configured
    default; `''` otherwise.

    Lets cross-agent sessions on the same target coexist: a
    `nd review 42` session and a `nd review 42 --agent codex`
    session get different names (`review-42` vs `review-42-codex`)
    and don't collide in the duplicate-session check.

    Returns `''` when no override is set, or when the override
    matches the configured default (a no-op override shouldn't
    rename anything).
    """
    if not override_binary:
        return ""
    configured = config.get("agent", {}).get("binary", "claude")
    if override_binary == configured:
        return ""
    return f"-{override_binary}"


def check_installed():
    """Verify that the nono CLI is available."""
    if not _nono_available():
        print(
            "Error: 'nono' command not found. Install nono first: "
            "https://docs.nono.sh/cli/getting_started/installation",
            file=sys.stderr,
        )
        sys.exit(1)
    _warn_if_outdated()


def _nono_available():
    """True if a nono binary can be located via NONO_BIN_PATH or PATH."""
    cmd = _nono_cmd()
    # Absolute path: presence already validated by _nono_cmd.
    if os.path.isabs(cmd):
        return True
    return shutil.which(cmd) is not None


def _warn_if_outdated():
    """Print a one-line advisory if a newer nono release exists.

    Fails open on any error: a missing version, network failure, or
    parse error never blocks the command. Set NONO_DEV_SKIP_VERSION_CHECK=1
    to silence the check entirely.
    """
    if os.environ.get("NONO_DEV_SKIP_VERSION_CHECK"):
        return
    installed = _installed_version()
    latest = _latest_version()
    if installed is None or latest is None:
        return
    if installed >= latest:
        return
    inst_str = ".".join(str(p) for p in installed)
    latest_str = ".".join(str(p) for p in latest)
    print(
        f"Warning: nono {inst_str} is installed but {latest_str} is available.\n"
        f"  Update: https://docs.nono.sh/cli/getting_started/installation\n"
        f"  Silence: NONO_DEV_SKIP_VERSION_CHECK=1",
        file=sys.stderr,
    )


def _installed_version():
    """Return the installed nono version as a (major, minor, patch) tuple."""
    try:
        result = subprocess.run(
            [_nono_cmd(), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    if result.returncode != 0:
        return None
    # Try stdout first, fall back to stderr.
    return _parse_version(result.stdout) or _parse_version(result.stderr)


def _parse_version(text):
    """Extract the first X.Y.Z found in text as a tuple of ints."""
    if not text:
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def _latest_version():
    """Return the latest published nono release as a tuple, or None."""
    path = _cache_path()
    cached = _read_cache(path)
    if cached is not None:
        # Cache is fresh; return its value (which may be None on a recent failure).
        return cached["version"]

    version = _fetch_latest_version()
    _write_cache(path, version)
    return version


def _cache_path():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "nono-dev", "nono-latest.json")


def _read_cache(path):
    """Return {'version': tuple|None} if the cache entry is still fresh."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    fetched_at = data.get("fetched_at", 0)
    version_str = data.get("version") or ""
    ttl = _VERSION_CACHE_TTL if version_str else _NEGATIVE_CACHE_TTL
    if time.time() - fetched_at > ttl:
        return None
    return {"version": _parse_version(version_str)}


def _write_cache(path, version):
    """Persist the lookup result. Both successes and failures are cached."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        version_str = ".".join(str(p) for p in version) if version else ""
        with open(path, "w") as f:
            json.dump({"version": version_str, "fetched_at": time.time()}, f)
    except OSError:
        pass


def _fetch_latest_version():
    """Hit the GitHub releases API; return None on any failure."""
    url = f"https://api.github.com/repos/{_NONO_REPO}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "nono-dev",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError, ValueError):
        return None
    return _parse_version(data.get("tag_name", ""))


def run_detached(
    name,
    *,
    agent_config=None,
    allows=None,
    reads=None,
    allow_cwd=False,
    system_prompt=None,
    user_prompt=None,
    rollback=None,
    workdir=None,
    agent_args=None,
):
    """Run a command inside nono in detached mode.

    `agent_args` is an iterable of extra arguments forwarded verbatim to
    the inner coding-agent invocation (today: `claude`). Use this for
    agent-specific flags like `--resume <session-id>` that nono-dev
    doesn't want to hard-code. Args are inserted between the system
    prompt and the optional user prompt so the agent's own positional
    argument (if any) still comes last.

    Returns the session ID parsed from nono's output.
    """
    agent = agent_config or _AGENT_DEFAULTS["claude"]
    profile = agent["profile"]
    binary = agent.get("binary", "claude")
    subcommand = agent.get("subcommand")
    auto_approve_flag = agent.get("auto_approve_flag")
    extra_flags = agent.get("extra_flags") or []
    system_prompt_flag = agent.get("system_prompt_flag")

    if profile == "nono-dev":
        profile_path = os.path.expanduser("~/.config/nono/profiles/nono-dev.json")
        if not os.path.isfile(profile_path):
            print(
                "nono-dev profile not installed. Run: nd install --force",
                file=sys.stderr,
            )
            sys.exit(1)

    # Editable installs of nono-dev import from this source tree. Grant read
    # access so `nd` works from inside any sandbox session.
    nono_dev_src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    extra_reads = [nono_dev_src]

    cmd = [_nono_cmd(), "run", "--detached", "--name", name, "--profile", profile]

    # Skip large directory trees during trust scan and rollback preflight
    for skip in ["node_modules", "target", ".venv", "__pycache__", ".next"]:
        cmd.extend(["--skip-dir", skip])

    if rollback is None or rollback.get("enabled", True):
        cmd.append("--rollback")
        excludes = rollback.get("exclude", []) if rollback else []
        for pattern in excludes:
            cmd.extend(["--rollback-exclude", pattern])

    for path in allows or []:
        cmd.extend(["--allow", path])

    for path in (reads or []) + extra_reads:
        cmd.extend(["--read", path])

    if allow_cwd:
        cmd.append("--allow-cwd")

    if workdir:
        cmd.extend(["--workdir", workdir])

    cmd.append("--")
    cmd.append(binary)
    if subcommand:
        cmd.append(subcommand)
    if auto_approve_flag:
        cmd.append(auto_approve_flag)
    if extra_flags:
        cmd.extend(extra_flags)

    # User-supplied agent args (`nd bare -- --resume <id>`) go before the
    # prompt so they're parsed as options by the agent CLI, not as part
    # of the positional user prompt.
    if agent_args:
        cmd.extend(agent_args)

    prompt_content = None
    if system_prompt:
        with open(system_prompt) as f:
            prompt_content = f.read()

    if system_prompt_flag and prompt_content:
        cmd.extend([system_prompt_flag, prompt_content])
        if user_prompt:
            cmd.append(user_prompt)
    elif prompt_content:
        # Agent has no --system-prompt flag; prepend to the user prompt.
        merged_prompt = f"{prompt_content}\n\n{user_prompt}" if user_prompt else prompt_content
        cmd.append(merged_prompt)
    elif user_prompt:
        cmd.append(user_prompt)

    result = subprocess.run(cmd, capture_output=True, text=True)

    # nono may write session info to either stdout or stderr
    combined = (result.stdout + "\n" + result.stderr).strip()

    if result.returncode != 0:
        print(f"Error starting nono session: {combined}", file=sys.stderr)
        sys.exit(1)

    session_id = _parse_session_id(combined)
    if not session_id:
        print(f"Warning: could not parse session ID from nono output:", file=sys.stderr)
        print(f"  stdout: {result.stdout.strip()}", file=sys.stderr)
        print(f"  stderr: {result.stderr.strip()}", file=sys.stderr)

    return session_id


def _parse_session_id(output):
    """Extract session ID from nono run --detached output.

    Expected format:
        Started detached session 764dce.
        Name: test-parse
        Attach with: nono attach 764dce
    """
    import re
    for line in output.strip().splitlines():
        # "Started detached session <id>."
        m = re.match(r"Started detached session (\S+?)\.?$", line.strip())
        if m:
            return m.group(1)
        # "Attach with: nono attach <id>"
        m = re.match(r"Attach with: nono attach (\S+)", line.strip())
        if m:
            return m.group(1)
    return output.strip()


def ps_json(include_all=True):
    """List nono sessions as parsed JSON."""
    cmd = [_nono_cmd(), "ps", "--json"]
    if include_all:
        cmd.append("--all")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []

    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return []


def attach(session_id):
    """Attach to a running nono session. Replaces the current process."""
    cmd = _nono_cmd()
    os.execvp(cmd, [cmd, "attach", session_id])


# -- pass-through argparse helpers -------------------------------------------
#
# Every `nd` launcher (bare/fix/feature/review/triage) sets up a fixed
# baseline of `--allow` / `--read` paths for the sandbox (project root,
# worktree, .git/, etc.). Users sometimes need to grant an additional
# path for a specific session -- e.g. a sibling repo they want to let
# Claude read while fixing a cross-cutting issue. Rather than hard-code
# those paths into the config or require a code change, expose them as
# repeatable CLI flags that forward 1:1 to `nono run --allow`/`--read`.
#
# Helpers live here (next to `run_detached`) so the argparse surface and
# the subprocess-call shape stay in sync. Adding a new pass-through flag
# is: extend `add_sandbox_pass_through_args`, extend the normaliser, and
# extend `run_detached`'s kwargs.


def add_sandbox_pass_through_args(parser):
    """Register `--allow PATH` and `--read PATH` on a launcher's argparse.

    Both are repeatable. Paths are stored in `args.extra_allows` and
    `args.extra_reads` verbatim; callers should normalise via
    `normalize_sandbox_paths()` before handing them to `run_detached`.
    """
    parser.add_argument(
        "--allow", action="append", dest="extra_allows", default=[],
        metavar="PATH",
        help="Grant read+write on an additional path inside the sandbox. "
             "Forwarded to `nono run --allow`. Repeatable.",
    )
    parser.add_argument(
        "--read", action="append", dest="extra_reads", default=[],
        metavar="PATH",
        help="Grant read-only access to an additional path inside the sandbox. "
             "Forwarded to `nono run --read`. Repeatable.",
    )


def normalize_sandbox_paths(args):
    """Expand `~` and resolve relative paths for `--allow` / `--read` inputs.

    Returns `(extra_allows, extra_reads)` as absolute paths. Missing attrs
    default to empty lists so this is safe to call on any args namespace.
    """
    def _norm(paths):
        return [os.path.abspath(os.path.expanduser(p)) for p in paths or []]
    return (
        _norm(getattr(args, "extra_allows", None)),
        _norm(getattr(args, "extra_reads", None)),
    )


# -- agent-args passthrough --------------------------------------------------
#
# Launchers spawn an inner coding agent (today `claude`, but the design
# is intentionally agent-agnostic so the project can swap implementations
# without a CLI rename). Users sometimes need to pass an agent-specific
# flag, e.g. `claude --resume <session-id>` to pick up a prior chat.
# Hard-coding every such flag into nono-dev is fragile, so we forward
# anything after a literal `--` on the launcher's command line:
#
#   nd bare myname -- --resume abc123
#   nd wt start mybranch -- --resume abc123
#
# Splitting happens BEFORE argparse parses (see `cli.py`), so launcher
# flags (`--no-rollback`, `--allow`, ...) work naturally and the agent
# args are never accidentally consumed as launcher flags. The split is
# scoped to agent-launcher subcommands so commands like `vm exec --`
# (which relies on argparse's standard `--` handling for its own
# positional command) keep working unchanged.
#
# `_AGENT_LAUNCHER_COMMANDS` enumerates which subcommands opt in. A
# nested-subcommand entry is encoded as "group/sub" (e.g. "wt/start").


_AGENT_LAUNCHER_COMMANDS = frozenset({
    "bare", "fix", "feature", "review", "triage",
    "wt/start", "invariants/draft",
})


def split_agent_args(argv, launcher_commands=_AGENT_LAUNCHER_COMMANDS):
    """Split argv at a standalone `--` for agent-launcher subcommands.

    Returns `(front, agent_args)`. If `argv` does not target an agent
    launcher or has no standalone `--`, returns `(argv, [])` so other
    subcommands keep argparse's default `--` semantics.

    Detects nested subcommands ("wt start", "invariants draft") by
    examining the first two non-flag tokens.
    """
    if "--" not in argv:
        return argv, []

    # Find the first two non-flag positional tokens to identify the
    # subcommand. `argv[0]` is the program name; skip it.
    positionals = []
    for tok in argv[1:]:
        if tok == "--":
            break
        if not tok.startswith("-"):
            positionals.append(tok)
            if len(positionals) == 2:
                break

    if not positionals:
        return argv, []

    cmd = positionals[0]
    nested = f"{cmd}/{positionals[1]}" if len(positionals) > 1 else None

    if cmd in launcher_commands or (nested and nested in launcher_commands):
        idx = argv.index("--")
        return argv[:idx], argv[idx + 1:]

    return argv, []


def get_agent_args(args):
    """Return the agent-args list attached to an argparse Namespace.

    Safe to call on any namespace; returns `[]` when the attribute is
    missing or empty. Launchers should pass this to
    `run_detached(..., agent_args=...)`.
    """
    return list(getattr(args, "agent_args", None) or [])
