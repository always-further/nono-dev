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

Wraps the `graphify` CLI into a `nd graph` command group so each developer maintains a per-repo knowledge graph, consumable by sandboxed agents at session launch. Stacked on top of the `feat/sandbox-lima-ssh` PR — this branch depends on the cross-repo fix/triage/review helpers and the profile-install plumbing from that branch.

- `nd graph build | update | query | explain | path | status` — thin wrapper over graphify; graphs live under `~/.local/share/nono-dev/graphs/<target>/`, entirely outside the target repo.
- Session-launch commands (`fix`, `feature`, `review`, `triage`, `wt start`) substitute the resolved graph path into their system prompts so the agent knows where to look before exploratory Read/Grep.
- One-line staleness warning printed to stderr at session launch when the graph is ≥5 commits behind, >7 days old, or not built.
- Sandbox profile grants read on `~/.local/share/nono-dev/graphs`; one rule covers every configured target.
- Per-dev storage only. Cache-sync interface defined (`nono_dev/graph_sync.py`) but no backend ships — adding one later is additive.

## Design notes

- **No symlinks in the target repo.** `graphify-out/` is hardcoded in graphify's output logic, so we invoke `graphify` with `cwd=<store>` and it writes its payload into the store, not the repo. Target repos are never modified; no `.git/info/exclude` edits, nothing under `git status`.
- **Explicit target matching, no silent fallback.** `_match_target` compares the canonical main-repo root (resolved via `git rev-parse --git-common-dir`, so it works from worktrees and subdirs) against configured `[graphs.<name>].path`. If no match is found it returns nothing — silently picking "the only configured target" would mask misconfiguration and, in multi-target setups, inject the wrong graph.
- **Build vs update are semantically distinct.** `nd graph build` wipes `<store>/graphify-out/` first for a real clean rebuild. `nd graph update` leaves it and does an incremental re-extraction.
- **Version + staleness signals.** Each build records `graphify_version`, `built_at`, `built_head` in `manifest.json`. `nd graph status` surfaces all three alongside `commits_behind` (computed at status time via `git rev-list built_head..HEAD`). Version mismatches and non-zero behind-counts are flagged but never auto-fixed.

## Out of scope / deferred

- Shared cache backend (S3 / git / HTTP). The `CacheSync` protocol is defined; `load_from_config` returns `None`.
- CI-driven graph regeneration.
- Neo4j export / MCP server / multi-target queries.
- In-VM graphify integration.
- Version pinning (we warn on mismatch; hard-pin revisited once graphify ships a breaking change).

## Test plan

- [ ] `nd install --force` picks up the new read grant in the profile.
- [ ] Add a `[graphs.<name>]` to `nono-dev.toml` pointing at a checkout; `nd graph build <name>` completes and writes to `~/.local/share/nono-dev/graphs/<name>/graphify-out/`.
- [ ] Target repo stays clean (`git status` shows nothing) during and after `nd graph build`.
- [ ] `nd graph status` shows the target with non-zero node/edge counts, `BEHIND 0`, and the current graphify version.
- [ ] `nd graph query "..."`, `nd graph explain "..."`, `nd graph path "..." "..."` all return results.
- [ ] `nd fix <issue>` (from the main checkout) prints no staleness warning and the rendered system prompt contains the real graph path (verify via `nono inspect` or by looking at the session prompt file).
- [ ] From a worktree or subdirectory of the configured repo, `nd fix` / `nd feature` / `nd wt start` still resolve the graph path correctly (canonical-root logic).
- [ ] On a repo with no `[graphs.*]` match, the prompt placeholder becomes "(no graph configured for this repo)" and no staleness warning fires.
- [ ] Artificially age `manifest.json` (hand-edit `built_at`) and confirm the staleness warning fires at session launch.
- [ ] `uv tool upgrade graphifyy` flagged by `nd graph status` with a version-mismatch note.
- [ ] Completion: `nd graph build no<TAB>` narrows to targets starting with `no`.

---

## Command to open the PR

```bash
# Push the branch if not already:
git push -u origin graphify-integration

gh pr create \
  --repo scp7/nono-dev \
  --base feat/sandbox-lima-ssh \
  --head graphify-integration \
  --title "feat(graph): nd graph command group and session prompt integration" \
  --body-file PR_DRAFT.md
```

Note: if using `--body-file PR_DRAFT.md`, gh will include this whole file. Either strip the header/title/footer sections first, or point `--body-file` at just the body section saved to a separate file.
