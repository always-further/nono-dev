# Issue Fix

You are working on a fix for a GitHub issue in the **nono** project, a Rust-based security sandbox CLI. You are operating inside a dedicated git worktree with sandbox protections.

## Repositories

The nono project spans several related repositories under https://github.com/always-further:

- `always-further/nono` — the core Rust sandbox CLI
- `always-further/nono-ts` — TypeScript bindings / SDK
- `always-further/nono-py` — Python bindings / SDK
- `always-further/nono-go` — Go bindings / SDK
- `always-further/nono-dev` — developer tooling (this workflow lives here)

Bugs can affect sibling repos; search and cross-link where relevant.

## Determining the target repo

The user message contains either a plain issue number (e.g. `576`) or a full GitHub URL (e.g. `https://github.com/always-further/nono-py/issues/42`).

- If it is a **URL**, extract `<org>/<repo>` and `<number>` from it and use that repo for all `gh` operations.
- If it is a **plain number**, resolve the current worktree's repo with `gh repo view --json nameWithOwner -q .nameWithOwner` (or `git remote get-url origin`).

Throughout this prompt, `<repo>` refers to the repo you resolved above, and `<number>` to the issue number.

## Steps

1. Use `gh issue view <number> -R <repo>` to retrieve the full issue details.
2. **Query the graph first.** Before reading code or searching GitHub, use the knowledge graph to orient yourself:
   - `nd graph query "<summary of the issue symptoms>"` — finds related issues, PRs, and code in one local lookup.
   - `nd graph explain "SomeModule"` — understand a module's role and connections.
   - `nd graph path "Issue #<related>" "SomeType"` — trace how a past issue connects to the code area.
   The graph contains ingested issues and PRs alongside code, so related issue searches and code location are often answered here without API calls or broad file reads.
3. Analyze the codebase to understand the root cause. Read relevant source files, trace the code paths involved, and identify where the bug or missing feature lives.
3. If more information is required first, construct a friendly human sounding comment that can be posted to the issue to gain more context and information. Before posting, ask the user if they are okay to proceed with you posting the issue. 
4. Implement the fix:
   - Make minimal, focused changes that address the issue.
   - Follow existing code conventions and patterns.
   - Do not introduce unrelated changes.
5. Write or update tests to cover the fix where appropriate.
6. Run CI tests locally to ensure your changes do not break existing functionality: `make ci`
7. Run formatting and lint checks: `make fmt` and `make clippy`
8. Once work is completed, ask the user before proceeding to making a pull request. Never go direct to the pull request. 
9. Commit your changes with a clear commit message referencing the issue number (e.g., `fix: resolve panic on empty config (#<number>)`), and in the body `Resolves: #123`  and always use the `-s` flag to sign your commits. Never reference the AI agent as a co-author. If the user asks you to use `nd git commit` to draft the message, run it with `--no-sign` because you are inside a sandbox and the signing key is not reachable: `nd git commit --no-sign`. 
10. Push the branch when the fix is ready, But confirm with the user first. 


## Knowledge graph

A Graphify knowledge graph of this project is available at:

    {{graph_path}}

Before doing exploratory Read/Grep/Glob calls, consult the graph to locate
candidate files, understand call relationships, and surface design
rationale. Query it with:

    nd graph query "where is credential injection handled?"
    nd graph explain "handle_reverse_proxy"
    nd graph path "ReverseProxyCtx" "CapabilitySet"

Trust `EXTRACTED` edges (confidence 1.0). Treat `INFERRED` (0.4-0.9) as
hints. Verify `AMBIGUOUS` (0.1-0.3) against source.

## Project Structure

```
crates/
  nono/             # Core sandboxing library
  nono-cli/         # CLI binary
  │  src/           # ~50 source files
  │  data/          # policy.json — built-in groups and profiles
  │  tests/         # Rust unit/integration tests
  nono-proxy/       # Network filtering proxy
bindings/c/         # C FFI (nono-ffi)
tests/
  integration/      # Bash integration test scripts
  run_integration_tests.sh
```

## Key Files by Bug Type

| Bug type | File |
|----------|------|
| Policy / permission issues | `crates/nono-cli/data/policy.json` |
| CLI flags / argument parsing | `crates/nono-cli/src/cli.rs` |
| Sandbox enforcement behavior | `crates/nono/src/sandbox.rs` |
| Capability definitions | `crates/nono-cli/src/capability_ext.rs` |
| Session lifecycle (ps / stop / prune) | `crates/nono-cli/src/session_commands.rs` |
| Execution strategy | `crates/nono-cli/src/exec_strategy.rs` |
| PTY / interactive shell | `crates/nono-cli/src/pty_proxy.rs` |
| Network proxy | `crates/nono-proxy/src/` |
| Policy group introspection | `crates/nono-cli/src/policy_cmd.rs` |

## policy.json Schema

Policy groups live under the top-level `"groups"` key:

```json
"git_config": {
  "description": "Read access to git configuration files",
  "allow": {
    "read": ["$HOME/.gitconfig", "$HOME/.config/git/ignore"],
    "read_file": ["$HOME/.config/git/config"]
  }
}
```

Built-in profiles (e.g. `claude`, `codex`) reference groups by name under `"security": { "groups": [...] }`. When fixing policy bugs, check whether the affected path should be added to an existing group or warrants a new one.

## Diagnostic Commands

```bash
nono policy groups <group>       # inspect a policy group's allow/deny rules
nono policy profile <profile>    # inspect a built-in profile and its groups
nono learn -- <command>          # trace what filesystem paths a command needs
```

## Common Bug Patterns

- **Process introspection failures** — `/proc/self/*` denied under Landlock causes SIGABRT in some runtimes (e.g. Bun). Fix: add a `proc_self` read rule to the relevant profile/group.
- **Landlock vs Seatbelt divergence** — Linux Landlock is stricter than macOS Seatbelt; a profile that works on macOS may fail on Linux. Reproduce on the correct platform before fixing.
- **Network proxy connection drops** — First connection succeeds, subsequent ones fail silently. Usually a connection pool or keep-alive issue in `nono-proxy`.
- **Environment variable loss** — Some runtimes re-exec themselves and lose inherited env vars inside the sandbox. Check `exec_strategy.rs` for env passthrough.

## Security Model

The nono project is a security tool. Be especially careful about:
- No user-controlled input reaching shell commands without sanitization.
- No path traversal vulnerabilities.
- No weakening of sandbox enforcement.
- The core nono crate must not accept CLI user messages directly.
- No use of unwrap or expect on user input or external data.
- Use `NonoError` for all error handling, with Results and proper error propagation.

## Constraints

- You are working inside a sandboxed worktree. All file changes must be within this directory.
- Use `gh` CLI for all GitHub interactions.
