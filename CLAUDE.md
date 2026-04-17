# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

nono-dev is a Python CLI tool for the nono project's development team. It provides:

1. Lima Linux VM management for Rust cross-compilation on macOS (with real ext4 filesystem for Landlock enforcement)
2. Sandboxed AI agent workflows (`triage`, `fix`, `review`, `feature`, `bare`) using nono sandbox and git worktrees when needed

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
nono-dev triage|fix|review|feature|bare   # Top-level workflow commands
nono-dev vm create|connect|status|destroy|recreate
nono-dev sb list|attach|stop|prune
nono-dev wt list|cd|cleanup
nono-dev shell-init
```

## Architecture

- `nono_dev/cli.py` -- argparse entry point with nested subparsers (vm, sb, wt groups)
- `nono_dev/commands/` -- one module per subcommand. Each exposes `add_parser(subparsers)` and `run(args)`
- `nono_dev/lima.py` -- thin subprocess wrapper around `limactl` CLI commands and mutagen sync
- `nono_dev/nono.py` -- thin subprocess wrapper around `nono` CLI (run_detached, ps_json, attach)
- `nono_dev/worktree.py` -- git worktree operations (add, list, remove, diff stats)
- `nono_dev/user_config.py` -- loads user-level `~/.config/nono-dev/config.toml` (worktree base dir, Lima home)
- `nono_dev/project_config.py` -- parse `nono-dev.toml`, merge with user config, resolve prompts, repo detection from git remote
- `nono_dev/template.py` -- builds Lima instance YAML programmatically (no PyYAML; uses a minimal `_yaml_dump` serializer)
- `nono_dev/config.py` -- constants: default VM name, OS, base apt packages, VM resource defaults
- `nono_dev/prompts/` -- shipped system prompt markdown files for each workflow command
- `nono_dev/dotfiles/` -- shipped dotfiles for `--shell-setup` VMs (.zshrc, .tmux.conf, starship.toml)

### Configuration

Config is loaded in three layers (later overrides earlier):

1. **Hardcoded defaults** -- `project_config.DEFAULTS`
2. **User config** -- `~/.config/nono-dev/config.toml` (global, applies to all repos)
3. **Repo config** -- `nono-dev.toml` (per-repo, checked into the codebase)

```toml
# ~/.config/nono-dev/config.toml
[worktree]
dir = "/Volumes/SSD/worktrees"  # repo name auto-appended (e.g. .../worktrees/nono/)

[lima]
home = "/Volumes/SSD/lima"      # sets LIMA_HOME for limactl
```

When `worktree.dir` comes from user config and is an absolute path, the repo name (from git remote) is auto-appended to keep projects separated. Repo-level `nono-dev.toml` overrides are used as-is with no auto-append.

Lima home is threaded as `lima_home=None` through all `lima.py` public functions and passed as `LIMA_HOME` env var to `limactl` subprocess calls.

### Sandbox workflow flow

1. Load `nono-dev.toml` config (repo auto-detected from git remote if not set)
2. For `fix`/`feature`: create a git worktree with `git worktree add`
3. For `bare`: use the current checkout directly with no worktree
4. Build a `nono run --detached` command with sandbox permissions, system prompt, rollback
5. Parse session ID from nono's stderr output
6. User attaches later with `nono-dev sb attach`

### VM creation flow

`create.py` uses Lima's provisioning system:

1. **Lima YAML config:** Generates a Lima instance YAML with `vmType: vz`, OS images, and `provision` scripts
2. **System provision script:** Creates user, installs apt packages, cargo target dir, MOTD, optionally shell tools (starship, eza, z)
3. **User provision script:** Installs Rust toolchain and cargo-audit
4. **Mutagen sync:** After VM boots, starts a continuous mutagen sync session from the host project directory to `~/project` on the VM's ext4 filesystem

Files live on ext4 inside the VM (not virtiofs) so Landlock can enforce sandbox rules.

## Key Constraints

- All Lima interaction goes through `nono_dev/lima.py` -- never shell out to `limactl` directly from commands
- All nono interaction goes through `nono_dev/nono.py` -- never shell out to `nono` directly from commands
- VM filesystems must be real ext4/btrfs (not virtiofs) for Landlock enforcement -- this is why mutagen sync is used instead of shared mounts
- Lima's `mounts` is set to `[]` (empty) to avoid virtiofs; mutagen handles file sync to ext4
- The Lima YAML uses `provision` scripts (not cloud-init `packages` directive) for all package installation
- The `provision` system script creates the VM user; Lima's default user is not used for project work
- `CARGO_TARGET_DIR` is set via shell profile (not `~/.cargo/config.toml`) so interactive builds use `~/.cargo_target_linux` while non-interactive scripts (tests, CI) use the default `target/` directory
- nono writes session info to stderr, not stdout -- `nono.py` reads both streams
- The JSON key for session IDs from `nono ps --json` is `session_id`, not `session`
- Claude Code's `--system-prompt` flag takes inline text, not a file path -- prompts are read and passed as content
- Claude Code's `-p` flag means "print mode" (non-interactive), not "prompt" -- prompts are positional args
- Worktree commands need `--allow .git/` (not just `.git/worktrees/`) for git commit operations
- `fix`/`feature` grant `--read` on the main repo for Claude's Read/Edit tools to follow worktree symlinks
- `bare` runs directly in the current checkout, so prompts and workflows must avoid overwriting unrelated local changes
- Config merge order is defaults -> user (`~/.config/nono-dev/config.toml`) -> repo (`nono-dev.toml`) -- repo always wins
- `lima_home` must be threaded through all `lima.py` calls -- never hardcode `~/.lima` in commands
