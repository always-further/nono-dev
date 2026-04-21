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

# Register the nono-dev command globally AND copy the sandbox profile
# to ~/.config/nono/profiles/nono-dev.json (required for sandboxed agents
# to SSH into Lima VMs, access gh, git config, etc.).
nono-dev install --force
```

Two console scripts are registered: `nono-dev` and the shorter alias `nd`. They resolve to the same entry point — use whichever you prefer.

## Shell Integration

Add tab completion and worktree shortcuts to your shell:

```bash
nono-dev shell-init --install       # appends the eval to ~/.zshrc (idempotent)
# or manually:
echo 'eval "$(nono-dev shell-init)"' >> ~/.zshrc
```

This installs:

- `nwt <name>` — cd into a worktree
- `nwts <name>` — launch a sandbox in a worktree AND cd into it
- `wt` / `wts` — same as above, but only if you don't already have a `wt` command (e.g. from Worktrunk)
- Tab completion for `nono-dev` and `nd` (subcommands, session names, worktree branches, VM names, issue numbers)

Restart your shell or `source ~/.zshrc` to load it.

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

This spawns a sandboxed Claude agent that retrieves the issue, performs root cause analysis, and **drafts** a follow-up comment to `triage-42.md` in the current directory. Review and edit the draft, then post manually with:

```bash
gh issue comment 42 -R always-further/nono --body-file triage-42.md
```

The agent runs detached in the background — attach to it at any time:

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

### Cross-repo fixes

The nono project spans sibling repos — `nono`, `nono-ts`, `nono-py`, `nono-go`, and this repo `nono-dev`. Passing a URL that points at a sibling creates a namespaced worktree so same-numbered issues don't collide:

```bash
nono-dev fix https://github.com/always-further/nono-py/issues/42
# -> worktree .worktrees/xrepo-nono-py-issue-42
# -> session  fix-nono-py-42
```

The reserved `xrepo-` prefix on cross-repo branches keeps user-chosen branches like `docs-issue-42` safely classified as feature branches.

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

Shows a dashboard of all worktrees and active sessions. Cross-repo rows appear with a `<slug>#<N>` prefix in the ISSUE/PR column:

```
PROJECT            NAME                           PATH                                   TYPE    ISSUE/PR     SESSION  STATUS   ATTACH    AGE    CHANGES
always-further/nono issue-42                      .worktrees/issue-42                    fix     #42          82984b   running  detached  2h30m  +34 -12
always-further/nono issue-123                     .worktrees/issue-123                   fix     #123         a1b2c3   running  attached  15m    +0 -0
always-further/nono my-new-feature                .worktrees/my-new-feature              feature my-new-feat  d4e5f6   running  detached  1h     +15 -3
always-further/nono xrepo-nono-py-issue-42        .worktrees/xrepo-nono-py-issue-42      fix     nono-py#42   e5f6a7   running  detached  10m    +2 -0
always-further/nono bare-api-spike                .                                      bare    api-spike    e7f8a9   running  detached  12m    +3 -1
always-further/nono triage-42                     -                                      triage  #42          f7a8b9   running  detached  5m     -
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
