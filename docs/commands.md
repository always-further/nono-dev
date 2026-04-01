# Commands

## Sandbox Workflow Commands

### `triage`

Spawn a sandboxed Claude agent to triage a GitHub issue.

```bash
nono-dev triage <issue-number>
```

The agent retrieves the issue, checks for duplicates and existing documentation, and posts a friendly follow-up comment asking for more information or pointing to a solution.

Runs in detached mode. Use `nono-dev attach <issue-number>` or `nono attach <session-id>` to connect.

### `fix`

Create a git worktree and spawn a sandboxed agent to fix a GitHub issue.

```bash
nono-dev fix <issue-number>
```

This command:
1. Creates a git worktree at `<worktree-dir>/issue-<N>` with branch `issue-<N>`
2. Launches Claude in a nono sandbox with write access to the worktree
3. The agent retrieves the issue, analyzes the codebase, and implements a fix

If the worktree or branch already exists, the existing worktree is reused.

### `review`

Spawn a sandboxed Claude agent to review a GitHub pull request.

```bash
nono-dev review <pr-number>
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

### `attach`

Reconnect to a running nono session.

```bash
nono-dev attach <target>
```

The target can be:
- An **issue or PR number** (e.g., `42`) -- finds the matching session by name
- A **session ID** or prefix (e.g., `82984b`) -- connects directly

If multiple sessions match a number, all matches are listed so you can pick the right one.

### `status`

Show a dashboard of all managed worktrees and nono sessions.

```bash
nono-dev status
```

Output:

```
WORKTREE          TYPE      ISSUE/PR   SESSION    STATUS    CHANGES
issue-42          fix       #42        82984b     running   +34 -12
issue-99          fix       #99        -          stopped   +120 -45
feat-new-api      feature   -          a3f21c     running   +200 -0
-                 triage    #42        f7a8b9     running   -
-                 review    #88        c1d2e3     stopped   -
```

The `CHANGES` column shows uncommitted line additions and deletions in each worktree.

### `cleanup`

Remove worktrees and their branches.

```bash
# Remove a specific worktree
nono-dev cleanup issue-42

# Remove all managed worktrees
nono-dev cleanup --all

# Skip confirmation prompts
nono-dev cleanup --all --force
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

## VM Commands

These commands manage OrbStack Linux VMs for Rust cross-compilation.

### `create`

Create a development VM.

```bash
nono-dev create [--os {debian,ubuntu}] [name] [--extras PKG,PKG] [--mount PATH] [--user USER] [--no-rust]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--os` | `debian` | Operating system |
| `name` | `nono-dev` | VM name |
| `--extras` | none | Additional apt packages (comma-separated) |
| `--mount` | current directory | Host directory to mount as `~/project` |
| `--user` | current macOS user | Username in the VM |
| `--no-rust` | | Skip Rust/Cargo installation |

### `connect`

Open an interactive shell inside a VM.

```bash
nono-dev connect [name]
```

### `vm-status`

List all OrbStack VMs and their current state.

```bash
nono-dev vm-status
```

### `destroy`

Delete a VM.

```bash
nono-dev destroy [name] [--force]
```

### `recreate`

Destroy and recreate a VM in one step. Accepts the same flags as `create`.

```bash
nono-dev recreate [name] [--os ...] [--extras ...] [--mount ...]
```
