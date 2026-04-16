# Workflows

nono-dev combines git worktrees with nono sandbox to give each task an isolated workspace and a sandboxed AI agent. All agent sessions run detached -- they continue working in the background while you do other things.

## Issue Triage

Quickly assess incoming issues without context-switching:

```bash
nono-dev triage 42
```

The agent retrieves the issue, searches for duplicates across the nono-family repos, checks documentation, and **drafts** a follow-up comment to `triage-42.md` in the current directory. The draft is **not** posted automatically — review/edit it, then post:

```bash
gh issue comment 42 -R always-further/nono --body-file triage-42.md
```

Check on the session while it's running:

```bash
nono-dev sb attach 42
```

## Bug Fix

End-to-end: from issue to a branch with a fix ready for review.

```bash
# Start the fix
nono-dev fix 123

# Check progress
nono-dev sb status

# Attach to guide the agent or review the fix
nono-dev sb attach 123

# When done, the worktree has commits on branch issue-123
wt issue-123
git log --oneline
git push -u origin issue-123
```

Clean up after the PR is merged:

```bash
nono-dev wt cleanup issue-123
```

### Cross-repo fixes

If the issue lives in a sibling repo (`nono-py`, `nono-ts`, `nono-go`, etc.), pass the full URL:

```bash
nono-dev fix https://github.com/always-further/nono-py/issues/42
```

This creates a **namespaced** worktree and session so a number collision with the core repo can't clash:

- Worktree: `.worktrees/xrepo-nono-py-issue-42`
- Branch: `xrepo-nono-py-issue-42`
- Session: `fix-nono-py-42`

A warning is printed noting the worktree is created in the current repo's `.worktrees/` directory rather than in the sibling repo's checkout — for a useful branching base, `cd` into the `nono-py` checkout first.

### Starting a sandbox in an existing worktree

If a worktree already exists (e.g. you branched manually, or you're resuming after cleanup removed an older session), use `wt start` / `wts`:

```bash
wts issue-123                       # cd in AND start a sandbox
nono-dev wt start my-feature        # without the shell shortcut
```

Session naming follows the branch shape: `issue-N` → `fix-N`, `xrepo-<slug>-issue-N` → `fix-<slug>-N`, anything else → `feat-<branch>`. If a matching session is already running, you're pointed at it rather than starting a duplicate.

## PR Review

Get a thorough review drafted while you work on other things:

```bash
nono-dev review 456
nono-dev review https://github.com/always-further/nono-py/pull/7   # cross-repo
```

The agent fetches the diff, reviews for correctness and security, and drafts a comment. Attach to approve or edit before it posts:

```bash
nono-dev sb attach 456
nono-dev sb attach review-nono-py-7       # cross-repo session
```

## Feature Development

Set up an isolated workspace for a new feature:

```bash
nono-dev feature auth-improvements
```

Attach and start directing the work:

```bash
nono-dev sb attach auth-improvements
```

The agent has write access only to the worktree at `.worktrees/auth-improvements`, keeping your main checkout untouched.

## Parallel Work

Run multiple tasks simultaneously. Each gets its own worktree and sandbox:

```bash
nono-dev fix 101
nono-dev fix 102
nono-dev review 200
nono-dev feature new-api
```

Monitor everything from one place:

```bash
nono-dev sb status
```

```
NAME              PATH                    TYPE    ISSUE/PR  SESSION  STATUS   ATTACH    AGE    CHANGES
issue-101         .worktrees/issue-101    fix     #101      82984b   running  detached  1h     +34 -12
issue-102         .worktrees/issue-102    fix     #102      a1b2c3   running  detached  45m    +0 -0
new-api           .worktrees/new-api      feature -         d4e5f6   running  detached  30m    +15 -3
review-200        -                       review  #200      f7a8b9   running  detached  20m    -
```

## Managing Sessions

```bash
# Stop a session
nono-dev sb stop review-200

# Stop by issue number
nono-dev sb stop 200

# Force stop
nono-dev sb stop --force fix-101

# Clean up old session files
nono-dev sb prune
nono-dev sb prune --older-than 7
```

## Worktree Navigation

With shell integration (`eval "$(nono-dev shell-init)"`):

```bash
wt issue-101                         # cd into the worktree
wt 101                               # also works with issue numbers
wt new-api                           # or branch names
wt xrepo-nono-py-issue-42            # cross-repo fix branch

wts issue-101                        # cd AND start a sandbox in it
```

If you already have a `wt` from Worktrunk or another tool, use `nwt` / `nwts` instead.

Without shell integration:

```bash
cd $(nono-dev wt cd issue-101)
```

## Cleanup

Remove completed worktrees:

```bash
# Remove one
nono-dev wt cleanup issue-101

# Remove all with no uncommitted changes
nono-dev wt cleanup --all

# Force remove everything
nono-dev wt cleanup --all --force
```

## Running Linux Builds and Tests

Lima VMs let you run Linux-only builds and tests (notably anything using Landlock) against the worktree's files, synced from macOS via mutagen.

```bash
# Create a VM once (one per project or shared across projects)
nono-dev vm create --shell-setup

# Open an interactive shell for longer sessions
nono-dev vm connect

# Run one-off commands from the host OR from inside a sandboxed agent
nono-dev vm exec -- uname -a
nono-dev vm exec -- cargo build --release
nono-dev vm exec --cwd / -- df -h /
nono-dev vm exec -m linux-gpu -- cargo test --workspace
```

`vm exec` uses SSH into the VM (via Lima's per-VM `~/.lima/<vm>/ssh.config`), so it works identically from the host shell and from inside an `nd fix` / `nd wt start` sandbox session — the sandbox profile grants exactly enough of `~/.lima` for this to work.

### Switching the synced project

Each VM syncs one host directory at a time. When you switch between worktrees, remount:

```bash
nono-dev vm mount                                    # see what's synced now
nono-dev vm mount ~/dev/nono/.worktrees/issue-42     # switch to a different worktree
```

`wt start` (and `wts`) will prompt you to remount automatically when the target worktree differs from the VM's current sync.

## Graph-Aware Fix and Feature

If you've configured a [knowledge graph](graph.md) for the target repo, `nd fix`, `nd feature`, `nd review`, and `nd wt start` automatically inject the graph's absolute path into the agent's system prompt. Before any exploratory Read/Grep/Glob pass, the agent can traverse the graph to orient itself.

First-time setup (per repo, per developer):

```bash
uv tool install graphifyy   # once, host-side
nd install --force          # pick up the profile read grant
# Add [graphs.<name>] to nono-dev.toml, then:
nd graph build <name>
```

Day-to-day:

```bash
nd graph update <name>      # after pulling new commits on the target repo
nd graph status             # check BEHIND column before starting a big session
nd fix 123                  # agent's prompt now knows where graph.json lives
```

Interactively check what the graph knows without launching a session:

```bash
nd graph query "where is credential injection handled?"
nd graph explain "handle_reverse_proxy"
nd graph path "ReverseProxyCtx" "CapabilitySet"
```

See [Knowledge Graph](graph.md) for the full reference.

## Rollback

All sessions run with nono's rollback enabled by default. If an agent makes unwanted changes, nono's snapshot system lets you restore the previous state:

```bash
nono rollback
```

Configure rollback behavior in `nono-dev.toml`:

```toml
[rollback]
enabled = true
dest = "~/.nono/rollbacks"
exclude = [".git", "node_modules"]
```

See [Configuration](configuration.md) for details.
