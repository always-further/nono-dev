# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

nono-dev is a Python CLI tool for the nono project's development team. It provides:

1. OrbStack Linux VM management for Rust cross-compilation on macOS
2. Sandboxed AI agent workflows (triage, fix, review, feature) using nono sandbox and git worktrees

**Zero external dependencies** -- stdlib only (argparse, subprocess, tempfile, json, tomllib, etc.).

## Running

```bash
# Install with uv/pip
uv sync
nono-dev fix 123
```

## CLI Structure

Commands are grouped under `vm`, `sb`, and `wt`:

```
nono-dev triage|fix|review|feature   # Top-level workflow commands
nono-dev vm create|connect|status|destroy|recreate
nono-dev sb status|attach|stop|prune
nono-dev wt list|cd|cleanup
nono-dev shell-init
```

## Architecture

- `nono_dev/cli.py` -- argparse entry point with nested subparsers (vm, sb, wt groups)
- `nono_dev/commands/` -- one module per subcommand. Each exposes `add_parser(subparsers)` and `run(args)`
- `nono_dev/orbstack.py` -- thin subprocess wrapper around `orb` and `orbctl` CLI commands
- `nono_dev/nono.py` -- thin subprocess wrapper around `nono` CLI (run_detached, ps_json, attach)
- `nono_dev/worktree.py` -- git worktree operations (add, list, remove, diff stats)
- `nono_dev/project_config.py` -- parse `nono-dev.toml`, resolve prompts, repo detection from git remote
- `nono_dev/template.py` -- builds cloud-init YAML programmatically (no PyYAML; uses a minimal `_yaml_dump` serializer)
- `nono_dev/config.py` -- constants: default VM name, OS, base apt packages
- `nono_dev/prompts/` -- shipped system prompt markdown files for each workflow command
- `nono_dev/dotfiles/` -- shipped dotfiles for `--shell-setup` VMs (.zshrc, .tmux.conf, starship.toml)

### Sandbox workflow flow

1. Load `nono-dev.toml` config (repo auto-detected from git remote if not set)
2. For `fix`/`feature`: create a git worktree with `git worktree add`
3. Build a `nono run --detached` command with sandbox permissions, system prompt, rollback
4. Parse session ID from nono's stderr output
5. User attaches later with `nono-dev sb attach`

### VM creation flow

`create.py` does a two-phase provisioning because OrbStack's own setup conflicts with cloud-init's `packages` directive (apt lock race):

1. **Phase 1 (cloud-init):** User creation, write_files (cargo config, motd), symlink setup only
2. **Phase 2 (post-create):** Runs `orb run -m <name>` commands to install apt packages, rustup, cargo-audit, and optionally shell tools (starship, eza, z)

## Key Constraints

- All OrbStack interaction goes through `nono_dev/orbstack.py` -- never shell out to `orb`/`orbctl` directly from commands
- All nono interaction goes through `nono_dev/nono.py` -- never shell out to `nono` directly from commands
- Cloud-init must NOT use the `packages` directive -- it races with OrbStack's own apt-get. Install packages via `orb run` post-create instead
- The cloud-init `users` directive creates the VM user; OrbStack's default user (e.g. `debian`) is not used
- `~/.cargo/config.toml` sets `target-dir` (not env vars) to keep Linux builds out of the shared macOS mount
- nono writes session info to stderr, not stdout -- `nono.py` reads both streams
- The JSON key for session IDs from `nono ps --json` is `session_id`, not `session`
- Claude Code's `--system-prompt` flag takes inline text, not a file path -- prompts are read and passed as content
- Claude Code's `-p` flag means "print mode" (non-interactive), not "prompt" -- prompts are positional args
- Worktree commands need `--allow .git/` (not just `.git/worktrees/`) for git commit operations
- `fix`/`feature` grant `--read` on the main repo for Claude's Read/Edit tools to follow worktree symlinks
