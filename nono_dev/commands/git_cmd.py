"""AI-assisted git operations."""

import subprocess
import sys

from nono_dev import gemini, style


COMMIT_SYSTEM_PROMPT = """\
You generate git commit messages following the Conventional Commits specification.

Format:

Natural relaxed description of the changes, ideally 50 characters or less
- First line: type(scope): description
- Blank line
- Body: optional detailed description using naural language, prose and only sparse use of bullet points. Use markdown formatting if helpful.

Types: feat, fix, refactor, docs, test, chore, ci, perf, build, style

Rules:
- Title must be under 72 characters and all lowercase
- Title uses imperative mood ("add", not "added" or "adds")
- Scope is optional but preferred when changes are focused on one area
- Body bullets start with "- "
- Be specific about what changed, not vague
- No emojis or non-standard formatting
"""


def add_parser(subparsers):
    """Register the 'git' command group."""
    git_parser = subparsers.add_parser("git", help="AI-assisted git operations")
    git_sub = git_parser.add_subparsers(dest="git_command")

    def _git_help(_args):
        print()
        print(style.banner("  nono-dev git"))
        print()
        print(style.help_row("git commit", "", "AI-generated conventional commit"))
        print()
        sys.exit(0)

    git_parser.set_defaults(func=_git_help)

    commit_parser = git_sub.add_parser(
        "commit", help="Generate a commit message with AI and commit",
    )
    commit_parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Stage all changes (including untracked) before committing. "
             "Without this flag, if anything is staged only the staged changes "
             "are committed; if nothing is staged, all changes are staged.",
    )
    commit_parser.set_defaults(func=run_commit)


def _get_staged_diff():
    """Get the diff of staged changes."""
    result = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _get_unstaged_diff():
    """Get the diff of unstaged (tracked) changes."""
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _get_unstaged_files():
    """Get list of tracked files with unstaged modifications."""
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True, text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _get_untracked():
    """Get list of untracked files (newline-separated string)."""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def _untracked_list(untracked):
    """Split the untracked-files blob into a list of paths."""
    return [line for line in untracked.splitlines() if line.strip()]


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
        print(style.error(f"Commit failed: {result.stderr.strip()}"), file=sys.stderr)
        sys.exit(1)
    print(style.success(result.stdout.strip()))


def run_commit(args):
    staged_diff = _get_staged_diff()
    unstaged_diff = _get_unstaged_diff()
    untracked = _get_untracked()

    use_all = getattr(args, "all", False)

    if use_all:
        # Legacy behavior: stage everything (including untracked) and commit.
        diff_parts = [d for d in (staged_diff, unstaged_diff) if d]
        diff = "\n".join(diff_parts)
        prompt_untracked = untracked
        stage_before_commit = True
    elif staged_diff:
        # Respect existing staging: commit only what's already staged.
        diff = staged_diff
        prompt_untracked = ""  # untracked aren't going in
        stage_before_commit = False

        # Tell the user what's being left out so they don't get surprised.
        unstaged_files = _get_unstaged_files()
        untracked_files = _untracked_list(untracked)
        skipped_parts = []
        if unstaged_files:
            skipped_parts.append(f"{len(unstaged_files)} unstaged")
        if untracked_files:
            skipped_parts.append(f"{len(untracked_files)} untracked")
        if skipped_parts:
            skipped = " and ".join(skipped_parts)
            print(style.muted(
                f"({skipped} files left out — run with -a to include)"
            ))
    else:
        # Nothing staged and no -a: fall back to today's behavior so users
        # who never stage manually keep their muscle memory.
        diff = unstaged_diff
        prompt_untracked = untracked
        stage_before_commit = True

    if not diff and not prompt_untracked:
        print(style.muted("No changes to commit."))
        return

    prompt_parts = []
    if diff:
        prompt_parts.append(f"Diff:\n{diff}")
    if prompt_untracked:
        prompt_parts.append(f"New untracked files:\n{prompt_untracked}")

    prompt = "Generate a commit message for these changes:\n\n" + "\n\n".join(prompt_parts)

    print(style.info("Generating commit message..."))
    message = gemini.generate(prompt, system_prompt=COMMIT_SYSTEM_PROMPT).strip()

    # Strip any markdown code fences the model might add
    if message.startswith("```"):
        lines = message.splitlines()
        lines = [l for l in lines if not l.startswith("```")]
        message = "\n".join(lines).strip()

    # Display the commit message with styling
    print()
    msg_lines = message.split("\n")
    if msg_lines:
        print(style.commit_title(msg_lines[0]))
        for line in msg_lines[1:]:
            if line.strip().startswith("- "):
                print(style.commit_body(line))
            elif line.strip():
                print(style.muted(line))
            else:
                print()
    print()

    answer = input(style.prompt_text("Commit with this message? ") + style.muted("[Y/n/e(dit)] ")).strip().lower()
    if answer == "n":
        print(style.warning("Aborted."))
        return
    if answer == "e":
        message = _edit_message(message)
        if not message:
            print(style.warning("Aborted."))
            return

    if stage_before_commit:
        _stage_all()
    _commit(message)

    # Offer to push
    branch = _current_branch()
    remote = _get_remote()
    if branch and remote:
        push_answer = input(
            style.prompt_text("Push commit? ")
            + style.muted("[Y/n] ")
            + style.value(f"[{remote}/{branch}] ")
        ).strip().lower()
        if push_answer != "n":
            _push(remote, branch)


def _current_branch():
    """Get the current git branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _get_remote():
    """Get the remote for the current branch, defaulting to origin."""
    result = subprocess.run(
        ["git", "config", "--get", "branch." + (_current_branch() or "") + ".remote"],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "origin"


def _push(remote, branch):
    """Push to remote, setting upstream if needed."""
    print(style.info(f"Pushing to {remote}/{branch}..."))
    result = subprocess.run(
        ["git", "push", "-u", remote, branch],
    )
    if result.returncode != 0:
        print(style.error("Push failed."), file=sys.stderr)
        sys.exit(1)
    print(style.success("Pushed."))


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
