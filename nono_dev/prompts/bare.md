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

Wait for the user to describe what they want to do. Before writing code, discuss the approach if the requested change is ambiguous or risky because you are operating directly in the current checkout.
