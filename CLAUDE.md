# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

nono-dev is a Python CLI tool that manages OrbStack Linux VMs for the nono project's development team. It wraps OrbStack's `orb`/`orbctl` commands to provision consistent Rust build environments on macOS.

**Zero external dependencies** — stdlib only (argparse, subprocess, tempfile, json, etc.).

## Running

```bash
# Direct execution (no install)
./nono-dev create --mount ~/dev/nono/

# Or install with uv/pip
uv sync
nono-dev create
```

## Architecture

- `nono_dev/cli.py` — argparse entry point, dispatches to subcommand modules
- `nono_dev/commands/` — one module per subcommand (create, connect, status, destroy, recreate). Each exposes `add_parser(subparsers)` and `run(args)`
- `nono_dev/orbstack.py` — thin subprocess wrapper around `orb` and `orbctl` CLI commands
- `nono_dev/template.py` — builds cloud-init YAML programmatically (no PyYAML; uses a minimal `_yaml_dump` serializer)
- `nono_dev/config.py` — constants: default VM name, OS, base apt packages

### VM creation flow

`create.py` does a two-phase provisioning because OrbStack's own setup conflicts with cloud-init's `packages` directive (apt lock race):

1. **Phase 1 (cloud-init):** User creation, write_files (cargo config, motd), symlink setup only
2. **Phase 2 (post-create):** Runs `orb run -m <name>` commands to install apt packages and rustup after the VM is up

## Key Constraints

- All OrbStack interaction goes through `nono_dev/orbstack.py` — never shell out to `orb`/`orbctl` directly from commands
- Cloud-init must NOT use the `packages` directive — it races with OrbStack's own apt-get. Install packages via `orb run` post-create instead
- The cloud-init `users` directive creates the VM user; OrbStack's default user (e.g. `debian`) is not used
- `~/.cargo/config.toml` sets `target-dir` (not env vars) to keep Linux builds out of the shared macOS mount
