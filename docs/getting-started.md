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

## Project Configuration

Create a `nono-dev.toml` file in the root of the project you want to work on:

```toml
[project]
repo = "always-further/nono"  # org/repo for GitHub CLI

[worktree]
dir = ".worktrees"  # where git worktrees are created

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
nono-dev attach 42
```

### Fix a bug

```bash
nono-dev fix 123
```

This creates a git worktree at `.worktrees/issue-123`, branches from main, and spawns a sandboxed agent to work on the fix.

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
nono-dev status
```

Shows a dashboard of all worktrees and active sessions:

```
WORKTREE          TYPE      ISSUE/PR   SESSION    STATUS    CHANGES
issue-42          fix       #42        82984b     running   +34 -12
issue-123         fix       #123       a1b2c3     running   +0 -0
my-new-feature    feature   -          d4e5f6     running   +15 -3
-                 triage    #42        f7a8b9     stopped   -
```
