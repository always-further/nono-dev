# Knowledge Graph

nono-dev integrates [Graphify](https://github.com/graphify-ai/graphify) to maintain a per-developer knowledge graph of one or more target repositories. Sandboxed agents launched by `fix`, `feature`, `review`, and `wt start` are pointed at the graph in their system prompt so they can orient themselves without expensive Read/Grep/Glob passes.

## When to use it

- You're working on a codebase large enough that "where is X handled?" costs the agent real tokens.
- You want the agent to understand *relationships* (call sites, type dependencies, module boundaries) instead of just "files containing this string."
- You're indexing more than one repo and want each scoped separately.

Graphify is strongest on code (AST-based extraction yields high-confidence `EXTRACTED` edges). It can also ingest URLs and documents via `graphify add`, but confidence degrades for prose. Treat it as a structure layer, not a full knowledge base.

## Prerequisites

Install Graphify once (host-side, not in the VM):

```bash
uv tool install graphifyy
```

If the profile isn't up to date, agents won't be able to read the graph. Run `nd install --force` after pulling a version of nono-dev that touches `nono_dev/profiles/nono-dev.json` so the read grant for `~/.local/share/nono-dev/graphs` is picked up.

## Configure a target

Add one section per repo to your `nono-dev.toml`:

```toml
[graphs.nono]
path = "~/dev/nono-repos/nono"
# store = "~/.local/share/nono-dev/graphs/nono"  # optional override
# extra_args = ["--mode", "deep"]                # passed through to graphify

[graphs.nono-dev]
path = "~/dev/nono-dev"
```

| Key | Required | Description |
|-----|----------|-------------|
| `path` | Yes | Absolute or user-expanded path to the target repo root. |
| `store` | No | Override the on-disk location for the graph. Defaults to `~/.local/share/nono-dev/graphs/<name>/`. |
| `extra_args` | No | Additional arguments appended to every `graphify update` invocation for this target. |

The reserved `[graphs.cache_sync]` section is a stub for a future shared-cache backend (S3, git, or HTTP). It does nothing today, but the shape is fixed so adding a backend is additive rather than breaking.

## Build the graph

A clean rebuild throws away any existing graph, cache, and cluster state:

```bash
nd graph build              # if only one target is configured
nd graph build nono         # pick a specific target
```

An incremental update re-extracts changed files and reuses the semantic cache:

```bash
nd graph update nono
```

Build and update both warn if the installed `graphify` binary version has changed since the last build (the graph schema may be stale). They'll also warn if the sandbox profile is missing the read grant so agents can't actually see the graph.

If multiple targets are configured and you omit the name, both commands error rather than guess. This is intentional: one command, one target.

## Query the graph

```bash
nd graph query "where is credential injection handled?"
nd graph query "..." -t nono --dfs --budget 4000
```

| Flag | Default | Description |
|------|---------|-------------|
| `-t`, `--target` | sole target | Which configured graph to query. Required when multiple targets exist. |
| `--dfs` | off | Depth-first traversal instead of breadth-first. |
| `--budget N` | `2000` | Cap the response at N tokens. |

Other retrieval shapes:

```bash
nd graph explain "handle_reverse_proxy"         # node + neighbors
nd graph path "ReverseProxyCtx" "CapabilitySet" # shortest path between two nodes
```

Trust `EXTRACTED` edges (confidence 1.0). Treat `INFERRED` (0.4–0.9) as hints. Verify `AMBIGUOUS` (0.1–0.3) against source.

## Check freshness

```bash
nd graph status
```

| Column | Meaning |
|--------|---------|
| `TARGET` | Name from `[graphs.<name>]`. |
| `PATH` | Configured repo root. |
| `STORE` | On-disk location of the graph. |
| `BUILT` | Date of the last `build`/`update`. |
| `HEAD` | Target repo HEAD at build time (short SHA). |
| `BEHIND` | Commits between `HEAD@build` and `HEAD@now`. Non-zero → run `nd graph update`. |
| `NODES` / `EDGES` | Graph size. |
| `VERSION` | Graphify version recorded at build time, flagged if different from the current install. |

## Storage layout

```
~/.local/share/nono-dev/graphs/<target>/
├── manifest.json           # wrapper metadata: graphify_version, built_at,
│                           #   built_head, node/edge counts
└── graphify-out/           # graphify's payload (hardcoded dir name)
    ├── graph.json
    ├── graph.html
    ├── GRAPH_REPORT.md
    ├── cache/
    └── cost.json
```

Graphify resolves its output directory relative to the target-path argument (it writes `<target>/graphify-out/`) and has no `--output` flag, so the wrapper redirects those writes into the store via a symlink. On first build, `<target>/graphify-out` becomes a symlink to `<store>/graphify-out/`, and `graphify-out` is added to `<target>/.git/info/exclude` (a per-clone exclude file that isn't tracked) so `git status` stays clean.

If you already have a real `<target>/graphify-out/` directory from a previous manual `graphify` run, `nd graph build` will migrate its contents into the store on first run (only when the store side is empty). If both sides have content, the build bails and asks you to pick which is authoritative.

Deletions can be as blunt as `rm -rf ~/.local/share/nono-dev/graphs/<target>/` — the symlink in the target repo will then dangle until the next build recreates it.

Each target is fully isolated. There is no cross-target dedup (Graphify's cache is content-hashed per output dir) and no cross-target query (`nd graph query` runs against exactly one `graph.json`).

## Agent integration

When you launch an `nd fix`, `nd feature`, `nd review`, or `nd wt start` session, nono-dev:

1. Determines the source repo from the worktree or current directory (walks to the main-repo root via `git rev-parse --git-common-dir`, so worktrees and subdirectories both work).
2. Looks it up in your configured targets by canonical path.
3. Renders the system prompt, substituting `{{graph_path}}` with the absolute path to `graph.json` (or a clear "no graph configured for this repo" / "graph not built yet" note if unavailable).
4. Launches the sandbox with `~/.local/share/nono-dev/graphs` readable.

Inside the session, the agent can invoke `nd graph query`, `explain`, and `path` directly. The profile read grant covers every configured target with one rule.

## Caveats

- **Single source of truth?** No. Graphify is a structure layer; for fuzzy prose search you'll want embeddings or BM25 alongside. See [`graph-integration.md`](../graph-integration.md) for the "out of scope" list (Neo4j, MCP server, cross-target queries).
- **Version pinning.** `nd graph build` warns on Graphify version mismatch but doesn't hard-pin. Upgrade with intent.
- **Cache sync.** The `CacheSync` protocol is defined in `nono_dev/graph_sync.py`, but `load_from_config` always returns `None`. No backend ships yet.
- **VM builds.** Graphify runs host-side only for now; there is no in-VM integration.
