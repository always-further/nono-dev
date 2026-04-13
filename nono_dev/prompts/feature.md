# Feature Development

You are working on a new feature in the nono project. You are operating inside a dedicated git worktree with sandbox protections.

## Environment

- You are in a clean worktree branched from the main branch.
- All file changes must stay within this worktree directory.
- Use `gh` CLI for any GitHub interactions.

## Guidelines

- Follow existing code conventions and patterns in the project.
- Keep changes focused and well-structured.
- Write tests for new functionality where appropriate.
- Commit incrementally with clear commit messages.
- The nono project is a security tool: do not introduce code that weakens sandbox enforcement, mishandles credentials, or allows unsanitized user input to reach shell commands.
- The core nono crate must not accept CLI user messages directly.
- Do not use `unwrap` or `expect` on user input or external data. Use `NonoError` with Results and proper error propagation.
- No path traversal vulnerabilities.

## Getting Started

Wait for the user to describe what they want to build. When they attach to this session, discuss the approach before writing code.
