# PR Draft

**Target:** `scp7/nono-dev`
**Base branch:** `feat/sandbox-lima-ssh`
**Head branch:** `graphify-integration`

---

## Title

```
feat(graph): nd graph command group and session prompt integration
```

---

## Body

## Summary

Wraps the `graphify` CLI into a `nd graph` command group so each developer maintains a per-repo knowledge graph, consumable by sandboxed agents at session launch. Stacked on top of the `feat/sandbox-lima-ssh` PR — this branch depends on the cross-repo fix/triage/review helpers and the profile-install plumbing from that branch. Bumps version to 0.1.4.

- `nd graph build | update | query | explain | path | status` — thin wrapper over graphify; graphs live under `~/.local/share/nono-dev/graphs/<target>/`, entirely outside the target repo (see Design notes for the symlink mechanism).
- Session-launch commands (`fix`, `feature`, `review`, `triage`, `wt start`) substitute the resolved graph path into their system prompts so the agent knows where to look before exploratory Read/Grep.
- One-line staleness warning printed to stderr at session launch when the graph is ≥5 commits behind, >7 days old, or not built.
- Sandbox profile grants read on `~/.local/share/nono-dev/graphs`; one rule covers every configured target.
- Per-dev storage only. Cache-sync interface defined (`nono_dev/graph_sync.py`) but no backend ships — adding one later is additive.

## Design notes

- **graphify-out lives outside the target repo, via a symlink.** Graphify hardcodes its output directory relative to the target path argument (it writes `<target>/graphify-out/`) and has no `--output` flag. To keep the per-dev store authoritative without checking anything into the target repo, the wrapper symlinks `<target>/graphify-out` → `<store>/graphify-out/` before invoking graphify, and appends `graphify-out` to `<target>/.git/info/exclude` (per-clone, untracked). Git sees nothing in `git status`, nothing in diffs, nothing in commits — one symlink entry exists in the repo root as the only visible artefact. Existing real `<target>/graphify-out/` directories (from a pre-wrapper manual `graphify` invocation) are migrated into the store on first build when the store is empty; if both sides have content, the build bails with a clear "remove one manually" message.
- **Explicit target matching, no silent fallback.** `_match_target` compares the canonical main-repo root (resolved via `git rev-parse --git-common-dir`, so it works from worktrees and subdirs) against configured `[graphs.<name>].path`. If no match is found it returns nothing — silently picking "the only configured target" would mask misconfiguration and, in multi-target setups, inject the wrong graph.
- **Build vs update are semantically distinct.** `nd graph build` wipes `<store>/graphify-out/` first for a real clean rebuild. `nd graph update` leaves it and does an incremental re-extraction (graphify reuses its content-hashed cache).
- **Version + staleness signals.** Each build records `graphify_version`, `built_at`, and `built_head` in `manifest.json`. `nd graph status` surfaces all three alongside `commits_behind` (computed at status time via `git rev-list built_head..HEAD`). Version mismatches and non-zero behind-counts are flagged but never auto-fixed.
- **Edge counting.** Graphify writes `graph.json` via networkx `node_link_data(edges="links")`, so `_graph_counts` looks for the `"links"` key first (with `"edges"` / `"Edges"` as fallbacks for robustness).

## Out of scope / deferred

- Shared cache backend (S3 / git / HTTP). The `CacheSync` protocol is defined; `load_from_config` returns `None`.
- CI-driven graph regeneration.
- Neo4j export / MCP server / multi-target queries.
- In-VM graphify integration.
- Version pinning (we warn on mismatch; hard-pin revisited once graphify ships a breaking change).

## Test plan

Verified locally against `always-further/nono` (≈115 source files, 3428 nodes, 6394 edges):

- [x] `nd install --force` installs v0.1.4 and copies the updated sandbox profile (with the graph read grant) to `~/.config/nono/profiles/nono-dev.json`.
- [ ] `nd install --with-graphify` installs nono-dev *and* runs `uv tool install graphifyy`; rerunning it skips the graphify step with "already installed". `nd install --with-graphify --force` reinstalls both. `nd graph install` on its own has the same skip/force semantics and is a no-op when graphify is already present via pipx/brew.
- [x] Add a `[graphs.<name>]` to `nono-dev.toml` pointing at a checkout; `nd graph build <name>` creates `<store>/graphify-out/graph.json` and the `<target>/graphify-out` symlink, appends `graphify-out` to `<target>/.git/info/exclude`.
- [x] Target repo stays clean (`git status` shows nothing) during and after build/update.
- [x] `nd graph status` shows the target with correct node/edge counts, `BEHIND 0`, and the current graphify version.
- [ ] `nd graph query "..."`, `nd graph explain "..."`, `nd graph path "..." "..."` all return results.
- [ ] `nd fix <issue>` (from the main checkout) prints no staleness warning and the rendered system prompt contains the real graph path (verify via `nono inspect` or by looking at the session prompt file).
- [ ] From a worktree or subdirectory of the configured repo, `nd fix` / `nd feature` / `nd wt start` still resolve the graph path correctly (canonical-root logic).
- [ ] On a repo with no `[graphs.*]` match, the prompt placeholder becomes "(no graph configured for this repo)" and no staleness warning fires.
- [ ] Artificially age `manifest.json` (hand-edit `built_at` or rewrite `built_head` to an older SHA) and confirm the staleness warning fires at session launch.
- [ ] After `uv tool upgrade graphifyy`, `nd graph status` flags the version mismatch.
- [ ] When a newer `graphifyy` is published on PyPI, `nd graph build`/`update` warn once and suggest `nd graph upgrade && nd graph update --all`. The warning stays quiet for 24h via `~/.cache/nono-dev/graphify-latest.json`, and `--no-version-check` skips the lookup entirely.
- [ ] `nd graph upgrade` runs `uv tool upgrade graphifyy`, clears the version cache, and reports the before→after version. `nd graph update --all` then rebuilds every configured target and reports a combined summary if any target fails.
- [ ] Completion: `nd graph build no<TAB>` narrows to targets starting with `no`.
- [ ] Migration path: start with a real `<target>/graphify-out/` dir and an empty store, run `nd graph update <name>`, confirm the contents move into the store and the symlink replaces the directory.

---

## Command to open the PR

```bash
# Push the branch (first time) or re-push after rebase:
git push -u origin graphify-integration
# or, after history-rewriting rebase:
git push --force-with-lease origin graphify-integration

gh pr create \
  --repo scp7/nono-dev \
  --base feat/sandbox-lima-ssh \
  --head graphify-integration \
  --title "feat(graph): nd graph command group and session prompt integration" \
  --body-file /tmp/pr-body.md
```

Extract just the body section into `/tmp/pr-body.md` so the PR doesn't include this framing:

```bash
awk '/^## Body$/{flag=1; next} /^---$/{if(flag){exit}} flag' PR_DRAFT.md > /tmp/pr-body.md
```
