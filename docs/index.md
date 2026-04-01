<div align="center">
  <img src="../assets/nono-dev-mascot.png" alt="nono-dev" width="600" />
</div>

# nono-dev

Development environment and sandboxed workflow manager for the nono project.

nono-dev gives your team two things:

1. **Consistent build environments** -- OrbStack Linux VMs with Rust toolchains, ready in seconds.
2. **Sandboxed AI workflows** -- issue triage, bug fixing, PR review, and feature development, each isolated in a git worktree with nono sandbox protections.

## Quick start

```bash
# Install
git clone https://github.com/always-further/nono-dev.git
cd nono-dev && uv sync

# Triage an issue
nono-dev triage 42

# Fix a bug in an isolated worktree
nono-dev fix 123

# Review a PR
nono-dev review 456

# Start a new feature
nono-dev feature my-feature

# Check what's running
nono-dev status
```

All agent sessions run detached in nono sandboxes. Attach at any time:

```bash
nono-dev attach 42
```

## Prerequisites

- macOS with [OrbStack](https://orbstack.dev/) (for VM commands)
- [nono](https://docs.nono.sh/cli/getting_started/installation) (for sandbox commands)
- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated
- [Claude Code](https://claude.ai/code) CLI
- Python 3.11+

## Next steps

- [Getting Started](getting-started.md) -- installation and first workflow
- [Commands](commands.md) -- full CLI reference
- [Configuration](configuration.md) -- `nono-dev.toml` reference
- [Workflows](workflows.md) -- practical guides for common tasks
