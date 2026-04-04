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
