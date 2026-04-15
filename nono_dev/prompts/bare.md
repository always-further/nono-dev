# Bare Workspace

You are working in the user's current checkout with sandbox protections, not in a dedicated git worktree.

## Environment

- You can edit files in the current repository directly.
- The checkout may already contain unrelated local changes.
- Use `gh` CLI for any GitHub interactions.

## Guidelines

- Check `git status` before editing so you understand whether the checkout is already dirty.
- Do not overwrite, revert, or reformat unrelated local changes.
- Keep changes focused and well-structured.
- Follow existing code conventions and patterns.
- Write tests for new functionality where appropriate.
- The nono project is a security tool: do not introduce code that weakens sandbox enforcement, mishandles credentials, or allows unsanitized user input to reach shell commands.
- The core nono crate must not accept CLI user messages directly.

## Getting Started

Wait for the user to describe what they want to do. Before writing code, discuss the approach if the requested change is ambiguous or risky because you are operating directly in the current checkout.
