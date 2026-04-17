# Getting Started

nono-dev is a CLI tool for the nono project's development team. It manages Lima Linux VMs for cross-compilation (with real ext4 for Landlock sandbox enforcement) and provides sandboxed AI agent workflows for issue triage, bug fixing, PR review, feature development in worktrees, and direct current-checkout sessions.

## Prerequisites

- macOS with [Homebrew](https://brew.sh/) (Lima and mutagen are auto-installed when needed)
- [nono](https://docs.nono.sh/cli/getting_started/installation) installed (for sandbox commands)
- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated
- Python 3.11+
- [Claude Code](https://claude.ai/code) CLI installed

## Installation

```bash
git clone https://github.com/always-further/nono-dev.git
cd nono-dev

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

This makes the `nono-dev` command available globally.

## Shell Integration

For the `wt` shell function (changes directory into worktrees), add to your `.zshrc` or `.bashrc`:

```bash
eval "$(nono-dev shell-init)"
```

## Configuration

### User config (recommended)

Create `~/.config/nono-dev/config.toml` to set global defaults. This is the best place to redirect worktrees and VM storage to an external drive:

```toml
[worktree]
dir = "/Volumes/SSD/worktrees"  # repo name auto-appended

[lima]
home = "/Volumes/SSD/lima"      # VM disk images stored here
```

### Repo config (optional)

Create a `nono-dev.toml` file in the root of the project you want to work on. This overrides user config:

```toml
[project]
repo = "always-further/nono"  # optional, auto-detected from git remote

[rollback]
enabled = true
```

See [Configuration](configuration.md) for all available options.

## Your First Workflow

### Triage an issue

```bash
cd /path/to/your/project
nono-dev triage 42
```

This spawns a sandboxed Claude agent that retrieves the issue, performs root cause analysis, and posts a follow-up comment. The agent runs in the background -- attach to it at any time:

```bash
nono-dev sb attach 42
```

### Fix a bug

```bash
nono-dev fix 123
```

This creates a git worktree at `.worktrees/issue-123`, branches from main, and spawns a sandboxed agent to work on the fix. You can also pass a full URL:

```bash
nono-dev fix https://github.com/always-further/nono/issues/123
```

### Review a PR

```bash
nono-dev review 456
```

A sandboxed agent retrieves the PR diff, reviews it, and drafts a comment. Attach to approve or edit before posting.

### Start a feature

```bash
nono-dev feature my-new-feature
```

Creates a worktree and branch, then spawns an agent you can direct interactively.

### Start in the current checkout

```bash
nono-dev bare api-spike
```

Starts a sandboxed Claude session directly in the current checkout, with no worktree creation. Use this when you explicitly want the agent operating in-place.

## Checking Status

```bash
nono-dev sb list
```

Shows a dashboard of all worktrees and active sessions:

```
NAME              PATH                    TYPE    ISSUE/PR  SESSION  STATUS   ATTACH    AGE    CHANGES
issue-42          .worktrees/issue-42     fix     #42       82984b   running  detached  2h30m  +34 -12
issue-123         .worktrees/issue-123    fix     #123      a1b2c3   running  attached  15m    +0 -0
my-new-feature    .worktrees/my-feature   feature my-new-feature d4e5f6 running detached  1h  +15 -3
bare-api-spike    .                       bare    api-spike e7f8a9   running  detached  12m    +3 -1
triage-42         -                       triage  #42       f7a8b9   running  detached  5m     -
```

## Updating

When a new version of nono-dev is released, pull the latest changes and re-deploy your dotfiles:

```bash
cd /path/to/nono-dev
git pull
nono-dev install --force
nono-dev dotfiles
```

The `dotfiles` command detects which files have changed, backs up your existing copies (to `~/.zshrc.bak`, etc.), and deploys the updated versions. If nothing changed, the files are skipped.

After updating, restart your shell or run:

```bash
source ~/.zshrc
```

## Migrating from OrbStack to Lima

nono-dev previously used OrbStack for VM management. VMs now use Lima with mutagen sync so files live on a real ext4 filesystem (required for Landlock sandbox enforcement).

If you have an existing OrbStack VM, delete it and create a fresh Lima VM:

```bash
# 1. Delete the old OrbStack VM
orb delete nono-dev

# 2. Update nono-dev
cd /path/to/nono-dev
git pull
nono-dev install --force
nono-dev dotfiles
source ~/.zshrc

# 3. Create a new Lima VM (auto-installs Lima and mutagen via Homebrew)
nono-dev vm create --shell-setup

# 4. Connect
nono-dev vm connect
```

You can uninstall OrbStack after confirming the new VM works.

## Setting Up a VM

```bash
# Basic VM with Rust toolchain
nono-dev vm create

# With zsh, starship, eza, bat, fd, ripgrep, direnv, fzf, tmux
nono-dev vm create --shell-setup

# Connect
nono-dev vm connect
```
