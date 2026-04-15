# Plan: `nd graph` — Graphify integration for nono-dev

## Goal

Add a `graph` command group to nono-dev that builds and queries a Graphify knowledge graph of a target repo (initially `nono`), and makes that graph consumable by sandboxed agents launched via `nd fix`, `nd wt start`, etc.

Per-developer flavor: each dev maintains their own graph on-disk. A pluggable cache-sync hook is specified now but not implemented until the per-dev cost is actually felt.

## Scope

**In scope**
- `nd graph build|update|query|explain|path|status` CLI commands (thin wrappers around `graphify`).
- Per-dev storage layout with a stable, predictable path.
- Config surface for declaring target repos in `nono-dev.toml`.
- Sandbox profile grant so `nd fix`/`nd wt start` sessions can read the graph.
- Prompt updates pointing agents at the graph before exploratory file reads.
- A clearly-defined cache-sync extension point (interface only, no implementation).

**Out of scope (deferred)**
- Shared cache implementation (S3 / git-based / HTTP).
- CI-driven graph regeneration.
- Pushing to Neo4j or running an MCP server.
- Graphify integration inside the Lima VM.
- Upstreaming the graph to the nono repo.

## Prerequisites

- `graphify` binary installed globally (currently via `uv tool install graphifyy`).
- Graph already built at least once per target repo before agents can use it.

The `nd graph build` command should auto-install Graphify if missing, mirroring how `lima.check_installed()` handles Lima.

---

## Command surface

```
nd graph build [target]             # initial build on a configured target
nd graph update [target]            # incremental update
nd graph query "<question>" [-t target] [--dfs] [--budget N]
nd graph explain "<node>" [-t target]
nd graph path "<a>" "<b>" [-t target]
nd graph status                     # list targets + last-updated + node/edge counts
```

`target` resolves to a name from `[graphs.<name>]` in `nono-dev.toml`. Omitted → uses the single configured target, or errors if multiple exist without `--target`.

Completion: `nd graph <TAB>` lists subcommands; `-t <TAB>` lists configured target names.

---

## Config surface

Extend `nono-dev.toml`:

```toml
[graphs.nono]
path = "/Users/scp/dev/nono-repos/nono"
# Optional: override default storage location
# store = "~/.local/share/nono-dev/graphs/nono"
# Optional: extra args to pass to graphify
# extra_args = ["--mode", "deep"]

[graphs.cache_sync]
# Reserved for later; no backend implemented yet.
# backend = "s3"
# bucket  = "..."
```

`[graphs.cache_sync]` exists to nail down the shape now so adding a backend is additive, not breaking.

---

## Storage layout

```
~/.local/share/nono-dev/graphs/<target>/
├── graph.json
├── graph.html
├── GRAPH_REPORT.md
├── cache/              # graphify's semantic cache (per-file content-hashed)
├── cost.json
└── manifest.json
```

Rationale: XDG-ish, outside the target repo, per-target directory. Keeps the target repo clean (no `graphify-out/` checked in or ignored); survives `git clean -fdx`.

---

## Sandbox profile integration

Add to [nono_dev/profiles/nono-dev.json](../../nono_dev/profiles/nono-dev.json):

```json
{
  "filesystem": {
    "read": [
      "$HOME/.local/share/nono-dev/graphs"
    ]
  }
}
```

Single grant covers all targets. Sandboxed agents get read-only access to any graph the host has built.

---

## Prompt integration

Extend existing system prompts ([nono_dev/prompts/fix.md](../../nono_dev/prompts/fix.md), [feature.md](../../nono_dev/prompts/feature.md), [review.md](../../nono_dev/prompts/review.md)) with a section:

```markdown
## Knowledge graph

A Graphify knowledge graph of this project is available at
`~/.local/share/nono-dev/graphs/<repo>/graph.json`. Before doing
exploratory Read/Grep/Glob calls, consult the graph to locate
candidate files, understand call relationships, and surface
design rationale.

Query it via:
  nd graph query "where is credential injection handled?"
  nd graph explain "handle_reverse_proxy"
  nd graph path "ReverseProxyCtx" "CapabilitySet"

Trust `EXTRACTED` edges (confidence 1.0). Treat `INFERRED`
(0.4–0.9) as hints. Verify `AMBIGUOUS` (0.1–0.3) against source.
```

The exact target-name resolution in the prompt is open (see questions).

---

## Cache-sync extension point (interface only)

Define a Python protocol in `nono_dev/graph_sync.py`:

```python
from typing import Protocol
from pathlib import Path

class CacheSync(Protocol):
    def pull(self, cache_dir: Path) -> None:
        """Fetch any remote cache entries into cache_dir. No-op on first use."""

    def push(self, cache_dir: Path) -> None:
        """Upload any local cache entries that aren't already remote."""

def load_from_config(config: dict) -> CacheSync | None:
    """Return a sync backend from [graphs.cache_sync], or None."""
```

`nd graph build` and `nd graph update` call `pull()` before extraction and `push()` after, wrapped in try/except that downgrades failures to a warning. No backends ship initially; `load_from_config` always returns `None`.

---

## Implementation tasks (ordered)

1. **Scaffold the command module** — `nono_dev/commands/graph.py` with subcommand dispatch mirroring `vm_exec.py` / `worktree_cmd.py` patterns. Wire into [nono_dev/cli.py](../../nono_dev/cli.py) and [nono_dev/completions.py](../../nono_dev/completions.py).
2. **Config resolution** — extend `nono_dev/project_config.py` with `get_graph_targets(config)` returning a dict of target → path/store/extra_args.
3. **`nd graph build`** — shell out to `graphify` with the resolved store dir. Auto-install graphify if missing (Homebrew? pipx? `uv tool install graphifyy`?).
4. **`nd graph update`** — same as build but with `--update`.
5. **`nd graph status`** — read `graph.json` + `manifest.json` from each target's store, print a table (target, path, last-updated, node/edge counts).
6. **`nd graph query|explain|path`** — shell through to `graphify` subcommands, pointing at the configured store.
7. **Sandbox profile update** — add `$HOME/.local/share/nono-dev/graphs` to `read`. Update [install.py](../../nono_dev/commands/install.py) if we decide to re-copy the profile on upgrade.
8. **Prompt updates** — add the "Knowledge graph" block to `fix.md`, `feature.md`, `review.md`.
9. **Cache-sync interface** — `nono_dev/graph_sync.py` stub with the protocol, `load_from_config` returning `None`. Hook the `pull`/`push` call sites into build/update.
10. **Docs** — `docs/commands.md` entry for `graph`; `docs/workflows.md` short section on graph-aware fix/feature flows.

Ship order: 1–6 first (CLI works standalone), then 7–8 (agents can use it), then 9 (extension point). 10 alongside.

---

## Open questions

- **Target name resolution in prompts.** The prompt sees a worktree path, not a target name. Two options:
  1. Inject the right graph path into the system prompt at session start (code lookup in `nd fix`/`nd wt start` before the prompt is passed to nono).
  2. Have the prompt itself tell the agent how to find targets (e.g. "run `nd graph status` to see configured targets"). Less surgical, more flexible.
  Leaning (1) for `nd fix` / `nd feature` (we know the repo from config), (2) for ad-hoc `nd wt start` cases.

- **Default target.** Should `nd graph build` with no target build all configured targets, or error? Probably error — one-command-one-action.

- **Graphify version pinning.** `nd graph build` auto-installs graphify if missing, but doesn't upgrade. A schema change in Graphify could silently break everything. Should we record the graphify version in `cost.json` or a new `version.txt` and warn on mismatch?

- **Staleness signal.** Should `nd graph status` also show the git HEAD at last build vs current HEAD for the target repo, so devs know when their graph is behind? Trivial to add.

- **Profile reinstall.** Changing the profile requires `nd install --force` to re-copy. Document this in the PR description, or have `nd graph build` verify the profile has the read grant and warn if not.

---

## Success criteria

- From a fresh checkout of nono-dev, a team member can: `nd install --force`, set up `nono-dev.toml`, run `nd graph build nono`, and within ~2–3 minutes have a working graph.
- Running `nd fix 576` in nono launches a sandboxed agent that can consult the graph — verified by checking whether it reads fewer files when answering "where is X handled?" compared to a non-graph run.
- The cache-sync stub is importable and wired in, even though `load_from_config` returns `None`. Adding an S3 backend later is a ~100-line PR.
