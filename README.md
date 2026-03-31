# nono-dev

Development environment manager for the nono project. Creates consistent [OrbStack](https://orbstack.dev/) Linux VMs with Rust build dependencies so every developer on the team gets an identical build environment in seconds.

OrbStack is a lightweight alternative to Docker Desktop and Linux VMs on macOS. It runs Linux distributions as fast, native virtual machines with seamless macOS integration.

## Prerequisites

- macOS with [OrbStack](https://orbstack.dev/) installed
- Python 3.9+
- Rust/Cargo installed on the host (for building on macOS; the VM gets its own Rust toolchain)

## Quick Start

```bash
# Clone the repo
git clone <repo-url>
cd nono-dev

# Create your VM (no install step needed)
./nono-dev create

# Connect to the VM
./nono-dev connect
```

This creates a Debian VM named `nono-dev` with:
- Rust toolchain (via rustup)
- C/C++ build dependencies (build-essential, pkg-config, cmake, etc.)
- `CARGO_TARGET_DIR` set to `~/.cargo_target_linux`
- Your current directory mounted at `~/project` inside the VM

Verify the environment is ready:

```bash
rustc --version
cc --version
echo $CARGO_TARGET_DIR
ls ~/project
```

## Installation

There are three ways to run the tool:

```bash
# 1. Run directly from the repo (no install)
./nono-dev create

# 2. Install as a CLI tool (recommended for regular use)
pip install -e .
nono-dev create

# 3. Run as a Python module
python -m nono_dev create
```

Option 2 makes `nono-dev` available from any directory.

## Commands

### create

```bash
nono-dev create [--os {debian,ubuntu}] [--name NAME] [--extras PKG,PKG] [--mount PATH] [--user USER] [--no-rust]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--os` | Operating system | `debian` |
| `--name` | VM name | `nono-dev` |
| `--extras` | Additional apt packages (comma-separated) | none |
| `--mount` | Host directory to symlink as `~/project` in the VM | current directory |
| `--user` | Username in the VM | current macOS user |
| `--no-rust` | Skip Rust/Cargo installation | |

If the VM already exists, you'll be prompted to recreate, connect, or abort.

Examples:

```bash
# Default Debian VM
nono-dev create

# Ubuntu with extra packages
nono-dev create --os ubuntu --extras protobuf-compiler,libdbus-1-dev

# Mount a specific directory
nono-dev create --mount /Users/alice/dev/nono

# Skip Rust (just need the C toolchain)
nono-dev create --no-rust
```

### connect

```bash
nono-dev connect [--name NAME]
```

Opens an interactive shell inside the VM.

### status

```bash
nono-dev status
```

Lists all OrbStack VMs and their current state.

### destroy

```bash
nono-dev destroy [--name NAME] [--force]
```

Deletes a VM. Prompts for confirmation unless `--force` is passed.

### recreate

```bash
nono-dev recreate [--name NAME] [--os ...] [--extras ...] [--mount ...]
```

Destroys and recreates a VM in one step. Accepts all the same flags as `create`.

## Working with the VM

### Project Mount

Your macOS project directory is available inside the VM at `~/project`. Edit files on macOS, build and run inside Linux:

```bash
# On the VM
cd ~/project
cargo build
cargo test
```

Changes are reflected immediately in both directions -- no syncing needed.

### SSH Agent Forwarding

Your macOS SSH agent is automatically forwarded into the VM. Git operations over SSH work without copying keys:

```bash
# Inside the VM -- uses your macOS SSH keys
git clone git@github.com:your-org/nono.git
```

### VS Code Remote Development

Use VS Code's Remote-SSH extension to edit and debug inside the VM while keeping the macOS UI:

1. Install the [Remote - SSH](https://marketplace.visualstudio.com/items?itemName=ms-vscode.remote-ssh) extension
2. Connect to the VM: `Cmd+Shift+P` -> `Remote-SSH: Connect to Host` -> `nono-dev`
3. Open `~/project`

The Rust Language Server, `cargo check`, and all tooling run inside the Linux environment.

### Networking

Each VM gets a `.orb.local` domain. If you're running a dev server inside the VM, access it from macOS at:

```
http://nono-dev.orb.local:8080
```

No port forwarding configuration needed.

## Installed Packages

The base environment includes:

- `build-essential` (gcc, g++, make)
- `pkg-config`
- `libssl-dev`
- `cmake`
- `perl`
- `git`
- `curl`

Add more at creation time with `--extras`:

```bash
nono-dev create --extras protobuf-compiler,libdbus-1-dev,clang
```

## Cleanup

```bash
# Remove a specific VM
nono-dev destroy --name nono-dev

# Skip the confirmation prompt
nono-dev destroy --force
```
