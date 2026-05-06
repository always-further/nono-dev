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
- Commit incrementally with clear commit messages. If the user asks you to use `nd git commit` to draft the message, run it with `--no-sign` because you are inside a sandbox and the signing key is not reachable: `nd git commit --no-sign`.
- The nono project is a security tool: do not introduce code that weakens sandbox enforcement, mishandles credentials, or allows unsanitized user input to reach shell commands.
- The core nono crate must not accept CLI user messages directly.
- Do not use `unwrap` or `expect` on user input or external data. Use `NonoError` with Results and proper error propagation.
- No path traversal vulnerabilities.

## Knowledge graph

A Graphify knowledge graph of this project is available at:

    {{graph_path}}

Before exploratory Read/Grep/Glob calls, consult the graph to orient
yourself, locate candidate files, and surface design rationale:

    nd graph query "how does X work?"
    nd graph explain "SomeType"
    nd graph path "TypeA" "TypeB"

Trust `EXTRACTED` edges (confidence 1.0); treat `INFERRED` (0.4-0.9) as
hints; verify `AMBIGUOUS` (0.1-0.3) against source.

## Getting Started

Wait for the user to describe what they want to build. When they attach to this session, discuss the approach before writing code.
