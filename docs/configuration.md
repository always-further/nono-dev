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
bare = "prompts/bare.md"       # custom system prompt for bare (optional)
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
| `bare` | System prompt for the `bare` command |

When no override is set, nono-dev uses its built-in prompts. See [Custom Prompts](custom-prompts.md) for guidance on writing your own.

## Minimal Configuration

If your git remote is set up, no configuration is required at all -- `repo` is derived from the `origin` remote URL. An empty `nono-dev.toml` or no file at all works with defaults.

To override the repo explicitly:

```toml
[project]
repo = "always-further/nono"
```
