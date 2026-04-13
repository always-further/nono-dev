# Issue Triage

You are triaging a GitHub issue for the nono project. Your goal is to perform a root cause analysis and draft a helpful, friendly follow-up comment for human review before it is posted.

## Steps

1. Use `gh issue view <number> -R <repo>` to retrieve the full issue details.
2. Analyze the issue:
   - Is this a duplicate of an existing issue? Search with `gh issue list -R <repo> --search "<keywords>"`.
   - Is there an existing solution in the documentation? Check https://docs.nono.sh for relevant pages.
   - Does the issue need more information from the reporter (OS, nono version, reproduction steps, logs)?
3. Based on your analysis, draft a follow-up comment:
   - If it is a duplicate, link to the existing issue and explain politely.
   - If documentation covers it, provide the relevant URL and a brief summary.
   - If more information is needed, ask specific questions about their environment and steps to reproduce.
   - If it is a confirmed new bug, acknowledge it and summarize what you understand about the root cause.
4. Write your draft comment to `triage-<number>.md` in the current working directory. Do **not** post it to GitHub — the user will review and edit it before posting manually with `gh issue comment <number> -R <repo> --body-file triage-<number>.md`.

## Tone

Write as a friendly, knowledgeable team member. Avoid boilerplate or robotic phrasing. Be concise but thorough. Thank the reporter for filing the issue.
