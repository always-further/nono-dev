# Commands

## Workflow Commands

These are the primary commands, available at the top level.

### `triage`

Spawn a sandboxed Claude agent to triage a GitHub issue.

```bash
nono-dev triage <issue>
nono-dev triage 42
nono-dev triage https://github.com/org/repo/issues/42
```

The agent retrieves the issue, checks for duplicates and existing documentation, and posts a friendly follow-up comment asking for more information or pointing to a solution.

### `fix`

Create a git worktree and spawn a sandboxed agent to fix a GitHub issue.

```bash
nono-dev fix <issue>
nono-dev fix 123
nono-dev fix https://github.com/org/repo/issues/123
```

This command:

1. Creates a git worktree at `<worktree-dir>/issue-<N>` with branch `issue-<N>`
2. Launches Claude in a nono sandbox with write access to the worktree and read access to the main repo
3. The agent retrieves the issue, analyzes the codebase, and implements a fix

If the worktree or branch already exists, the existing worktree is reused.

### `review`

Spawn a sandboxed Claude agent to review a GitHub pull request.

```bash
nono-dev review <pr>
nono-dev review 456
nono-dev review https://github.com/org/repo/pull/456
```

The agent retrieves the PR diff, reviews for correctness, security, and style, then drafts a comment. Attach to the session to approve posting the review.

### `feature`

Create a git worktree and spawn a sandboxed agent for new feature development.

```bash
nono-dev feature <branch-name>
```

This command:

1. Creates a git worktree at `<worktree-dir>/<branch-name>` with the given branch
2. Launches Claude in a nono sandbox with write access to the worktree
3. The agent waits for your direction when you attach

---

## `sb` -- Sandbox Session Management

### `sb status`

Show a dashboard of all managed worktrees and nono sessions.

```bash
nono-dev sb status
```

Output:

```
NAME              PATH                    TYPE    ISSUE/PR  SESSION  STATUS   ATTACH    AGE    CHANGES
issue-42          .worktrees/issue-42     fix     #42       82984b   running  detached  2h30m  +34 -12
review-530        -                       review  #530      abe85b   running  attached  15m    -
issue-99          .worktrees/issue-99     fix     #99       -        -        -         -      +120 -45
```

Columns are dynamically sized to fit content.

### `sb attach`

Reconnect to a running nono session.

```bash
nono-dev sb attach <target>
```

The target can be:

- A **session name** (e.g., `fix-123`, `review-530`)
- An **issue or PR number** (e.g., `123`) -- finds the matching session
- A **session ID** or prefix (e.g., `82984b`)

### `sb stop`

Stop a running nono session.

```bash
nono-dev sb stop <target>
nono-dev sb stop review-530
nono-dev sb stop 530
nono-dev sb stop --force fix-123
```

| Flag | Description |
|------|-------------|
| `--force` | SIGKILL instead of SIGTERM |

### `sb prune`

Clean up old nono session files.

```bash
nono-dev sb prune
nono-dev sb prune --dry-run
nono-dev sb prune --older-than 7
nono-dev sb prune --keep 10
```

| Flag | Description |
|------|-------------|
| `--dry-run` | Show what would be removed |
| `--older-than DAYS` | Remove sessions older than N days |
| `--keep N` | Keep only the N most recent sessions |

---

## `wt` -- Worktree Management

### `wt list`

List all managed worktrees.

```bash
nono-dev wt list
```

### `wt cd`

Print the path to a worktree (used by the `wt` shell function).

```bash
nono-dev wt cd <name>
```

With `eval "$(nono-dev shell-init)"` in your `.zshrc`, use the `wt` function directly:

```bash
wt issue-123        # cd into the worktree
wt 123              # also works with issue numbers
wt fix-123          # or session names
```

### `wt cleanup`

Remove worktrees and their branches.

```bash
nono-dev wt cleanup issue-42
nono-dev wt cleanup --all
nono-dev wt cleanup --all --force
```

If a worktree has uncommitted changes, you are prompted before deletion:

```
Worktree 'issue-42' has uncommitted changes (+34 -12). Delete anyway? [y/N]
```

| Flag | Description |
|------|-------------|
| `--all` | Remove all worktrees in the configured directory |
| `--force` | Skip confirmation prompts |

---

## `git` -- AI-Assisted Git Operations

### `git commit`

Generate a commit message using Gemini AI and commit with sign-off.

```bash
nono-dev git commit
```

This command:

1. Collects all staged, unstaged, and untracked changes
2. Sends the diff to Gemini 2.5 Flash to generate a [conventional commit](https://www.conventionalcommits.org/) message
3. Shows the proposed message and asks for confirmation
4. Stages all changes and commits with `git commit -s`

Options at the prompt:

- **Y** -- commit with the proposed message
- **n** -- abort
- **e** -- open the message in `$EDITOR` for manual editing before committing

Requires `GEMINI_API_KEY` or `GOOGLE_API_KEY` set in your environment.

---

## `vm` -- OrbStack VM Management

### `vm create`

Create a development VM.

```bash
nono-dev vm create [--os {debian,ubuntu}] [name] [--extras PKG,PKG] [--mount PATH] [--user USER] [--no-rust] [--shell-setup]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--os` | `debian` | Operating system |
| `name` | `nono-dev` | VM name |
| `--extras` | none | Additional apt packages (comma-separated) |
| `--mount` | current directory | Host directory to mount as `~/project` |
| `--user` | current macOS user | Username in the VM |
| `--no-rust` | | Skip Rust/Cargo installation |
| `--shell-setup` | | Install zsh, starship, eza, tmux, ripgrep, fzf with dotfiles |

### `vm connect`

Open an interactive shell inside a VM.

```bash
nono-dev vm connect [name]
```

### `vm status`

List all OrbStack VMs and their current state.

```bash
nono-dev vm status
```

### `vm destroy`

Delete a VM.

```bash
nono-dev vm destroy [name] [--force]
```

### `vm recreate`

Destroy and recreate a VM in one step. Accepts the same flags as `vm create`.

```bash
nono-dev vm recreate [name] [--os ...] [--extras ...] [--mount ...] [--shell-setup]
```

---

## Utilities

### `dotfiles`

Deploy shipped dotfiles and install shell tools on the local machine.

```bash
nono-dev dotfiles
nono-dev dotfiles --force
nono-dev dotfiles --no-install
nono-dev dotfiles --preset nono-dev
```

This command:

1. Installs shell tools via Homebrew (starship, eza, tmux, z, zsh-autosuggestions)
2. Installs the MesloLGS Nerd Font for starship icons
3. Deploys `.zshrc`, `.zprofile`, and `.tmux.conf` to your home directory
4. Lets you pick a starship prompt preset

Existing files are backed up to `<file>.bak` before overwriting. Files that are already up to date are skipped.

Run this command again after updating nono-dev to pick up any dotfile changes.

| Flag | Description |
|------|-------------|
| `--force` | Overwrite existing files without backing up |
| `--no-install` | Only deploy dotfiles, skip Homebrew tool installation |
| `--preset NAME` | Use a specific starship preset (skip interactive picker) |

Available starship presets: `nono-dev`, `catppuccin-powerline`, `tokyo-night`, `pastel-powerline`, `bracketed-segments`, `gruvbox-rainbow`, `jetpack`, `pure-preset`.

### `install`

Install nono-dev as a globally available command via `uv tool`.

```bash
nono-dev install
nono-dev install --force
```

| Flag | Description |
|------|-------------|
| `--force` | Reinstall even if already installed |

### `shell-init`

Print shell functions for nono-dev integration. Add to your `.zshrc` or `.bashrc`:

```bash
eval "$(nono-dev shell-init)"
```

This provides the `wt` function for changing into worktree directories.
