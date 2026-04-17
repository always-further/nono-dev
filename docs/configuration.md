# Configuration

nono-dev uses a two-level configuration system:

1. **User config** -- `~/.config/nono-dev/config.toml` (global, applies to all repos)
2. **Repo config** -- `nono-dev.toml` in the project root (per-repo, overrides user config)

Settings are merged in order: hardcoded defaults -> user config -> repo config. Repo config always wins.

## User Config

The user config lives at `~/.config/nono-dev/config.toml` and sets global defaults across all projects. This is the right place for machine-specific paths like an external SSD.

```toml
[worktree]
dir = "/Volumes/SSD/worktrees"  # repo name auto-appended

[lima]
home = "/Volumes/SSD/lima"      # sets LIMA_HOME for limactl
```

When `worktree.dir` is set in user config and is an absolute path, the repo name (derived from the git remote, e.g. `nono`) is automatically appended to keep projects separated:

```
/Volumes/SSD/worktrees/nono/issue-123
/Volumes/SSD/worktrees/other-project/issue-456
```

When `lima.home` is set, all `limactl` commands use it as `LIMA_HOME`, storing VM disk images and instance data there instead of the default `~/.lima/`.

## Repo Config

The repo config is a `nono-dev.toml` file placed in the root of your project repository. The CLI searches upward from the current directory to find it.

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

## User Config Sections

### `[worktree]` (user)

| Key | Default | Description |
|-----|---------|-------------|
| `dir` | none | Base directory for git worktrees. The repo name is auto-appended (e.g. `/Volumes/SSD/worktrees` becomes `/Volumes/SSD/worktrees/nono/`). |

### `[lima]`

| Key | Default | Description |
|-----|---------|-------------|
| `home` | `~/.lima` (Lima default) | Directory where Lima stores VM instances and disk images. Passed as `LIMA_HOME` to all `limactl` commands. |

## Repo Config Sections

### `[project]`

| Key | Required | Description |
|-----|----------|-------------|
| `repo` | No | GitHub repository in `org/repo` format. Used by the `gh` CLI to fetch issues and PRs. If not set, derived automatically from the `origin` git remote URL. |

### `[worktree]` (repo)

| Key | Default | Description |
|-----|---------|-------------|
| `dir` | `.worktrees` | Directory where git worktrees are created. Relative paths are resolved from the config file location. Overrides the user config value. Repo-level paths are used as-is (no auto-append). |

> **Tip:** Prefer setting `worktree.dir` in user config (`~/.config/nono-dev/config.toml`) to keep worktrees outside the repo. In-repo worktrees can confuse IDEs and require `.gitignore` entries.

If using the default in-repo location, add this to your `.gitignore`:

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
