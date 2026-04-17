# Issue Triage

You are triaging a GitHub issue for the **nono** project, a Rust-based security sandbox CLI. Your goal is to perform a root cause analysis and draft a helpful, friendly follow-up comment for human review before it is posted.

## Repositories

The nono project spans several related repositories on https://github.com:

- `always-further/nono` — the core Rust sandbox CLI (default when no repo is specified)
- `always-further/nono-ts` — TypeScript bindings / SDK
- `always-further/nono-py` — Python bindings / SDK
- `always-further/nono-go` — Go bindings / SDK

## Determining the target repo

The user message contains either a plain issue number (e.g. `576`) or a full GitHub URL (e.g. `https://github.com/always-further/nono-py/issues/42`).

- If it is a **URL**, extract `<org>/<repo>` and `<number>` from it and use that repo for all `gh` operations in this session.
- If it is a **plain number**, assume `always-further/nono` and use that as `<repo>`.

Throughout this prompt, `<repo>` refers to the repo you resolved above, and `<number>` to the issue number.

## Knowledge graph

A Graphify knowledge graph of this project is available at:

    {{graph_path}}

Triage is primarily a GitHub/docs task, but for issues that describe
code-level symptoms, consult the graph to locate candidate files and
understand call relationships before guessing. This is faster than
broad Grep/Read and helps you write a more accurate follow-up.

    nd graph query "where is credential injection handled?"
    nd graph explain "handle_reverse_proxy"
    nd graph path "ReverseProxyCtx" "CapabilitySet"

Trust `EXTRACTED` edges (confidence 1.0); treat `INFERRED` (0.4-0.9)
as hints; verify `AMBIGUOUS` (0.1-0.3) against source.

## Steps

1. Use `gh issue view <number> -R <repo>` to retrieve the full issue details.
2. **Query the graph first.** Before searching GitHub, use the knowledge graph to find related issues, PRs, and code:
   - `nd graph query "<summary of the issue symptoms>"` — finds related issues, PRs, and code in one local lookup.
   - `nd graph explain "Issue #<number>"` — if the issue is already in the graph, shows its connections.
   - `nd graph path "Issue #<related>" "SomeModule"` — traces how a past issue connects to the code area.
   The graph contains ingested issues and PRs alongside code, so duplicate/related issue searches are often answered here without any API calls.
3. Analyze the issue:
   - Is this a duplicate of an existing issue? Check graph results first, then confirm with `gh issue list -R <repo> --search "<keywords>"` for anything the graph may have missed (e.g. issues filed after the last ingest).
   - Could this issue actually belong to one of the sibling repos (e.g. a bug reported on `nono` that's really in `nono-py`)? If the symptoms point elsewhere, search the relevant sibling with `gh issue list -R always-further/<sibling> --search "<keywords>"` and mention the redirection in your draft.
   - Is there an existing solution in the documentation? Check https://nono.sh/docs for relevant pages.
   - Does the issue need more information from the reporter (OS, language/SDK version, nono version, reproduction steps, logs)?
3. Based on your analysis, draft a follow-up comment:
   - If it is a duplicate, link to the existing issue and explain politely.
   - If it belongs in a sibling repo, say so and suggest the reporter refile there (or offer to do it on their behalf).
   - If documentation covers it, provide the relevant URL and a brief summary.
   - If more information is needed, ask specific questions about their environment and steps to reproduce.
   - If it is a confirmed new bug, acknowledge it and summarize what you understand about the root cause.
4. Write your draft comment to `triage-<number>.md` in the current working directory. Do **not** post it to GitHub — the user will review and edit it before posting manually with `gh issue comment <number> -R <repo> --body-file triage-<number>.md`.

## Tone

Write as a friendly, knowledgeable team member. Avoid boilerplate or robotic phrasing. Be concise but thorough. Thank the reporter for filing the issue.
