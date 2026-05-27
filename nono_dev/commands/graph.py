"""Graphify knowledge-graph commands: build/update/query/explain/path/status.

Thin wrapper around the `graphify` CLI. Each developer maintains their own
graph on-disk under ~/.local/share/nono-dev/graphs/<target>/ (per the
DEFAULT_GRAPH_STORE_ROOT in project_config). The graph is consumable by
sandboxed agents via the read grant in the nono-dev profile.

graphify resolves its output directory relative to the *target path*
argument (it writes `<target>/graphify-out/`), not cwd, and exposes no
--output flag. To keep the per-dev store authoritative without checking
a `graphify-out/` tree into the target repo, we:

  1. Symlink `<target>/graphify-out` -> `<store>/graphify-out/` before
     invoking graphify, so its writes land in the store.
  2. Append `graphify-out` to `<target>/.git/info/exclude` (per-clone,
     not a tracked .gitignore edit) so `git status` stays clean.

`<store>/manifest.json` (our own metadata file) sits alongside the
symlink target, separating wrapper metadata from graphify's payload.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from nono_dev import graph_sync, project_config, style

# PyPI package name for graphify (note the double-y).
GRAPHIFY_PACKAGE = "graphifyy"

# How long to trust a cached "latest version" lookup before refetching.
_LATEST_VERSION_TTL_SECONDS = 24 * 60 * 60

# Where we persist the last PyPI lookup between runs. Kept under the user's
# cache dir (XDG-ish) so `nd graph` doesn't chatter at PyPI on every build.
_VERSION_CACHE_PATH = os.path.expanduser("~/.cache/nono-dev/graphify-latest.json")


# -- argparse wiring ---------------------------------------------------------


def _graph_help(_args):
    print()
    print(style.banner("  nono-dev graph"))
    print()
    print(style.help_row("graph build",   "[target|--all]", "Build the knowledge graph for a target"))
    print(style.help_row("graph update",  "[target|--all]", "Incrementally update the graph"))
    print(style.help_row("graph query",   "<question>",     "Query the graph (BFS traversal)"))
    print(style.help_row("graph explain", "<node>",         "Explain a node and its neighbors"))
    print(style.help_row("graph path",    "<a> <b>",        "Shortest path between two nodes"))
    print(style.help_row("graph ingest",  "[target]",       "Fetch GitHub issues/PRs into the graph corpus"))
    print(style.help_row("graph install", "[--force]",      "Install the graphify package via uv tool"))
    print(style.help_row("graph upgrade", "",               "Upgrade the graphify package via uv tool"))
    print(style.help_row("graph status",  "",               "Show configured targets and freshness"))
    print()
    sys.exit(0)


def add_parser(subparsers):
    graph_parser = subparsers.add_parser("graph", help="Manage the Graphify knowledge graph")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    graph_parser.set_defaults(func=_graph_help)

    # graph build
    build_parser = graph_sub.add_parser("build", help="Build the knowledge graph for a target")
    build_parser.add_argument("target", nargs="?", default=None, help="Target name (from [graphs.<name>])")
    build_parser.add_argument("--all", action="store_true", dest="all_targets",
                              help="Build every configured target")
    build_parser.add_argument("--no-ingest", action="store_true", dest="no_ingest",
                              help="Skip auto-ingest even if configured")
    build_parser.add_argument("--no-version-check", action="store_true", dest="no_version_check",
                              help="Skip the PyPI check for a newer graphify release")
    build_parser.set_defaults(func=run_build)

    # graph update
    update_parser = graph_sub.add_parser("update", help="Incrementally update the graph")
    update_parser.add_argument("target", nargs="?", default=None)
    update_parser.add_argument("--all", action="store_true", dest="all_targets",
                               help="Update every configured target")
    update_parser.add_argument("--no-ingest", action="store_true", dest="no_ingest",
                               help="Skip auto-ingest even if configured")
    update_parser.add_argument("--no-version-check", action="store_true", dest="no_version_check",
                               help="Skip the PyPI check for a newer graphify release")
    update_parser.set_defaults(func=run_update)

    # graph query
    query_parser = graph_sub.add_parser("query", help="Query the graph")
    query_parser.add_argument("question", help="Natural language question")
    query_parser.add_argument("-t", "--target", default=None, help="Target name")
    query_parser.add_argument("--dfs", action="store_true", help="Depth-first traversal")
    query_parser.add_argument("--budget", type=int, default=None, help="Max output tokens")
    query_parser.set_defaults(func=run_query)

    # graph explain
    explain_parser = graph_sub.add_parser("explain", help="Explain a node")
    explain_parser.add_argument("node", help="Node label")
    explain_parser.add_argument("-t", "--target", default=None)
    explain_parser.set_defaults(func=run_explain)

    # graph path
    path_parser = graph_sub.add_parser("path", help="Shortest path between two nodes")
    path_parser.add_argument("a", help="Source node label")
    path_parser.add_argument("b", help="Destination node label")
    path_parser.add_argument("-t", "--target", default=None)
    path_parser.set_defaults(func=run_path)

    # graph ingest
    ingest_parser = graph_sub.add_parser("ingest", help="Fetch GitHub issues and PRs into the graph corpus")
    ingest_parser.add_argument("target", nargs="?", default=None, help="Target name")
    ingest_parser.add_argument("--limit", type=int, default=None, help="Max issues/PRs to fetch (default: all)")
    ingest_parser.add_argument("--no-files", action="store_true", dest="no_files",
                               help="Skip fetching files changed per PR")
    ingest_parser.set_defaults(func=run_ingest)

    # graph install
    install_parser = graph_sub.add_parser("install", help="Install the graphify package via uv tool")
    install_parser.add_argument("--force", action="store_true",
                                help="Reinstall even if graphify is already present")
    install_parser.set_defaults(func=run_install)

    # graph upgrade
    upgrade_parser = graph_sub.add_parser("upgrade", help="Upgrade the graphify package via uv tool")
    upgrade_parser.set_defaults(func=run_upgrade)

    # graph status
    status_parser = graph_sub.add_parser("status", help="Show targets and freshness")
    status_parser.set_defaults(func=run_status)


# -- graphify wrappers -------------------------------------------------------


# graphify 0.5.5's main() crashes on a NameError ('_os' is referenced without
# import) in its tip-printing block, *after* the graph has already been
# rebuilt and written to disk. We treat a non-zero exit as success only when
# all three of these signals are present, so we never swallow a real failure.
_GRAPHIFY_TIP_BUG_STDERR = "NameError: name '_os' is not defined"
_GRAPHIFY_SUCCESS_STDOUT = "graph.json, graph.html and GRAPH_REPORT.md updated"


def _run_graphify_capturing(cmd, cwd):
    """Run graphify, tee its stdout/stderr live, and return (rc, out, err).

    We need both behaviours: the user sees real-time progress (graphify
    update can take a while), and we keep the full text so we can detect
    the known graphify 0.5.5 tip-printing bug after the fact.

    Sets GRAPHIFY_NO_TIPS=1 in the environment as future-proofing: today
    the NameError fires before the env check so it has no effect, but when
    graphify upstream fixes the typo this will skip the buggy code path
    entirely. setdefault means we don't clobber a user override.
    """
    env = dict(os.environ)
    env.setdefault("GRAPHIFY_NO_TIPS", "1")

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    out_buf, err_buf = [], []

    def _pump(src, sink, buf):
        # readline returns "" at EOF; iter(..., "") makes that the stop
        # sentinel. Flushing per-line keeps the live tee responsive.
        for line in iter(src.readline, ""):
            sink.write(line)
            sink.flush()
            buf.append(line)
        src.close()

    t_out = threading.Thread(target=_pump, args=(proc.stdout, sys.stdout, out_buf))
    t_err = threading.Thread(target=_pump, args=(proc.stderr, sys.stderr, err_buf))
    t_out.start()
    t_err.start()
    proc.wait()
    t_out.join()
    t_err.join()

    return proc.returncode, "".join(out_buf), "".join(err_buf)


def _is_graphify_tip_bug(graph_json, stdout_text, stderr_text):
    """True iff this run hit graphify 0.5.5's post-success NameError.

    Requires *all three* signals so the heuristic stays narrow:
      - graph.json was actually written (file exists)
      - graphify printed its end-of-update success line
      - the exact NameError signature is in stderr
    When graphify upstream fixes '_os', the NameError signal disappears
    and this stops matching, so the normal exit-code path takes over.
    """
    return (
        os.path.isfile(graph_json)
        and _GRAPHIFY_SUCCESS_STDOUT in stdout_text
        and _GRAPHIFY_TIP_BUG_STDERR in stderr_text
    )


def _check_graphify_installed():
    """Verify that graphify is available, offering an install hint otherwise."""
    if shutil.which("graphify"):
        return
    print(
        style.error("'graphify' command not found. Install it with:"),
        file=sys.stderr,
    )
    print("  nd graph install", file=sys.stderr)
    print(style.dim(
        f"  (or `uv tool install {GRAPHIFY_PACKAGE}` directly)"
    ), file=sys.stderr)
    sys.exit(1)


def _graphify_version():
    """Return the installed graphify version string, or 'unknown'."""
    # graphify has no --version; try a couple of common forms.
    for flag in ("version", "--version", "-V"):
        try:
            result = subprocess.run(
                ["graphify", flag], capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        out = (result.stdout + result.stderr).strip()
        if result.returncode == 0 and out and "unknown command" not in out:
            return out.splitlines()[0].strip()
    # Fall back to the package version via uv/pipx if installed that way.
    try:
        result = subprocess.run(
            ["uv", "tool", "list"], capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if line.startswith("graphifyy"):
                return line.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _parse_version(raw):
    """Extract a (major, minor, patch) tuple from a version-ish string.

    Accepts any of 'graphifyy v0.5.2', '0.5.2', 'v1.0.0', '1.2.3.dev4+g...'.
    Returns None when no semver-shaped token is present (e.g. 'unknown').
    """
    if not raw:
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", str(raw))
    if not m:
        return None
    try:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _format_version(tup):
    """Render a (major, minor, patch) tuple back as 'x.y.z'."""
    return ".".join(str(n) for n in tup) if tup else "unknown"


def _read_version_cache():
    """Return cached `{version, fetched_at}` dict, or {} on any failure."""
    if not os.path.isfile(_VERSION_CACHE_PATH):
        return {}
    try:
        with open(_VERSION_CACHE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_version_cache(version):
    """Persist the latest-known PyPI version with a fetch timestamp."""
    payload = {
        "version": version,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        os.makedirs(os.path.dirname(_VERSION_CACHE_PATH), exist_ok=True)
        with open(_VERSION_CACHE_PATH, "w") as f:
            json.dump(payload, f)
    except OSError:
        # Cache is a best-effort optimisation; silently ignore write errors.
        pass


def _cache_is_fresh(entry):
    """True when `entry['fetched_at']` is within the TTL window."""
    ts = entry.get("fetched_at")
    if not ts:
        return False
    try:
        fetched = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - fetched).total_seconds()
    return 0 <= age < _LATEST_VERSION_TTL_SECONDS


def _latest_graphify_version(force=False):
    """Return the latest published graphify version string, or None.

    Uses a 24h on-disk cache to stay quiet. Silent on any failure (offline,
    PyPI flake, malformed JSON): the check is advisory, never blocking.
    Pass force=True to bypass the cache (e.g. right after `graph upgrade`).
    """
    if not force:
        cached = _read_version_cache()
        if _cache_is_fresh(cached) and cached.get("version"):
            return cached["version"]

    url = f"https://pypi.org/pypi/{GRAPHIFY_PACKAGE}/json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nono-dev"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None

    version = (data.get("info") or {}).get("version")
    if not version:
        return None
    _write_version_cache(version)
    return version


def _warn_graphify_outdated(skip=False):
    """Warn to stderr if a newer graphify is published on PyPI.

    No-op when `skip` is set, the version lookup fails, or either version
    can't be parsed as semver. Safe to call multiple times per process --
    the PyPI fetch is cached for 24h.
    """
    if skip:
        return
    installed_raw = _graphify_version()
    installed = _parse_version(installed_raw)
    if installed is None:
        # Can't compare; stay silent rather than guess.
        return
    latest_raw = _latest_graphify_version()
    latest = _parse_version(latest_raw)
    if latest is None or latest <= installed:
        return
    print(
        style.warning(
            f"graphify {_format_version(installed)} is installed; "
            f"{_format_version(latest)} is available on PyPI.\n"
            f"  Run `nd graph upgrade && nd graph update --all` to refresh."
        ),
        file=sys.stderr,
    )


def _ensure_store_symlink(target):
    """Wire the target repo's graphify-out to the per-dev store.

    Creates the store dir, symlinks <target>/graphify-out -> <store>/graphify-out,
    and adds graphify-out to the target repo's per-clone git exclude file
    so `git status` stays clean. Returns the store path.

    Handles the migration case where `<target>/graphify-out` is an existing
    real directory (from a previous manual `graphify` invocation): if the
    store is empty, the directory's contents are moved into the store; if
    both exist non-empty, we bail rather than guess which is authoritative.
    """
    store = target["store"]
    repo = target["path"]
    os.makedirs(store, exist_ok=True)

    store_out = os.path.join(store, "graphify-out")
    link = os.path.join(repo, "graphify-out")

    # Case 1: correct symlink already exists.
    if os.path.islink(link):
        if os.path.realpath(link) == os.path.realpath(store_out):
            return store
        # Different symlink target -- replace it.
        os.unlink(link)

    # Case 2: real directory exists in target repo (from a pre-wrapper
    # graphify run, or a previous failed wrapper build). Try to migrate.
    elif os.path.isdir(link):
        store_out_exists = os.path.isdir(store_out) and os.listdir(store_out)
        if store_out_exists:
            print(
                style.error(
                    f"both {link} (real dir) and {store_out} (store) have "
                    f"content. Remove one manually so nd graph can continue:\n"
                    f"  rm -rf {link}          # if the store is authoritative\n"
                    f"  rm -rf {store_out}     # if the in-repo copy is authoritative"
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        # Store empty -- move the in-repo dir into the store, then symlink.
        print(
            style.info(
                f"Migrating existing {link} into {store_out}..."
            ),
            file=sys.stderr,
        )
        if os.path.isdir(store_out):
            shutil.rmtree(store_out)
        shutil.move(link, store_out)
    elif os.path.exists(link):
        print(
            style.error(
                f"{link} exists and is not a directory or symlink; "
                f"remove it so nd graph can manage graphify-out."
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(store_out, exist_ok=True)
    if not os.path.islink(link):
        os.symlink(store_out, link)
    _ensure_git_excluded(repo, "graphify-out")
    return store


def _ensure_git_excluded(repo, entry):
    """Append `entry` to <repo>/.git/info/exclude if not already present.

    Uses the per-clone exclude file so the symlink doesn't pollute
    `git status` and doesn't require a tracked .gitignore change. No-op
    if the repo isn't a git checkout, or the exclude file isn't writable.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=repo, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return
    if result.returncode != 0:
        return
    git_common = result.stdout.strip()
    if not git_common or not os.path.isdir(git_common):
        return
    info_dir = os.path.join(git_common, "info")
    exclude_path = os.path.join(info_dir, "exclude")

    try:
        os.makedirs(info_dir, exist_ok=True)
        existing = ""
        if os.path.isfile(exclude_path):
            with open(exclude_path, encoding="utf-8") as f:
                existing = f.read()
        for line in existing.splitlines():
            if line.strip() == entry:
                return
        prefix = "" if existing.endswith("\n") or not existing else "\n"
        with open(exclude_path, "a", encoding="utf-8") as f:
            f.write(f"{prefix}{entry}\n")
    except OSError as exc:
        print(
            style.warning(
                f"could not update {exclude_path}: {exc} -- "
                f"add '{entry}' to .gitignore or .git/info/exclude manually."
            ),
            file=sys.stderr,
        )


def _graphify_out(store):
    """graphify's output subdirectory inside the store."""
    return os.path.join(store, "graphify-out")


def _graph_json_path(store):
    return os.path.join(_graphify_out(store), "graph.json")


def _cache_dir(store):
    return os.path.join(_graphify_out(store), "cache")


def _profile_has_graph_read():
    """Check whether the installed sandbox profile grants read on the graphs dir."""
    profile_path = os.path.expanduser("~/.config/nono/profiles/nono-dev.json")
    if not os.path.isfile(profile_path):
        return False
    try:
        with open(profile_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    reads = data.get("filesystem", {}).get("read", []) or []
    root = project_config.DEFAULT_GRAPH_STORE_ROOT.rstrip("/")
    # Accept either the $HOME form or the expanded absolute path.
    candidates = {root, "$HOME/.local/share/nono-dev/graphs",
                  os.path.expanduser(root)}
    return any(r.rstrip("/") in candidates for r in reads)


def _profile_preflight():
    if not _profile_has_graph_read():
        print(
            style.warning(
                "sandbox profile missing graph read grant -- sandboxed "
                "agents will not be able to read the graph. Run:\n"
                "  nd install --force"
            ),
            file=sys.stderr,
        )


def _write_manifest(store, target_name, target, graph_json, extra=None):
    """Write manifest.json capturing build metadata."""
    manifest_path = os.path.join(store, "manifest.json")
    node_count, edge_count = _graph_counts(graph_json)
    built_head = _git_rev_parse(target["path"], "HEAD")
    payload = {
        "target": target_name,
        "repo_path": target["path"],
        "graphify_version": _graphify_version(),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "built_head": built_head,
        "node_count": node_count,
        "edge_count": edge_count,
    }
    if extra:
        payload.update(extra)
    try:
        with open(manifest_path, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError as exc:
        print(
            style.warning(f"could not write manifest {manifest_path}: {exc}"),
            file=sys.stderr,
        )


def _graph_counts(graph_json):
    """Return (nodes, edges) from graph.json. (0, 0) on any read failure."""
    if not os.path.isfile(graph_json):
        return 0, 0
    try:
        with open(graph_json) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 0, 0
    nodes = data.get("nodes") or data.get("Nodes") or []
    # graphify writes networkx node_link_data with edges="links"; accept
    # both keys so we stay compatible if that ever changes.
    edges = data.get("links") or data.get("edges") or data.get("Edges") or []
    return len(nodes), len(edges)


def _git_rev_parse(repo_path, ref):
    try:
        result = subprocess.run(
            ["git", "rev-parse", ref],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _commits_behind(repo_path, base_sha):
    if not base_sha:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{base_sha}..HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip() or 0)
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return None


def _read_manifest(store):
    path = os.path.join(store, "manifest.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _warn_version_mismatch(store):
    manifest = _read_manifest(store)
    recorded = manifest.get("graphify_version")
    if not recorded or recorded == "unknown":
        return
    current = _graphify_version()
    if current == "unknown" or current == recorded:
        return
    print(
        style.warning(
            f"graphify version changed since last build "
            f"({recorded} -> {current}); the graph schema may be stale. "
            f"Consider `nd graph build` to regenerate."
        ),
        file=sys.stderr,
    )


# -- command handlers --------------------------------------------------------


def _run_build_or_update(args, *, update):
    _check_graphify_installed()
    config = project_config.load()
    _profile_preflight()
    # PyPI check runs once per invocation, regardless of target count.
    _warn_graphify_outdated(skip=getattr(args, "no_version_check", False))

    all_targets = getattr(args, "all_targets", False)
    if all_targets and args.target:
        print(
            style.error("pass either a target name or --all, not both."),
            file=sys.stderr,
        )
        sys.exit(1)

    if all_targets:
        targets = project_config.get_graph_targets(config)
        if not targets:
            print(
                style.error(
                    "no graph targets configured. Add a [graphs.<name>] "
                    f"section to {project_config.CONFIG_FILENAME}."
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        items = sorted(targets.items())
    else:
        name, target = project_config.resolve_graph_target(config, args.target)
        items = [(name, target)]

    no_ingest = getattr(args, "no_ingest", False)
    failures = []
    for idx, (name, target) in enumerate(items):
        if idx > 0:
            print()  # visual separator between targets
        try:
            _build_or_update_target(config, name, target, update=update, no_ingest=no_ingest)
        except SystemExit as exc:
            # Don't abort the remaining --all targets on a single failure;
            # collect the failure and continue so one stale repo doesn't
            # block the rest.
            if not all_targets:
                raise
            code = exc.code if isinstance(exc.code, int) else 1
            failures.append((name, code))

    if failures:
        summary = ", ".join(f"{n} (exit {c})" for n, c in failures)
        print(style.error(f"failed targets: {summary}"), file=sys.stderr)
        sys.exit(1)


def _build_or_update_target(config, name, target, *, update, no_ingest):
    """Run a single target's build/update. Raises SystemExit on failure."""
    if update:
        _warn_version_mismatch(target["store"])

    # Auto-ingest if configured, unless --no-ingest
    if target.get("ingest") and not no_ingest:
        import argparse as _ap
        ingest_args = _ap.Namespace(target=name, limit=None, no_files=False)
        run_ingest(ingest_args)
        print()

    if not os.path.isdir(target["path"]):
        print(style.error(f"target path does not exist: {target['path']}"), file=sys.stderr)
        sys.exit(1)

    store = _ensure_store_symlink(target)

    # `build` is a clean rebuild: wipe graphify's output dir so no stale
    # graph.json, cache entries, or cluster artefacts survive. `update` is
    # incremental and reuses whatever is already on disk.
    if not update:
        out_dir = _graphify_out(store)
        if os.path.isdir(out_dir):
            try:
                shutil.rmtree(out_dir)
                os.makedirs(out_dir, exist_ok=True)
            except OSError as exc:
                print(
                    style.error(
                        f"could not clear {out_dir} for clean rebuild: {exc}"
                    ),
                    file=sys.stderr,
                )
                sys.exit(1)

    # Cache-sync pull (no-op until a backend is wired up).
    sync = graph_sync.load_from_config(config)
    if sync is not None:
        try:
            sync.pull(Path(_cache_dir(store)))
        except Exception as exc:
            print(style.warning(f"cache sync pull failed: {exc}"), file=sys.stderr)

    # graphify has no explicit "build" subcommand -- running `graphify
    # update <path>` on a fresh store performs the initial extraction.
    cmd = ["graphify", "update", target["path"]]
    cmd.extend(target.get("extra_args", []))

    print(style.info(f"{'Updating' if update else 'Building'} graph for '{name}' at {target['path']}..."))
    print(style.muted(f"  store: {store}"))
    try:
        # cwd=target: graphify resolves `graphify-out/` relative to the
        # *target path* (not cwd), so where we run from doesn't actually
        # matter for output location. We rely on the symlink created by
        # _ensure_store_symlink to redirect writes into the store.
        rc, stdout_text, stderr_text = _run_graphify_capturing(cmd, target["path"])
    except FileNotFoundError:
        print(style.error("graphify not found on PATH"), file=sys.stderr)
        sys.exit(1)

    graph_json = _graph_json_path(store)

    if rc != 0:
        if _is_graphify_tip_bug(graph_json, stdout_text, stderr_text):
            print(style.warning(
                "graphify exited non-zero due to a known tip-printing bug "
                "in 0.5.5 (NameError on '_os'), but the graph was rebuilt "
                "successfully. Treating this run as a success."
            ), file=sys.stderr)
        else:
            print(style.error(f"graphify exited with code {rc}"), file=sys.stderr)
            sys.exit(rc)

    _write_manifest(store, name, target, graph_json)

    if sync is not None:
        try:
            sync.push(Path(_cache_dir(store)))
        except Exception as exc:
            print(style.warning(f"cache sync push failed: {exc}"), file=sys.stderr)

    nodes, edges = _graph_counts(graph_json)
    print(style.success(f"{'Updated' if update else 'Built'} graph for '{name}'"))
    print(f"  {style.label('Graph:')}  {style.value(graph_json)}")
    print(f"  {style.label('Nodes:')}  {style.value(str(nodes))}")
    print(f"  {style.label('Edges:')}  {style.value(str(edges))}")


def run_build(args):
    _run_build_or_update(args, update=False)


def run_update(args):
    _run_build_or_update(args, update=True)


def _invalidate_version_cache():
    """Drop the cached PyPI-latest-version file (best-effort).

    Called after install/upgrade so the next `build`/`update` doesn't nag
    about a "newer" release that we just installed locally.
    """
    try:
        if os.path.isfile(_VERSION_CACHE_PATH):
            os.unlink(_VERSION_CACHE_PATH)
    except OSError:
        pass


def _require_uv():
    """Print an actionable error and exit if `uv` isn't on PATH."""
    if shutil.which("uv"):
        return
    print(
        style.error(
            "'uv' not found. Install uv first "
            "(https://docs.astral.sh/uv/) or manage graphify with "
            f"your preferred tool (e.g. `pipx install {GRAPHIFY_PACKAGE}`)."
        ),
        file=sys.stderr,
    )
    sys.exit(1)


def install_graphify(force=False):
    """Install graphify via `uv tool install graphifyy`.

    Shared by `nd graph install` and `nd install --with-graphify` so both
    paths behave identically: same uv invocation, same cache invalidation,
    same version reporting. Returns the exit code (0 on success, including
    the already-installed skip path when `force` is False).

    When graphify is already on PATH and `force` is False, this is a no-op
    -- important for idempotent `nd install --with-graphify` reruns and for
    not blowing away a user's pipx/brew-managed install.
    """
    _require_uv()

    if not force and shutil.which("graphify"):
        version = _parse_version(_graphify_version())
        if version:
            print(style.muted(
                f"graphify {_format_version(version)} already installed; "
                f"use --force to reinstall."
            ))
        else:
            print(style.muted(
                "graphify already installed; use --force to reinstall."
            ))
        return 0

    cmd = ["uv", "tool", "install", GRAPHIFY_PACKAGE]
    if force:
        cmd.append("--force")
    print(style.info(f"Running: {' '.join(cmd)}"))
    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        print(style.error("uv not found on PATH"), file=sys.stderr)
        return 1

    _invalidate_version_cache()

    if result.returncode != 0:
        return result.returncode

    installed = _parse_version(_graphify_version())
    if installed:
        print(style.success(f"graphify {_format_version(installed)} installed."))
    else:
        print(style.success("graphify installed."))
    return 0


def run_install(args):
    """`nd graph install` handler."""
    sys.exit(install_graphify(force=args.force))


def run_upgrade(_args):
    """Upgrade the graphify package via `uv tool upgrade`.

    Requires `uv` on PATH. If graphify wasn't installed via `uv tool`, the
    upgrade will no-op or error -- we surface uv's exit code in that case
    rather than trying to second-guess pipx/brew/etc. On success we bust the
    PyPI-version cache so the next `build`/`update` reports the new version.
    """
    _check_graphify_installed()
    _require_uv()

    before = _parse_version(_graphify_version())
    cmd = ["uv", "tool", "upgrade", GRAPHIFY_PACKAGE]
    print(style.info(f"Running: {' '.join(cmd)}"))
    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        print(style.error("uv not found on PATH"), file=sys.stderr)
        sys.exit(1)

    _invalidate_version_cache()

    if result.returncode != 0:
        sys.exit(result.returncode)

    after = _parse_version(_graphify_version())
    if before and after and after > before:
        print(style.success(
            f"graphify upgraded {_format_version(before)} -> {_format_version(after)}. "
            f"Run `nd graph update --all` to refresh graphs."
        ))
    elif after:
        print(style.success(f"graphify is at {_format_version(after)}."))


def _graphify_passthrough(args, subcmd, *, extra_cli_args):
    _check_graphify_installed()
    config = project_config.load()
    _, target = project_config.resolve_graph_target(config, getattr(args, "target", None))
    _warn_version_mismatch(target["store"])

    graph_json = _graph_json_path(target["store"])
    if not os.path.isfile(graph_json):
        print(
            style.error(
                f"graph not built for '{target['path']}'. Run `nd graph build` first."
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = ["graphify", subcmd, *extra_cli_args, "--graph", graph_json]
    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        print(style.error("graphify not found on PATH"), file=sys.stderr)
        sys.exit(1)
    sys.exit(result.returncode)


def run_query(args):
    extra = [args.question]
    if args.dfs:
        extra.append("--dfs")
    if args.budget is not None:
        extra.extend(["--budget", str(args.budget)])
    _graphify_passthrough(args, "query", extra_cli_args=extra)


def run_explain(args):
    _graphify_passthrough(args, "explain", extra_cli_args=[args.node])


def run_path(args):
    _graphify_passthrough(args, "path", extra_cli_args=[args.a, args.b])


def run_status(_args):
    config = project_config.load()
    targets = project_config.get_graph_targets(config)
    if not targets:
        print(style.muted("No graph targets configured."))
        print(style.dim(f"  Add a [graphs.<name>] section to {project_config.CONFIG_FILENAME}."))
        return

    current_graphify = _graphify_version()
    headers = ["TARGET", "PATH", "STORE", "BUILT", "HEAD", "BEHIND", "NODES", "EDGES", "VERSION"]
    rows = []
    for name, target in sorted(targets.items()):
        manifest = _read_manifest(target["store"])
        built_at = manifest.get("built_at", "-")
        if built_at != "-" and "T" in built_at:
            built_at = built_at.split("T")[0]
        built_head = manifest.get("built_head")
        short_head = (built_head[:8] if built_head else "-")
        behind = _commits_behind(target["path"], built_head)
        behind_str = "-" if behind is None else str(behind)
        nodes = manifest.get("node_count", "-")
        edges = manifest.get("edge_count", "-")
        recorded_version = manifest.get("graphify_version", "-")
        version_str = recorded_version
        if recorded_version not in ("-", "unknown") and current_graphify not in ("unknown",):
            if recorded_version != current_graphify:
                version_str = style.warning(f"{recorded_version} != {current_graphify}")
        rows.append([
            name, target["path"], target["store"], built_at,
            short_head, behind_str, str(nodes), str(edges), version_str,
        ])

    # Column widths are computed against *visible* cell widths so ANSI-styled
    # cells (e.g. the VERSION mismatch) don't stretch the column.
    widths = [
        max(style.visible_len(r[i]) for r in ([headers] + rows))
        for i in range(len(headers))
    ]
    header_line = "  ".join(
        style.table_header(h.ljust(widths[i])) for i, h in enumerate(headers)
    )
    print(header_line)
    for row in rows:
        line = "  ".join(style.pad_visible(cell, widths[i]) for i, cell in enumerate(row))
        print(line)


# -- ingest: GitHub issues + PRs into the graph corpus ----------------------

INGEST_DIR_NAME = ".nono-dev/github"


def _detect_github_repo(repo_path):
    """Derive org/repo from git remote in a directory.

    Prefers 'upstream' over 'origin' so forks automatically resolve
    to the canonical repo where issues and PRs live.
    """
    import re as _re
    for remote in ("upstream", "origin"):
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", remote],
                capture_output=True, text=True, cwd=repo_path,
            )
            if result.returncode != 0:
                continue
            url = result.stdout.strip()
            m = _re.match(r"git@[^:]+:(.+?)(?:\.git)?$", url)
            if m:
                return m.group(1)
            m = _re.match(r"https?://[^/]+/(.+?)(?:\.git)?$", url)
            if m:
                return m.group(1)
        except (OSError, subprocess.SubprocessError):
            continue
    return None


class GhCommandError(Exception):
    """Raised when a gh CLI command fails."""


def _gh_json(cmd):
    """Run a gh command that returns JSON, return parsed list."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise GhCommandError(result.stderr.strip())
    return json.loads(result.stdout)


def _fetch_issues(repo, limit=None, since=None):
    """Fetch issues (open + closed) from a GitHub repo."""
    lim = str(limit) if limit else "9999"
    cmd = [
        "gh", "issue", "list", "-R", repo,
        "--state", "all", "--limit", lim,
        "--json", "number,title,body,state,labels,comments,assignees,author,createdAt,closedAt",
    ]
    if since:
        cmd.extend(["--search", f"updated:>{since}"])
    return _gh_json(cmd)


def _fetch_prs(repo, limit=None, since=None):
    """Fetch PRs (open + closed + merged) from a GitHub repo."""
    lim = str(limit) if limit else "9999"
    cmd = [
        "gh", "pr", "list", "-R", repo,
        "--state", "all", "--limit", lim,
        "--json", "number,title,body,state,labels,comments,author,createdAt,mergedAt,closedAt,baseRefName,headRefName",
    ]
    if since:
        cmd.extend(["--search", f"updated:>{since}"])
    return _gh_json(cmd)


def _fetch_pr_files(repo, pr_number):
    """Fetch files changed in a PR via the REST API."""
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/pulls/{pr_number}/files",
             "--paginate", "--jq", ".[].filename"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    return []


def _format_issue_md(issue):
    """Format a GitHub issue as rich markdown for graphify extraction."""
    n = issue["number"]
    title = issue.get("title", "")
    state = issue.get("state", "OPEN")
    body = issue.get("body") or ""
    author = issue.get("author", {}).get("login", "unknown")
    created = (issue.get("createdAt") or "")[:10]
    closed = (issue.get("closedAt") or "")[:10]
    labels = ", ".join(l["name"] for l in issue.get("labels", []))
    assignees = ", ".join(a["login"] for a in issue.get("assignees", []))

    lines = [
        f"# Issue #{n}: {title}",
        "",
        f"- **State:** {state}",
        f"- **Author:** @{author}",
        f"- **Created:** {created}",
    ]
    if closed:
        lines.append(f"- **Closed:** {closed}")
    if labels:
        lines.append(f"- **Labels:** {labels}")
    if assignees:
        lines.append(f"- **Assignees:** {assignees}")

    lines.extend(["", "## Description", "", body])

    comments = issue.get("comments", [])
    if comments:
        lines.extend(["", "## Comments", ""])
        for c in comments:
            c_author = c.get("author", {}).get("login", "unknown")
            c_created = (c.get("createdAt") or "")[:10]
            c_body = c.get("body") or ""
            lines.extend([f"### @{c_author} ({c_created})", "", c_body, ""])

    return "\n".join(lines) + "\n"


def _format_pr_md(pr, files=None):
    """Format a GitHub PR as rich markdown for graphify extraction."""
    n = pr["number"]
    title = pr.get("title", "")
    state = pr.get("state", "OPEN")
    body = pr.get("body") or ""
    author = pr.get("author", {}).get("login", "unknown")
    created = (pr.get("createdAt") or "")[:10]
    merged = (pr.get("mergedAt") or "")[:10]
    closed = (pr.get("closedAt") or "")[:10]
    labels = ", ".join(l["name"] for l in pr.get("labels", []))
    base = pr.get("baseRefName", "")
    head = pr.get("headRefName", "")

    lines = [
        f"# PR #{n}: {title}",
        "",
        f"- **State:** {state}",
        f"- **Author:** @{author}",
        f"- **Created:** {created}",
    ]
    if merged:
        lines.append(f"- **Merged:** {merged}")
    elif closed:
        lines.append(f"- **Closed:** {closed}")
    if labels:
        lines.append(f"- **Labels:** {labels}")
    if base and head:
        lines.append(f"- **Branch:** {head} → {base}")

    lines.extend(["", "## Description", "", body])

    if files:
        lines.extend(["", "## Files Changed", ""])
        for f in files:
            lines.append(f"- `{f}`")

    comments = pr.get("comments", [])
    if comments:
        lines.extend(["", "## Comments", ""])
        for c in comments:
            c_author = c.get("author", {}).get("login", "unknown")
            c_created = (c.get("createdAt") or "")[:10]
            c_body = c.get("body") or ""
            lines.extend([f"### @{c_author} ({c_created})", "", c_body, ""])

    return "\n".join(lines) + "\n"


def _ingest_meta_path(ingest_dir):
    return os.path.join(ingest_dir, ".ingest_meta.json")


def _read_ingest_meta(ingest_dir):
    path = _ingest_meta_path(ingest_dir)
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _write_ingest_meta(ingest_dir, meta):
    path = _ingest_meta_path(ingest_dir)
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")


def run_ingest(args):
    config = project_config.load()
    name, target = project_config.resolve_graph_target(config, args.target)
    target_path = target["path"]

    github_repo = target.get("repo") or _detect_github_repo(target_path)
    if not github_repo:
        print(style.error(f"cannot detect GitHub repo from git remote in {target_path}"), file=sys.stderr)
        print(style.dim(f"  Set 'repo' in [graphs.{name}] to specify it explicitly."), file=sys.stderr)
        sys.exit(1)

    if not shutil.which("gh"):
        print(style.error("'gh' CLI not found. Install it: https://cli.github.com"), file=sys.stderr)
        sys.exit(1)

    ingest_dir = os.path.join(target_path, INGEST_DIR_NAME)
    issues_dir = os.path.join(ingest_dir, "issues")
    prs_dir = os.path.join(ingest_dir, "prs")
    os.makedirs(issues_dir, exist_ok=True)
    os.makedirs(prs_dir, exist_ok=True)

    # Exclude from git
    _ensure_git_excluded(target_path, ".nono-dev/")

    # Differential: only fetch items updated since last ingest
    meta = _read_ingest_meta(ingest_dir)
    since = meta.get("last_ingest")
    mode = "incremental" if since else "full"

    print(style.info(f"Ingesting GitHub data for '{name}' from {github_repo}..."))
    if since:
        print(style.muted(f"  incremental: updated since {since}"))
    print()

    # Fetch issues
    print(f"  {style.label('issues:')}    fetching...", end="", flush=True)
    try:
        issues = _fetch_issues(github_repo, limit=args.limit, since=since)
        print(f"\r  {style.label('issues:')}    {len(issues)} {'updated' if since else 'fetched'}")
    except GhCommandError as exc:
        msg = str(exc)
        if "disabled" in msg.lower():
            print(f"\r  {style.label('issues:')}    {style.muted('disabled — skipping')}")
            issues = []
        else:
            print(style.error(f"gh failed: {msg}"), file=sys.stderr)
            sys.exit(1)

    for issue in issues:
        md = _format_issue_md(issue)
        path = os.path.join(issues_dir, f"issue-{issue['number']}.md")
        with open(path, "w") as f:
            f.write(md)

    # Fetch PRs
    print(f"  {style.label('PRs:')}       fetching...", end="", flush=True)
    try:
        prs = _fetch_prs(github_repo, limit=args.limit, since=since)
        print(f"\r  {style.label('PRs:')}       {len(prs)} {'updated' if since else 'fetched'}")
    except GhCommandError as exc:
        msg = str(exc)
        if "disabled" in msg.lower():
            print(f"\r  {style.label('PRs:')}       {style.muted('disabled — skipping')}")
            prs = []
        else:
            print(style.error(f"gh failed: {msg}"), file=sys.stderr)
            sys.exit(1)

    pr_file_count = 0
    if not args.no_files and prs:
        print(f"  {style.label('PR files:')}  fetching...", end="", flush=True)
        for i, pr in enumerate(prs, 1):
            files = _fetch_pr_files(github_repo, pr["number"])
            md = _format_pr_md(pr, files=files)
            path = os.path.join(prs_dir, f"pr-{pr['number']}.md")
            with open(path, "w") as f:
                f.write(md)
            pr_file_count += len(files)
            if i % 10 == 0:
                print(f"\r  {style.label('PR files:')}  {i}/{len(prs)}...", end="", flush=True)
        print(f"\r  {style.label('PR files:')}  {pr_file_count} files across {len(prs)} PRs")
    else:
        for pr in prs:
            md = _format_pr_md(pr)
            path = os.path.join(prs_dir, f"pr-{pr['number']}.md")
            with open(path, "w") as f:
                f.write(md)

    # Update timestamp
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meta["last_ingest"] = now
    meta["repo"] = github_repo
    meta["issue_count"] = meta.get("issue_count", 0) if since else 0
    meta["issue_count"] += len(issues)
    meta["pr_count"] = meta.get("pr_count", 0) if since else 0
    meta["pr_count"] += len(prs)
    _write_ingest_meta(ingest_dir, meta)

    # Summary
    print()
    total_issues = meta["issue_count"]
    total_prs = meta["pr_count"]
    if since:
        print(style.success(f"Updated {len(issues)} issues + {len(prs)} PRs (total on disk: {total_issues} + {total_prs})"))
    else:
        print(style.success(f"Ingested {len(issues)} issues + {len(prs)} PRs into {ingest_dir}"))
    print(f"  {style.label('next:')}  run {style.value(f'nd graph build {name}')} to index code + issues + PRs together")
