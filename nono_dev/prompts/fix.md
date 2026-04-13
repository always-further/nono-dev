# Issue Fix

You are working on a fix for a GitHub issue in the nono project. You are operating inside a dedicated git worktree with sandbox protections.

## Steps

1. Use `gh issue view <number> -R <repo>` to retrieve the full issue details.
2. Analyze the codebase to understand the root cause. Read relevant source files, trace the code paths involved, and identify where the bug or missing feature lives.
3. If more information is required first, construct a friendly human sounding comment that can be posted to the issue to gain more context and information. Before posting, ask the user if they are okay to proceed with you posting the issue. 
4. Implement the fix:
   - Make minimal, focused changes that address the issue.
   - Follow existing code conventions and patterns.
   - Do not introduce unrelated changes.
5. Write or update tests to cover the fix where appropriate.
6. Run CI tests locally to ensure your changes do not break existing functionality: `make ci`
7. Run formatting and lint checks: `make fmt` and `make clippy`
8. Once work is completed, ask the user before proceeding to making a pull request. Never go direct to the pull request. 
9. Commit your changes with a clear commit message referencing the issue number (e.g., `fix: resolve panic on empty config (#<number>)`), and in the body `Resolves: #123`  and always use the `-s` flag to sign your commits. Never Reference Claude as a co-author. 
10. Push the branch when the fix is ready, But confirm with the user first. 


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

Built-in profiles (e.g. `claude-code`, `codex`) reference groups by name under `"security": { "groups": [...] }`. When fixing policy bugs, check whether the affected path should be added to an existing group or warrants a new one.

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
