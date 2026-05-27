<!--
  This file is mirrored at nono_dev/prompts/invariants_draft.md so the
  packaged `nd invariants draft` launcher can ship it as a system prompt.
  Keep both files byte-identical when editing. The HTML comment is
  preserved in the prompt copy too.
-->
---
name: invariants-init
description: >
  Bootstrap a real `invariants.yaml` for a graphify-enabled repository.
  Combines the knowledge graph (`nd graph` queries and explanations) with
  codebase context (AGENTS.md / CLAUDE.md, architecture docs, lint config,
  existing `// invariant` comments, test patterns) to draft a curated set of
  load-bearing rules grouped by subsystem, then validates the result.
trigger: /draft-invariants
---

# /draft-invariants

Two entry points, same behaviour:

- **Interactive** — inside an agent session, `/draft-invariants` (no args).
- **Headless** — from any shell, run inside a sandboxed worktree (`nd bare`
  or `nd feature`) and invoke this skill via the slash command.

The goal is to leave the repo with a `proj/invariants.yaml` (the
draft-phase path) that **validates green**, **cites real source docs**,
and **groups entries by subsystem** in the same shape as a hand-written
file. The user then curates and promotes it to `docs/invariants.yaml`.

## Preconditions

- Current working directory is a checkout of the target repo.
- `nd`, `rg`, and `gh` are on `PATH`.
- A graphify knowledge graph is available — verify with `nd graph status`. If absent, advise the user to run `nd graph build` first; the skill can still proceed without one but with reduced fidelity (graph queries return nothing, so subsystem discovery falls back to manual reading).
- Active graph path (substituted by `nd` when this skill is launched as a system prompt): `{{graph_path}}`. If empty, fall back to `graphify-out/graph.json` under cwd.
- `yq` and `jq` recommended for re-validating without a Python interpreter; `nd invariants validate` covers the common path.

**Silent degradation**: every input source below is optional. If a file is absent, skip the corresponding signal — never fabricate citations. Cite only paths and anchors that exist on disk.

## Step 1 — Decide the target file

```bash
# Prefer the draft-phase path so we don't clobber a curated docs/ file.
if   [ -f docs/invariants.yaml ]; then TARGET=proj/invariants.yaml; CURATED_EXISTS=1
elif [ -f proj/invariants.yaml ]; then TARGET=proj/invariants.yaml; CURATED_EXISTS=0
else                                    TARGET=proj/invariants.yaml; CURATED_EXISTS=0
fi
```

If `docs/invariants.yaml` already exists, **never overwrite it**. Always write the draft to `proj/invariants.yaml` and tell the user to diff against the curated file before promoting.

If `proj/invariants.yaml` already exists, ask the user whether to append, replace, or read-and-extend. Default to **read-and-extend** — load the existing entries, keep their `id`s stable, and only add new ones.

## Step 2 — Read existing context

Read these in order; skip any that don't exist. Keep the file paths and heading anchors handy — they become `source:` citations later.

1. **`AGENTS.md` / `CLAUDE.md`** — the most reliable source of project-wide rules (check for both; prefer `AGENTS.md` if present, fall back to `CLAUDE.md`). Many existing invariants cite these files as `source:`. Read fully.
2. **`README.md`** — high-level "this project is a security tool" framing, often surfaces top-priority rules.
3. **`docs/architecture/` or `proj/ARCHITECTURE*.md`** — design docs. Headings often phrase invariants directly ("the library vs CLI split is a load-bearing invariant"). Glob for `*.md` and read each.
4. **Existing `// invariant <id>:` comments** — the project may already mark rules in code:
   ```bash
   rg -n '(?i)//[\s/]*invariant[:\s]' --type-add 'src:*.{rs,py,ts,go,java,c,cpp,h,hpp}' -t src
   ```
   Each match is *evidence* that the project has a rule worth lifting into the file. The comment usually carries the `id`.
5. **Lint / format config** — encoded rules. Read whichever apply:
   - Rust: `clippy.toml`, `.clippy.toml`, `Cargo.toml` (`[lints.clippy]`), `rust-toolchain.toml`. Look for `unwrap_used = "deny"`, `panic = "deny"`, `dbg_macro`, etc.
   - Python: `pyproject.toml` (`[tool.ruff.lint]`), `.ruff.toml`, `mypy.ini`, `setup.cfg`. Look for strict mode flags.
   - TypeScript: `eslint.config.*`, `tsconfig.json` (`strict: true`).
   - Each enforced rule is a candidate invariant of `severity: medium`.
6. **CI config** — `.github/workflows/`, `Makefile`, `justfile`. Required checks (DCO sign-off, `make ci`, `cargo audit`) become `severity: low` process invariants.
7. **Recent issues/PRs labelled `security`, `bug`, `regression`** — surface footguns that the codebase has already paid for. Use:
   ```bash
   gh issue list --state all --label security --limit 50 --json number,title,body,url
   gh pr list   --state all --search 'in:title fix CVE OR security' --limit 50 --json url,title
   ```
   Each recurring footgun is a candidate `severity: high` invariant.

## Step 3 — Map the architecture with `nd graph`

Confirm the graph is fresh:

```bash
nd graph status
```

If `BEHIND > 20` or `BUILT` is more than 14 days old, advise running `nd graph update` before continuing.

Then use the graph to discover subsystems and load-bearing types:

```bash
# Open-ended seed query; use the answer to identify the dominant clusters.
nd graph query "What are the load-bearing types, modules, or rules in this codebase?"

# Subsystem vocabulary — feeds the `subsystems:` arrays.
nd graph query "What subsystems or major components exist in this codebase, in plain English?"

# Per-subsystem deep dive — repeat for each subsystem the previous step named.
nd graph explain "<central-type-or-module>"

# Bridge nodes — high-betweenness types are usually invariant carriers.
# These often appear in the graphify report:
cat graphify-out/GRAPH_REPORT.md 2>/dev/null | grep -A5 -i 'betweenness\|bridge'
```

Use community labels from `graphify-out/.graphify_labels.json` if present; else use the dominant type names. Each community typically maps to 1-3 invariants.

## Step 4 — Cluster findings into themes

Group every signal collected in Steps 2 and 3 into themes. The themes from a real well-formed file are a good starting point — adapt them to what this repo actually has:

| Theme | Typical signals |
| --- | --- |
| **Structural** | "The library vs CLI split", "X is mutable in parent / immutable in child", architectural separation rules |
| **Path / IO handling** | canonicalize-at-grant-and-enforcement, Path::starts_with vs string prefix, env-var validation |
| **Platform-specific** | Linux vs macOS divergences, sandbox capability differences |
| **Coding standards** | clippy / ruff enforcements, no-unwrap, unsafe-confined-to-FFI, must-use |
| **Secrets / credentials** | zeroize, never-log, never-persist-cleartext |
| **Testing discipline** | env save/restore, every-new-X-needs-tests, no flaky parallel tests |
| **IPC / concurrency** | peer authentication, bounded framing, message-size caps |
| **Process / CI** | DCO sign-off, required checks, commit policy |

Drop any theme that has no signals. Add new themes only if the repo's signals genuinely don't fit the list above.

## Step 5 — Draft entries

For each signal, draft one entry against the schema (`nono_dev/schemas/invariants.schema.json`):

- **`id`**: kebab-case, descriptive, stable (`lib-policy-free`, `path-canonicalize`). 3-60 chars. Match `^[a-z][a-z0-9-]*[a-z0-9]$`.
- **`subsystems`**: 2-6 plain-English tags. Use the language a contributor would use in an issue, not graphify community ids. **Be generous** — overlap is fine; missing tags hurts triage matching.
- **`statement`**: one to three sentences. **Actionable**, not vague. Include a concrete failure example where it sharpens the rule. 20-1500 chars.
  - Good: *"Library code must not call .unwrap() on values originating from user input. Propagate errors via Result; reserve panics for unreachable conditions."*
  - Bad: *"Handle errors well."*
- **`source`**: cite the file you actually read. Two forms:
  - `path/to/doc.md#anchor` (relative to repo root; anchor is the doc's heading slug).
  - `https://...` (GitHub issue, RFC, CVE, upstream doc).
  - **Never invent paths.** If you can't cite a real doc for a rule, write the rule into a doc first (`proj/INVARIANTS-NOTES.md`), then cite it.
- **`severity`**:
  - `high` — security hole, data-loss bug, correctness regression.
  - `medium` — API contract, testing discipline, platform-specific behaviour.
  - `low` — style, ergonomics, process.
- **`added`**: today's date in `YYYY-MM-DD`.
- **`tags`** (optional): cross-cutting labels (`security`, `performance`, `api-stability`).
- **`related`** (optional): list of other ids that travel together. Use sparingly.

Aim for 15-30 entries on a first pass. Fewer than ~10 means you stopped too early; more than ~50 dilutes signal.

## Step 6 — Write the file

Use the `nd invariants init` template as a structural starting point if `$TARGET` doesn't exist:

```bash
[ -f "$TARGET" ] || nd invariants init "$TARGET"
```

Then **replace the example entries** with the entries you drafted, preserving the header prose and section dividers. Adapt the section dividers to the themes from Step 4.

If `$TARGET` exists and the user asked to extend rather than replace:

1. Read the existing entries (note their `id`s).
2. Append your new entries under the appropriate section divider.
3. Never silently rename or remove an existing `id` — that breaks references in `// invariant <id>:` code comments.

## Step 7 — Validate and iterate

```bash
nd invariants validate "$TARGET"
```

Address every error before continuing. Common ones:

- **`id: ... must match /^[a-z][a-z0-9-]*[a-z0-9]$/`** — kebab-case only, no underscores, no leading/trailing hyphens.
- **`source: ... must be 'path/to/doc.md[#anchor]' or 'https://...'`** — anchor must match `[A-Za-z0-9_-]+`. No spaces, no `#` in the slug.
- **`statement: length must be 20-1500`** — too short usually means too vague; expand. Too long means split into multiple entries.
- **`subsystems[i]: must match /^[a-z][a-z0-9_-]*$/`** — lowercase only; underscores OK, hyphens OK.

Iterate until clean.

## Step 8 — Hand off

Print a short summary to the user:

```
Drafted N invariants → proj/invariants.yaml

  Themes:    <comma-separated theme names>
  Citations: <count of unique source docs cited>
  Severities: high=<n> medium=<n> low=<n>

Next steps:
  1. Review proj/invariants.yaml against your own intuition. The first
     pass is a starting point, not the final word.
  2. Drop entries that aren't load-bearing for *this* repo, even if the
     graph found them.
  3. Tighten statements where they read vague.
  4. Once happy, move the file:
       git mv proj/invariants.yaml docs/invariants.yaml
     and commit.

The triage skill (`nd triage`) will pick up docs/invariants.yaml
automatically and start citing entries in its reports.
```

If `docs/invariants.yaml` already existed when this skill ran, also surface a diff hint:

```
  diff <(yq -P 'sort_by(.id)' docs/invariants.yaml) \
       <(yq -P 'sort_by(.id)' proj/invariants.yaml)
```

## Edge cases

- **No graph available**: state this up front; rely entirely on Steps 2 (docs / lint config / `// invariant` comments). Output should still be useful but will skip the architectural-pillar entries that the graph reveals.
- **No AGENTS.md or CLAUDE.md, no docs/, no proj/, no lint config**: tell the user the repo is missing the inputs this skill consumes. Suggest they hand-write a starter via `nd invariants init` and add design docs first.
- **Cross-repo**: if the cwd's git remote points at a different repo than the graph was built for, abort with the same advice as repo-triage: rerun from a checkout that the graph describes.
- **`statement` exceeds 1500 chars**: split into two entries with related ids.
- **You can't find a `source:` citation**: do **not** invent one. Either write the rule into `proj/INVARIANTS-NOTES.md` first and cite that, or drop the entry. A made-up citation is worse than a missing entry — it survives review and silently misleads everyone afterwards.

## What this skill is not

- Not a replacement for human curation. It does the bulk reading and grouping; humans pick what's load-bearing for *this* repo and tighten the wording.
- Not a continuous process. Run it once to bootstrap. After that, the file is hand-edited as the codebase evolves; a future `/invariants-update` skill (planned) handles drift.
- Not a search engine. It only emits rules it can cite; vague intuitions belong in design notes, not in this file.
