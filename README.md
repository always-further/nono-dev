<div align="center">
  <img src="assets/nono-dev-mascot.png" alt="nono-dev" width="600" />
</div>

# nono-dev

Development environment and sandboxed workflow manager for the [nono](https://github.com/always-further/nono) project. Provides two things:

1. **Lima Linux VMs** with Rust build toolchains for cross-compilation on macOS (real ext4 filesystem for Landlock sandbox enforcement).
2. **Sandboxed AI workflows** -- issue triage, bug fixing, PR review, feature development in git worktrees, and direct current-checkout sessions, all protected by [nono](https://docs.nono.sh) sandboxes.

See the [Documentation](https://always-further.github.io/nono-dev/) to get started!

## Prerequisites

- macOS with [Homebrew](https://brew.sh/) (Lima and mutagen are auto-installed when needed)
- [nono](https://docs.nono.sh/cli/getting_started/installation) (for sandbox commands)
- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated
- [Claude Code](https://claude.ai/code) CLI
- Python 3.11+ with [uv](https://docs.astral.sh/uv/) or pip

## Installation

```bash
git clone https://github.com/always-further/nono-dev.git
cd nono-dev
uv sync
nono-dev install --force       # registers the `nono-dev` nono sandbox profile
                               # and installs the `nono-dev` / `nd` commands globally
```

Optional shell integration (enables tab completion and the `wt` / `wts` shorthand functions for changing into worktrees and starting sandbox sessions):

```bash
nono-dev shell-init --install  # appends eval to ~/.zshrc (idempotent)
# or manually:
echo 'eval "$(nono-dev shell-init)"' >> ~/.zshrc
```

If you already have a `wt` command (e.g. from [Worktrunk](https://github.com/foresightpublishing/worktrunk)), nono-dev's helpers are available as `nwt` / `nwts` so nothing clobbers your existing tool.

Everywhere below, `nono-dev` and `nd` are interchangeable.

## Quick Start

### Sandbox workflows

```bash
# Triage a GitHub issue
nono-dev triage 42

# Fix a bug in an isolated worktree
nono-dev fix 123

# Review a pull request
nono-dev review 456
nono-dev review https://github.com/org/repo/pull/456

# Start a new feature
nono-dev feature my-feature

# Open a sandboxed Claude session in the current checkout
nono-dev bare api-spike
```

All sessions run detached in nono sandboxes with rollback enabled. Manage them with:

```bash
nono-dev sb list                # Dashboard of sessions and worktrees
nono-dev sb attach 123          # Attach to a session by issue number
nono-dev sb attach fix-123      # Or by session name
nono-dev sb stop review-456     # Stop a session
```

### Worktree management

```bash
nono-dev wt list                  # List managed worktrees
nono-dev wt cd issue-123          # Print the worktree path (use `wt` shortcut to cd)
nono-dev wt start issue-123       # Open a worktree AND start a sandbox session
nono-dev wt cleanup issue-123     # Remove a worktree and its branch
nono-dev wt cleanup --all         # Remove all managed worktrees
```

With shell-init loaded:

```bash
wt issue-123                      # cd into a worktree
wts issue-123                     # cd in AND start a sandbox (== nwts if wt is taken)
```

### Lima VMs

```bash
nono-dev vm create                # Ubuntu VM (80 GiB disk by default)
nono-dev vm create --shell-setup  # With zsh, starship, eza, bat, fd, ripgrep, direnv, fzf
nono-dev vm create --disk 120GiB --cpus 8 --memory 16GiB  # Custom resources
nono-dev vm connect               # Shell into the (only / default) VM
nono-dev vm status                # List VMs
nono-dev vm exec -- uname -a      # Run a command in the VM via SSH
nono-dev vm mount                 # Show what's currently synced
nono-dev vm mount /path/to/repo   # Switch default VM's sync to that path
nono-dev vm mount linux-gpu /path/to/repo  # Target a specific VM
nono-dev vm destroy               # Delete the VM
```

`connect`, `exec`, `mount`, and `destroy` auto-select a VM if only one exists, and accept `-m <name>` / `--name <name>` as an alias for the positional name. Explicit names that don't exist fail with an error — they never silently fall back to a different VM.

`recreate` deliberately does not auto-select: to avoid destroying the wrong VM, an omitted name always resolves to the default (`nono-dev`), never to an unrelated sole VM.

## Configuration

Create `nono-dev.toml` in your project root (optional -- repo is auto-detected from git remote):

```toml
[project]
repo = "always-further/nono"

[worktree]
dir = ".worktrees"

[rollback]
enabled = true
```

See [Configuration docs](docs/configuration.md) for all options.

## CLI Reference

```
nono-dev triage <issue>            Triage a GitHub issue (drafts local .md for review)
nono-dev fix <issue>               Fix a GitHub issue in a sandboxed worktree
nono-dev review <pr>               Review a GitHub PR
nono-dev feature <branch>          Start a feature in a sandboxed worktree
nono-dev bare [name]               Start a sandboxed Claude session in the current checkout

nono-dev vm create|connect|exec|status|mount|destroy|recreate
nono-dev sb list|attach|stop|prune|inspect
nono-dev wt list|cd|start|cleanup
nono-dev graph build|update|query|explain|path|status
nono-dev git commit [--no-sign]    AI-generated conventional commit (--no-sign skips GPG signing)

nono-dev install [--force]         Install `nono-dev` / `nd` + sandbox profile
nono-dev dotfiles                  Write shipped dotfiles to ~
nono-dev shell-init [--install]    Print (or install) shell integration
```

Issues and PRs accept both numbers (`123`) and GitHub URLs. Sibling repos (`nono`, `nono-ts`, `nono-py`, `nono-go`, `nono-dev`) are recognised automatically from URLs; plain numbers default to the current repo's git remote.

## VM Environment

VMs created with `nono-dev vm create` include:

- Rust toolchain (rustup) with cargo-audit
- Build dependencies: build-essential, pkg-config, libssl-dev, cmake, git, curl
- `CARGO_TARGET_DIR` set to `~/.cargo_target_linux` (avoids conflicts with macOS builds)
- Project synced to `~/project` via mutagen (continuous, on ext4 for Landlock enforcement)

With `--shell-setup`:

- zsh with starship prompt (Nerd Font icons)
- Modern CLI tools: eza (ls), bat (cat), fd (find), ripgrep (grep), fzf, direnv, tmux, z
- nono-dev shell aliases (`nd`, `ndf`, `nds`, `ndw`, etc.)
- Per-directory environment via direnv with Rust/nono helpers (`.direnvrc`)
- Pre-configured dotfiles (.zshrc, .direnvrc, .tmux.conf, starship.toml)
