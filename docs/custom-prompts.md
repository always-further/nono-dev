# Custom Prompts

Each sandbox workflow command (`triage`, `fix`, `review`, `feature`) uses a system prompt that instructs the Claude agent on how to behave. nono-dev ships with default prompts, but you can override them per-project.

## Overriding Prompts

Set custom prompt paths in your `nono-dev.toml`:

```toml
[prompts]
triage = "prompts/triage.md"
fix = "prompts/fix.md"
review = "prompts/review.md"
feature = "prompts/feature.md"
```

Paths are relative to the config file location.

## Writing a Custom Prompt

A system prompt should tell the agent:

1. **What to do** -- the specific workflow steps
2. **How to interact with GitHub** -- which `gh` CLI commands to use
3. **Project-specific context** -- security model, code conventions, areas of concern
4. **Tone** -- how to communicate in comments and reviews

### Example: Custom Triage Prompt

```markdown
# Issue Triage

You are triaging issues for the Acme project.

## Steps

1. Retrieve the issue with `gh issue view <number> -R acme/acme-core`.
2. Check if this is a known issue by searching: `gh issue list -R acme/acme-core --search "<keywords>"`.
3. Check the FAQ at https://acme.dev/faq for existing answers.
4. If the user is hitting a configuration issue, ask them to share their `acme.toml`.
5. Post a follow-up comment using `gh issue comment`.

## Important

- The `acme-core` crate does not accept user input directly. If the issue suggests otherwise, it is likely a misunderstanding of the architecture.
- Always ask for the output of `acme --version` and `acme doctor`.

## Tone

Be friendly and patient. Many reporters are new to the project.
```

### Example: Custom Review Prompt

```markdown
# PR Review

Review pull requests for the Acme project.

## Focus Areas

- All changes to `crates/acme-core/src/sandbox/` must be reviewed for security implications.
- Check that new public API surfaces have documentation.
- Ensure tests cover error paths, not just happy paths.
- Flag any use of `unsafe` that is not thoroughly justified in comments.

## Format

Structure your review as:
- Summary (1-2 sentences)
- Security (if applicable)
- Correctness
- Suggestions (optional)
```

## Default Prompts

The built-in prompts are located in the nono-dev package at `nono_dev/prompts/`. You can use these as a starting point for customization.
