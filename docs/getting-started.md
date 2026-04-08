# Getting Started

nono-dev is a CLI tool for the nono project's development team. It manages OrbStack Linux VMs for cross-compilation and provides sandboxed AI agent workflows for issue triage, bug fixing, PR review, and feature development.

## Prerequisites

- macOS with [OrbStack](https://orbstack.dev/) installed (for VM commands)
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

## Project Configuration

Create a `nono-dev.toml` file in the root of the project you want to work on:

```toml
[project]
repo = "always-further/nono"  # optional, auto-detected from git remote

[worktree]
dir = ".worktrees"

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

## Checking Status

```bash
nono-dev sb status
```

Shows a dashboard of all worktrees and active sessions:

```
NAME              PATH                    TYPE    ISSUE/PR  SESSION  STATUS   ATTACH    AGE    CHANGES
issue-42          .worktrees/issue-42     fix     #42       82984b   running  detached  2h30m  +34 -12
issue-123         .worktrees/issue-123    fix     #123      a1b2c3   running  attached  15m    +0 -0
my-new-feature    .worktrees/my-feature   feature -         d4e5f6   running  detached  1h     +15 -3
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

## Setting Up a VM

```bash
# Basic VM with Rust toolchain
nono-dev vm create

# With zsh, starship, eza, tmux, ripgrep, fzf
nono-dev vm create --shell-setup

# Connect
nono-dev vm connect
```
