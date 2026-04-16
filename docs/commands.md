# Commands

## Workflow Commands

These are the primary commands, available at the top level.

### `triage`

Spawn a sandboxed Claude agent to triage a GitHub issue.

```bash
nono-dev triage <issue>
nono-dev triage 42
nono-dev triage https://github.com/always-further/nono-py/issues/42
```

The agent retrieves the issue, checks for duplicates and existing documentation across the nono-family repos (`nono`, `nono-ts`, `nono-py`, `nono-go`, `nono-dev`), and **drafts** a friendly follow-up comment to `triage-<N>.md` in the current directory. The draft is **not** posted automatically — review/edit it, then post manually:

```bash
gh issue comment <N> -R <repo> --body-file triage-<N>.md
```

When a full URL is passed, the target repo is taken from the URL; otherwise the current repo's `origin` remote is used. Sibling repos are considered for cross-references when analysing the issue.

### `fix`

Create a git worktree and spawn a sandboxed agent to fix a GitHub issue.

```bash
nono-dev fix <issue>
nono-dev fix 123
nono-dev fix https://github.com/always-further/nono/issues/123
nono-dev fix https://github.com/always-further/nono-py/issues/42   # cross-repo
```

**Same-repo** (plain number or URL matching the current repo's remote):

1. Creates a git worktree at `<worktree-dir>/issue-<N>` with branch `issue-<N>`
2. Session name: `fix-<N>`

**Cross-repo** (URL pointing at a sibling like `nono-py`):

1. Creates a git worktree at `<worktree-dir>/xrepo-<slug>-issue-<N>` with branch `xrepo-<slug>-issue-<N>`
2. Session name: `fix-<slug>-<N>`
3. A warning is printed noting the worktree lives in the current repo, not in the sibling repo (you may want to `cd` into the sibling checkout first for a more useful branching base)

The reserved `xrepo-` prefix keeps user-chosen branches like `docs-issue-42` or `cleanup-issue-7` classified as feature branches — they will not be confused with cross-repo fix branches.

If the worktree or branch already exists, the existing worktree is reused.

### `review`

Spawn a sandboxed Claude agent to review a GitHub pull request.

```bash
nono-dev review <pr>
nono-dev review 456
nono-dev review https://github.com/always-further/nono/pull/456
nono-dev review https://github.com/always-further/nono-py/pull/7   # cross-repo
```

The agent retrieves the PR diff, reviews for correctness, security, and style, then drafts a comment. Attach to the session to approve posting the review.

Same-repo session name is `review-<N>`; cross-repo (URL pointing at a sibling) is `review-<slug>-<N>` so PRs with the same number across siblings don't collide.

### `feature`

Create a git worktree and spawn a sandboxed agent for new feature development.

```bash
nono-dev feature <branch-name>
```

This command:

1. Creates a git worktree at `<worktree-dir>/<branch-name>` with the given branch
2. Launches Claude in a nono sandbox with write access to the worktree
3. The agent waits for your direction when you attach

### `bare`

Start a sandboxed Claude session directly in the current checkout.

```bash
nono-dev bare [name]
nono-dev bare api-spike
```

This command:

1. Uses the current repository checkout as the sandbox workspace
2. Launches Claude in a nono sandbox with write access to the current checkout
3. The agent waits for your direction when you attach

Use this when you want a sandboxed interactive Claude session without creating a branch or worktree first.

---

## `sb` -- Sandbox Session Management

### `sb list`

Show a dashboard of all managed worktrees and nono sessions.

```bash
nono-dev sb list
```

Output:

```
NAME              PATH                    TYPE    ISSUE/PR  SESSION  STATUS   ATTACH    AGE    CHANGES
issue-42          .worktrees/issue-42     fix     #42       82984b   running  detached  2h30m  +34 -12
bare-api-spike    .                       bare    api-spike c1d2e3   running  detached  12m    +3 -1
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

- A **session name** — same-repo (`fix-123`, `review-530`) or cross-repo (`fix-nono-py-42`)
- A **worktree branch** — `issue-123` or `xrepo-nono-py-issue-42`
- An **issue or PR number** (e.g., `123`) — finds the matching session (fails loudly if the number is ambiguous across types)
- A **session ID** or prefix (e.g., `82984b`)

### `sb stop`

Stop a running nono session. Accepts the same target shapes as `sb attach`.

```bash
nono-dev sb stop <target>
nono-dev sb stop review-530
nono-dev sb stop fix-nono-py-42            # cross-repo
nono-dev sb stop xrepo-nono-py-issue-42    # by branch
nono-dev sb stop 530                       # by number (if unambiguous)
nono-dev sb stop --force fix-123
```

| Flag | Description |
|------|-------------|
| `--force` | SIGKILL instead of SIGTERM |

### `sb inspect`

Show detailed information for a single session, including linked worktree and change stats.

```bash
nono-dev sb inspect <target>
nono-dev sb inspect fix-nono-py-42
nono-dev sb inspect xrepo-nono-py-issue-42
nono-dev sb inspect --json fix-123
```

| Flag | Description |
|------|-------------|
| `--json` | Output as JSON (full session dict plus a `worktree` entry) |

Target resolution follows the same rules as `sb attach`. For `fix` / `feature` sessions, the output includes the worktree branch, path, and `+add/-del` diff stats against its origin base.

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

With `eval "$(nono-dev shell-init)"` in your `.zshrc`, use the shell shortcut directly:

```bash
wt issue-123                      # cd into the worktree
wt 123                            # also works with issue numbers
wt fix-123                        # or session names
wt xrepo-nono-py-issue-42         # cross-repo fix branch
```

If you already have a `wt` command (e.g. from [Worktrunk](https://github.com/foresightpublishing/worktrunk)), the nono-dev helper is installed as `nwt` instead so it doesn't clobber your existing tool.

### `wt start`

Resolve a worktree, launch a sandboxed Claude session in it, and print the worktree path. Used by the `wts` / `nwts` shell shortcut to cd after launching.

```bash
nono-dev wt start <name>
nono-dev wt start --no-rollback <name>
```

| Flag | Description |
|------|-------------|
| `--no-rollback` | Disable nono rollback snapshots for this session |

The session name is derived from the branch: `issue-<N>` → `fix-<N>`, `xrepo-<slug>-issue-<N>` → `fix-<slug>-<N>`, anything else → `feat-<branch>`. If a matching session is already running, the command prints how to attach to it instead of starting a duplicate.

With shell integration:

```bash
wts issue-42          # start sandbox in issue-42 worktree AND cd into it
nwts issue-42         # same (use if `wts` conflicts with another tool)
```

If launched from inside `nd wt start` and a Lima VM is running, you'll be prompted to remount the VM's project sync to the new worktree when the worktree path differs from the VM's current mount.

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

## `graph` -- Knowledge Graph Management

Wraps [Graphify](https://github.com/graphify-ai/graphify) to build, query, and inspect a per-developer knowledge graph of one or more target repositories. See [Knowledge Graph](graph.md) for concepts, configuration, and the agent integration.

### `graph build`

Clean rebuild of the graph for a configured target. Wipes any existing graph, cache, and cluster state under the store, then re-extracts from scratch.

```bash
nono-dev graph build              # only if exactly one target is configured
nono-dev graph build nono
```

Errors if multiple targets are configured and no name is given. Warns if Graphify isn't installed, the profile is missing the read grant, or the binary version differs from the one recorded on a previous build.

### `graph update`

Incremental update. Re-extracts changed files and reuses Graphify's semantic cache.

```bash
nono-dev graph update [target]
```

### `graph query`

Natural-language BFS (or DFS) traversal of the graph.

```bash
nono-dev graph query "where is credential injection handled?"
nono-dev graph query "..." -t nono --dfs --budget 4000
```

| Flag | Default | Description |
|------|---------|-------------|
| `-t`, `--target` | sole target | Target name when multiple graphs are configured |
| `--dfs` | off | Depth-first traversal |
| `--budget N` | `2000` | Cap response at N tokens |

### `graph explain`

Plain-language summary of a node and its neighbors.

```bash
nono-dev graph explain "handle_reverse_proxy" [-t target]
```

### `graph path`

Shortest path between two nodes.

```bash
nono-dev graph path "ReverseProxyCtx" "CapabilitySet" [-t target]
```

### `graph status`

Dashboard of configured targets with freshness signals.

```bash
nono-dev graph status
```

Columns: TARGET, PATH, STORE, BUILT (date), HEAD (short SHA at build), BEHIND (commits from built HEAD to current HEAD), NODES, EDGES, VERSION (flagged on mismatch with the installed Graphify).

---

## `vm` -- Lima VM Management

### VM name resolution

All VM-targeting subcommands (`connect`, `exec`, `mount`, `destroy`) accept the target in two equivalent ways:

- Positional: `nono-dev vm connect linux-gpu`
- Flag: `nono-dev vm connect -m linux-gpu` or `--name linux-gpu`

If no name is given, they auto-select:

1. The VM named `nono-dev` (the default), if it exists
2. Otherwise the sole running VM if exactly one exists
3. Otherwise an error listing the available VMs

Explicit names that don't exist **fail closed** — they will never silently fall back to a different VM. `recreate` does not auto-select a sole unrelated VM either; it falls back only to the configured default (to avoid destroying the wrong VM).

### `vm create`

Create a development VM.

```bash
nono-dev vm create [--os {fedora,ubuntu,debian}] [name] [--extras PKG,PKG] [--mount PATH] [--user USER]
                   [--no-rust] [--shell-setup]
                   [--disk SIZE] [--cpus N] [--memory SIZE]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--os` | `fedora` | Operating system (`fedora`, `ubuntu`, `debian`) |
| `name` | `nono-dev` | VM name (positional) |
| `--extras` | none | Additional packages (comma-separated, distro-native) |
| `--mount` | current directory | Host directory to sync to `~/project` via mutagen |
| `--user` | current macOS user | Username in the VM |
| `--no-rust` | | Skip Rust/Cargo installation |
| `--shell-setup` | | Install zsh, starship, eza, bat, fd, ripgrep, direnv, fzf, tmux with dotfiles |
| `--disk` | `80GiB` | VM disk size (Lima disks are sparse — only used space is written) |
| `--cpus` | `4` | CPU count |
| `--memory` | `8GiB` | RAM |

Rust builds can chew through disk quickly (target artifacts, cargo registry, mutagen caches), so the default disk is sized generously. Because the image is sparse, picking `--disk 120GiB` costs nothing up front.

### `vm connect`

Open an interactive shell inside a VM. Prints the current mutagen mount (host → guest) before opening the shell so you know which project is active.

```bash
nono-dev vm connect [name]
nono-dev vm connect -m linux-gpu
```

### `vm exec`

Run a command inside a VM via SSH. Used to drive Rust builds, tests, and other Linux-only operations from the macOS host (or from inside an `nd fix` / `nd wt start` sandbox session).

```bash
nono-dev vm exec [-m name] [--cwd DIR] -- <cmd> [args...]
nono-dev vm exec -- uname -a
nono-dev vm exec --cwd / -- df -h /
nono-dev vm exec -m linux-gpu -- cargo build --release
```

| Flag | Default | Description |
|------|---------|-------------|
| `-m`, `--name` | auto-select | VM name |
| `--cwd` | `~/project` | Working directory inside the VM |

Internally uses `ssh -F ~/.lima/<vm>/ssh.config lima-<vm>` — never mutates the user's `~/.ssh/config`, and works from inside a sandbox with a narrow `~/.lima` grant. If the VM has never been started on this machine, an error points you to run `nd vm connect` first to bring it up.

### `vm status`

List all Lima VMs and their current state.

```bash
nono-dev vm status
```

### `vm mount`

Show or switch the host directory synced into the VM's `~/project`. Two positionals — both optional — are disambiguated by shape:

```bash
nono-dev vm mount                                    # show default VM's mount
nono-dev vm mount linux-gpu                          # show that VM's mount
nono-dev vm mount /path/to/repo                      # switch default VM's sync to a path
nono-dev vm mount linux-gpu /path/to/repo            # switch that VM's sync to a path
nono-dev vm mount -m linux-gpu /path/to/repo         # same, flag form
```

| Flag | Default | Description |
|------|---------|-------------|
| `-m`, `--name` | auto-select | VM name (alias for positional) |
| `--user` | current macOS user | Username in the VM |

An arg starting with `/`, `./`, `../`, `~`, containing a path separator, or naming an existing directory is treated as a path. Anything else is treated as a VM name. If you need to force VM-name interpretation (e.g. a VM whose name collides with a path shape), use `-m <name>`.

Switching terminates the existing mutagen sync and starts a new one pointing at the given directory. The VM itself is not restarted.

### `vm destroy`

Delete a VM. Asks for confirmation unless `--force`.

```bash
nono-dev vm destroy [name] [--force]
nono-dev vm destroy -m linux-gpu
```

### `vm recreate`

Destroy and recreate a VM in one step. Accepts the same flags as `vm create` plus `-m/--name`.

```bash
nono-dev vm recreate [name] [--os ...] [--extras ...] [--disk ...] [--cpus ...] [--memory ...] [--shell-setup]
```

Unlike the other VM subcommands, `recreate` does not auto-select a sole VM — omitting the name always resolves to the configured default (`nono-dev`), to avoid destroying an unrelated VM by accident.

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

1. Installs shell tools via Homebrew (starship, eza, bat, fd, ripgrep, direnv, tmux, z, zsh-autosuggestions)
2. Installs the MesloLGS Nerd Font for starship icons
3. Deploys `.zshrc`, `.zprofile`, `.direnvrc`, and `.tmux.conf` to your home directory
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

Install nono-dev as a globally available command via `uv tool`, and copy the nono-dev sandbox profile to `~/.config/nono/profiles/nono-dev.json`.

```bash
nono-dev install
nono-dev install --force
```

| Flag | Description |
|------|-------------|
| `--force` | Reinstall even if already installed |

The installed profile extends `claude-code` with read access to `~/.lima`, `~/.config/gh`, `~/.ssh`, and read-file access to `~/.gitconfig` / `~/.gitconfig.local`. It's what every `fix` / `feature` / `triage` / `review` / `wt start` sandbox session uses by default, and what allows `nd vm exec` to SSH into Lima VMs from inside a sandbox.

Run `nono-dev install --force` after pulling a new version of nono-dev to refresh both the binary and the profile.

### `shell-init`

Print (or install) shell integration for nono-dev.

```bash
eval "$(nono-dev shell-init)"       # load in the current shell
nono-dev shell-init --install       # append eval to ~/.zshrc (idempotent)
```

Provides:

- `nwt <name>` — cd into a worktree. Always installed.
- `nwts <name>` — launch a sandbox in a worktree AND cd into it. Always installed.
- `wt` and `wts` — same as above, installed **only** if you don't already have `wt` / `wts` commands (e.g. from Worktrunk). Tab completion binds to whichever shortcut is actually in place.
- `compdef` for `nono-dev` and `nd` so Tab completes subcommands, session names, worktree branches, VM names, and issue numbers.

See `nono-dev --complete` (hidden) for the completion backend — it's a pure-Python walk of the argparse tree with live lookups for session/worktree/VM names.
