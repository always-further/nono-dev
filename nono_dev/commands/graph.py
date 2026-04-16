"""Graphify knowledge-graph commands: build/update/query/explain/path/status.

Thin wrapper around the `graphify` CLI. Each developer maintains their own
graph on-disk under ~/.local/share/nono-dev/graphs/<target>/ (per the
DEFAULT_GRAPH_STORE_ROOT in project_config). The graph is consumable by
sandboxed agents via the read grant in the nono-dev profile.

graphify writes its outputs to `<cwd>/graphify-out/` by default and has no
--output flag. To keep the target repo untouched, we invoke graphify with
cwd=<store>/ and pass the repo path as the argument, so graphify's output
lands at <store>/graphify-out/. Our own manifest.json sits one level up at
<store>/manifest.json, separating wrapper metadata from graphify's payload.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from nono_dev import graph_sync, project_config, style


# -- argparse wiring ---------------------------------------------------------


def _graph_help(_args):
    print()
    print(style.banner("  nono-dev graph"))
    print()
    print(f"    {style.value('graph build'):<40} {style.muted('[target]')}       {style.dim('Build the knowledge graph for a target')}")
    print(f"    {style.value('graph update'):<40} {style.muted('[target]')}       {style.dim('Incrementally update the graph')}")
    print(f"    {style.value('graph query'):<40} {style.muted('<question>')}      {style.dim('Query the graph (BFS traversal)')}")
    print(f"    {style.value('graph explain'):<40} {style.muted('<node>')}          {style.dim('Explain a node and its neighbors')}")
    print(f"    {style.value('graph path'):<40} {style.muted('<a> <b>')}         {style.dim('Shortest path between two nodes')}")
    print(f"    {style.value('graph status'):<40}                 {style.dim('Show configured targets and freshness')}")
    print()
    sys.exit(0)


def add_parser(subparsers):
    graph_parser = subparsers.add_parser("graph", help="Manage the Graphify knowledge graph")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    graph_parser.set_defaults(func=_graph_help)

    # graph build
    build_parser = graph_sub.add_parser("build", help="Build the knowledge graph for a target")
    build_parser.add_argument("target", nargs="?", default=None, help="Target name (from [graphs.<name>])")
    build_parser.set_defaults(func=run_build)

    # graph update
    update_parser = graph_sub.add_parser("update", help="Incrementally update the graph")
    update_parser.add_argument("target", nargs="?", default=None)
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

    # graph status
    status_parser = graph_sub.add_parser("status", help="Show targets and freshness")
    status_parser.set_defaults(func=run_status)


# -- graphify wrappers -------------------------------------------------------


def _check_graphify_installed():
    """Verify that graphify is available, offering an install hint otherwise."""
    if shutil.which("graphify"):
        return
    print(
        "Error: 'graphify' command not found. Install it with:\n"
        "  uv tool install graphifyy",
        file=sys.stderr,
    )
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


def _ensure_store_dir(target):
    """Create the per-target store directory and return its path.

    The store is a plain directory outside the target repo. graphify is
    invoked with cwd=<store>, so its `graphify-out/` payload lands inside
    the store, not inside the repo.
    """
    store = target["store"]
    os.makedirs(store, exist_ok=True)
    return store


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
    edges = data.get("edges") or data.get("Edges") or []
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
    name, target = project_config.resolve_graph_target(config, args.target)
    _profile_preflight()
    if update:
        _warn_version_mismatch(target["store"])

    if not os.path.isdir(target["path"]):
        print(style.error(f"target path does not exist: {target['path']}"), file=sys.stderr)
        sys.exit(1)

    store = _ensure_store_dir(target)

    # `build` is a clean rebuild: wipe graphify's output dir so no stale
    # graph.json, cache entries, or cluster artefacts survive. `update` is
    # incremental and reuses whatever is already on disk.
    if not update:
        out_dir = _graphify_out(store)
        if os.path.isdir(out_dir):
            try:
                shutil.rmtree(out_dir)
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
        # cwd=store so graphify writes <store>/graphify-out/ instead of
        # polluting the target repo with a graphify-out/ directory.
        result = subprocess.run(cmd, cwd=store)
    except FileNotFoundError:
        print(style.error("graphify not found on PATH"), file=sys.stderr)
        sys.exit(1)
    if result.returncode != 0:
        print(style.error(f"graphify exited with code {result.returncode}"), file=sys.stderr)
        sys.exit(result.returncode)

    graph_json = _graph_json_path(store)
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

    # Simple column-aligned print (mirrors sandbox_status style without importing).
    widths = [max(len(_strip_ansi(r[i])) for r in ([headers] + rows)) for i in range(len(headers))]
    header_line = "  ".join(style.table_header(h.ljust(widths[i])) for i, h in enumerate(headers))
    print(header_line)
    for row in rows:
        line = "  ".join(_pad_visible(cell, widths[i]) for i, cell in enumerate(row))
        print(line)


def _strip_ansi(s):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", str(s))


def _pad_visible(s, width):
    """Left-pad a possibly-ANSI-styled string to `width` visible characters."""
    visible_len = len(_strip_ansi(s))
    pad = max(0, width - visible_len)
    return f"{s}{' ' * pad}"
