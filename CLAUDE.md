# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

nono-dev is a Python CLI tool for the nono project's development team. It provides:

1. Lima Linux VM management for Rust cross-compilation on macOS (with real ext4 filesystem for Landlock enforcement)
2. Sandboxed AI agent workflows (`triage`, `fix`, `review`, `feature`, `bare`) using nono sandbox and git worktrees when needed

**Zero external dependencies** -- stdlib only (argparse, subprocess, tempfile, json, tomllib, etc.).

## Running

```bash
# Install with uv/pip (editable)
uv sync
nono-dev install --force      # also copies the sandbox profile to ~/.config/nono/profiles/
nono-dev fix 123              # or `nd fix 123` (alias)
```

## CLI Structure

Commands are grouped under `vm`, `sb`, `wt`, and `git`:

```
nono-dev triage|fix|review|feature|bare   # Top-level workflow commands
nono-dev vm create|connect|exec|status|mount|destroy|recreate
nono-dev sb list|attach|stop|prune|inspect
nono-dev wt list|cd|start|cleanup
nono-dev graph build|update|query|explain|path|status
nono-dev git commit [--no-sign]   # --no-sign skips GPG signing (use inside sandboxes)
nono-dev install|dotfiles|shell-init
```

Two console scripts are registered (see `pyproject.toml`): `nono-dev` and the shorter alias `nd`. They resolve to the same entry point.

## Architecture

- `nono_dev/cli.py` -- argparse entry point with nested subparsers (vm, sb, wt, git groups); early `--complete` handler for shell completion
- `nono_dev/commands/` -- one module per subcommand. Each exposes `add_parser(subparsers)` and `run(args)`
- `nono_dev/lima.py` -- thin subprocess wrapper around `limactl` and mutagen. Also provides `resolve_vm_name()` (auto-select logic) and `ssh_argv()` (builds `ssh -F <lima ssh.config>` invocations so we never mutate `~/.ssh/config` from exec paths).
- `nono_dev/nono.py` -- thin subprocess wrapper around `nono` CLI (run_detached, ps_json, attach). Defaults `profile="nono-dev"` and auto-grants read on the nono-dev source tree so editable installs work from inside a sandbox.
- `nono_dev/worktree.py` -- git worktree operations (add, list, remove, diff stats)
- `nono_dev/user_config.py` -- loads user-level `~/.config/nono-dev/config.toml` (worktree base dir, Lima home)
- `nono_dev/project_config.py` -- parse `nono-dev.toml`, merge with user config, resolve prompts, repo detection from git remote
- `nono_dev/template.py` -- builds Lima instance YAML programmatically (no PyYAML; uses a minimal `_yaml_dump` serializer)
- `nono_dev/config.py` -- constants: default VM name, OS, base apt packages, VM resource defaults (default disk 80GiB)
- `nono_dev/completions.py` -- pure-Python completion engine behind `nono-dev --complete` (top-level, session names, worktree names, VM names via `limactl list --json`, issue numbers)
- `nono_dev/prompts/` -- shipped system prompt markdown files for each workflow command (triage/fix/review/feature)
- `nono_dev/profiles/` -- shipped nono sandbox profile (`nono-dev.json`) copied to `~/.config/nono/profiles/` by `nono-dev install`
- `nono_dev/dotfiles/` -- shipped dotfiles for `--shell-setup` VMs (.zshrc, .direnvrc, .tmux.conf, starship.toml)

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
4. Build a `nono run --detached --profile nono-dev` command with sandbox permissions, system prompt, rollback
5. `run_detached` auto-grants `--read` on the nono-dev source tree so the `nd` editable install can import inside the sandbox
6. Parse session ID from nono's stderr output
7. User attaches later with `nono-dev sb attach`

The `nono-dev` sandbox profile (`nono_dev/profiles/nono-dev.json`) extends `claude-code` and adds read grants for `~/.lima`, `~/.config/gh`, `~/.ssh`, plus read-file access to `~/.gitconfig(.local)`. That's enough for a sandboxed agent to run `nd vm exec` (SSH into Lima VMs) and `gh` without further per-session plumbing.

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
- `nono.run_detached` always appends the nono-dev source dir to `--read` — an editable install of `nd` imports from there, so sandboxed agents would otherwise fail to run `nd` with a permission error
- `nd vm exec` uses `ssh -F ~/.lima/<vm>/ssh.config lima-<vm>` — never modifies `~/.ssh/config` — so it works from inside a sandbox that only has the narrow `~/.lima` grant
- Host-aliased SSH (`ssh lima-<vm>`) without `-F` is NOT safe to rely on — it only works if mutagen's `_ensure_ssh_include` has patched `~/.ssh/config` on that host, which isn't guaranteed
- `lima.resolve_vm_name(name, default)` fails closed: an explicit name that doesn't exist errors rather than falling back (critical for destructive commands like `destroy`/`recreate`)
- `vm mount` disambiguates its two positional args by shape: an arg starting with `/`, `~`, `./`, `../`, or containing a path separator / existing dir is treated as a path; otherwise it's a VM name. Use `-m <name>` to force VM interpretation.
- `bare` runs directly in the current checkout, so prompts and workflows must avoid overwriting unrelated local changes
- Config merge order is defaults -> user (`~/.config/nono-dev/config.toml`) -> repo (`nono-dev.toml`) -- repo always wins
- `lima.home` (set in `~/.config/nono-dev/config.toml` or `nono-dev.toml`) is threaded through every `limactl` and mutagen call via `LIMA_HOME` — VM-touching commands must load it via `project_config.get_lima_home(config)` and pass it as `lima_home=` to `lima.*` helpers
