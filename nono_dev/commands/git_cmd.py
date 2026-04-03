"""AI-assisted git operations."""

import subprocess
import sys

from nono_dev import gemini


COMMIT_SYSTEM_PROMPT = """\
You generate git commit messages following the Conventional Commits specification.

Format:
- First line: type(scope): description
- Blank line
- Body: bullet points explaining what changed and why

Types: feat, fix, refactor, docs, test, chore, ci, perf, build, style

Rules:
- Title must be under 72 characters
- Title uses imperative mood ("add", not "added" or "adds")
- Scope is optional but preferred when changes are focused on one area
- Body bullets start with "- "
- Be specific about what changed, not vague
- Output plain text only, no markdown formatting, no backticks
- Do not wrap the output in a code block
"""


def add_parser(subparsers):
    """Register the 'git' command group."""
    git_parser = subparsers.add_parser("git", help="AI-assisted git operations")
    git_sub = git_parser.add_subparsers(dest="git_command")
    git_parser.set_defaults(func=lambda _: git_parser.print_help())

    commit_parser = git_sub.add_parser(
        "commit", help="Generate a commit message with AI and commit",
    )
    commit_parser.set_defaults(func=run_commit)


def _get_diff():
    """Get the combined diff of staged and unstaged changes."""
    # Unstaged changes
    unstaged = subprocess.run(
        ["git", "diff"],
        capture_output=True, text=True,
    )
    # Staged changes
    staged = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True, text=True,
    )
    return (unstaged.stdout + staged.stdout).strip()


def _get_untracked():
    """Get list of untracked files."""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _stage_all():
    """Stage all changes."""
    subprocess.run(["git", "add", "-A"], check=True)


def _commit(message):
    """Commit with sign-off."""
    result = subprocess.run(
        ["git", "commit", "-s", "-m", message],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Commit failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout.strip())


def run_commit(_args):
    diff = _get_diff()
    untracked = _get_untracked()

    if not diff and not untracked:
        print("No changes to commit.")
        return

    prompt_parts = []
    if diff:
        prompt_parts.append(f"Diff:\n{diff}")
    if untracked:
        prompt_parts.append(f"New untracked files:\n{untracked}")

    prompt = "Generate a commit message for these changes:\n\n" + "\n\n".join(prompt_parts)

    print("Generating commit message...")
    message = gemini.generate(prompt, system_prompt=COMMIT_SYSTEM_PROMPT).strip()

    # Strip any markdown code fences the model might add
    if message.startswith("```"):
        lines = message.splitlines()
        lines = [l for l in lines if not l.startswith("```")]
        message = "\n".join(lines).strip()

    print()
    print(message)
    print()

    answer = input("Commit with this message? [Y/n/e(dit)] ").strip().lower()
    if answer == "n":
        print("Aborted.")
        return
    if answer == "e":
        message = _edit_message(message)
        if not message:
            print("Aborted.")
            return

    _stage_all()
    _commit(message)


def _edit_message(message):
    """Open the message in an editor for the user to modify."""
    import os
    import tempfile

    editor = os.environ.get("EDITOR", "vi")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".gitcommit", delete=False,
    ) as f:
        f.write(message)
        tmp_path = f.name

    try:
        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0:
            return None
        with open(tmp_path) as f:
            edited = f.read().strip()
        return edited if edited else None
    finally:
        os.unlink(tmp_path)
