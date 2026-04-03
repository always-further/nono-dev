# Workflows

nono-dev combines git worktrees with nono sandbox to give each task an isolated workspace and a sandboxed AI agent. All agent sessions run detached -- they continue working in the background while you do other things.

## Issue Triage

Quickly assess incoming issues without context-switching:

```bash
nono-dev triage 42
```

The agent retrieves the issue, searches for duplicates, checks documentation, and posts a follow-up comment. Check on it later:

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

## PR Review

Get a thorough review drafted while you work on other things:

```bash
nono-dev review 456
```

The agent fetches the diff, reviews for correctness and security, and drafts a comment. Attach to approve or edit before it posts:

```bash
nono-dev sb attach 456
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
wt issue-101            # cd into the worktree
wt 101                  # also works with issue numbers
wt new-api              # or branch names
```

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
