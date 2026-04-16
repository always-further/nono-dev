# Configuration

nono-dev is configured via a `nono-dev.toml` file placed in the root of your project repository. The CLI searches upward from the current directory to find it.

## Full Reference

```toml
[project]
repo = "org/repo"  # GitHub org/repo (auto-detected from git remote)

[worktree]
dir = ".worktrees"  # directory for git worktrees (default: ".worktrees")

[rollback]
enabled = true                     # enable nono rollback snapshots (default: true)
dest = "~/.nono/rollbacks"         # custom rollback destination (default: ~/.nono/rollbacks/)
exclude = [".git", "node_modules"] # patterns to exclude from snapshots (optional)

[prompts]
triage = "prompts/triage.md"   # custom system prompt for triage (optional)
fix = "prompts/fix.md"         # custom system prompt for fix (optional)
review = "prompts/review.md"   # custom system prompt for review (optional)
feature = "prompts/feature.md" # custom system prompt for feature (optional)
```

## Sections

### `[project]`

| Key | Required | Description |
|-----|----------|-------------|
| `repo` | No | GitHub repository in `org/repo` format. Used by the `gh` CLI to fetch issues and PRs. If not set, derived automatically from the `origin` git remote URL. |

### `[worktree]`

| Key | Default | Description |
|-----|---------|-------------|
| `dir` | `.worktrees` | Directory where git worktrees are created. Relative paths are resolved from the config file location. |

Add this directory to your `.gitignore`:

```
.worktrees/
```

### `[rollback]`

nono's rollback feature creates atomic snapshots of all file changes during a session, allowing you to restore the previous state if something goes wrong.

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `true` | Pass `--rollback` to all nono sessions. |
| `dest` | `~/.nono/rollbacks/` (nono default) | Override the rollback snapshot destination. Defaults to nono's standard location outside the repo to avoid polluting git history. |
| `exclude` | `[]` | Patterns to exclude from rollback snapshots. Each pattern is passed as `--rollback-exclude`. |

### `[prompts]`

Override the default system prompts shipped with nono-dev. Paths are relative to the config file location.

| Key | Description |
|-----|-------------|
| `triage` | System prompt for the `triage` command |
| `fix` | System prompt for the `fix` command |
| `review` | System prompt for the `review` command |
| `feature` | System prompt for the `feature` command |

When no override is set, nono-dev uses its built-in prompts. See [Custom Prompts](custom-prompts.md) for guidance on writing your own.

## Minimal Configuration

If your git remote is set up, no configuration is required at all -- `repo` is derived from the `origin` remote URL. An empty `nono-dev.toml` or no file at all works with defaults.

To override the repo explicitly:

```toml
[project]
repo = "always-further/nono"
```

## Sibling Repos and Cross-Repo URLs

The `triage`, `fix`, and `review` commands accept full GitHub URLs as well as plain issue/PR numbers. When a URL points at a different repo than the current worktree — for example, you run `nd fix https://github.com/always-further/nono-py/issues/42` from inside `nono-dev` — the target repo is taken from the URL.

Session and branch names are automatically namespaced to avoid collisions between same-numbered issues across siblings:

| Command                                               | Branch                        | Session            |
|-------------------------------------------------------|-------------------------------|--------------------|
| `nd fix 42` (same repo)                               | `issue-42`                    | `fix-42`           |
| `nd fix https://github.com/.../nono-py/issues/42`     | `xrepo-nono-py-issue-42`      | `fix-nono-py-42`   |
| `nd triage https://github.com/.../nono-ts/issues/9`   | —                             | `triage-nono-ts-9` |
| `nd review https://github.com/.../nono-go/pull/3`     | —                             | `review-nono-go-3` |

No configuration is required for this — the `nono-family` repos (`nono`, `nono-ts`, `nono-py`, `nono-go`, `nono-dev`) are referenced by the shipped prompts and recognised by URL.

## VM Resource Defaults

VM sizing is set at VM-creation time via CLI flags on `nd vm create` / `nd vm recreate`, not in `nono-dev.toml`. Current defaults:

| Resource | Default | Flag |
|----------|---------|------|
| Disk     | `80GiB` | `--disk` |
| CPUs     | `4`     | `--cpus` |
| Memory   | `8GiB`  | `--memory` |

Lima disk images are sparse — only used space is actually written — so picking `--disk 120GiB` for headroom costs nothing up front. Rust target directories, cargo caches, and mutagen indices can consume significant space on longer-lived VMs, so generous sizing is recommended.
