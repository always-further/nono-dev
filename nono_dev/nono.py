"""Thin wrapper around the nono sandbox CLI."""

import json
import os
import shutil
import subprocess
import sys


def check_installed():
    """Verify that the nono CLI is available."""
    if not shutil.which("nono"):
        print(
            "Error: 'nono' command not found. Install nono first: "
            "https://docs.nono.sh/cli/getting_started/installation",
            file=sys.stderr,
        )
        sys.exit(1)


def run_detached(
    name,
    *,
    profile="nono-dev",
    allows=None,
    reads=None,
    allow_cwd=False,
    system_prompt=None,
    user_prompt=None,
    rollback=None,
    workdir=None,
):
    """Run a command inside nono in detached mode.

    Returns the session ID parsed from nono's output.
    """
    if profile == "nono-dev":
        profile_path = os.path.expanduser("~/.config/nono/profiles/nono-dev.json")
        if not os.path.isfile(profile_path):
            print(
                "nono-dev profile not installed. Run: nd install --force",
                file=sys.stderr,
            )
            sys.exit(1)

    cmd = ["nono", "run", "--detached", "--name", name, "--profile", profile]

    # Skip large directory trees during trust scan and rollback preflight
    for skip in ["node_modules", "target", ".venv", "__pycache__", ".next"]:
        cmd.extend(["--skip-dir", skip])

    if rollback is None or rollback.get("enabled", True):
        cmd.append("--rollback")
        excludes = rollback.get("exclude", []) if rollback else []
        for pattern in excludes:
            cmd.extend(["--rollback-exclude", pattern])

    for path in allows or []:
        cmd.extend(["--allow", path])

    for path in reads or []:
        cmd.extend(["--read", path])

    if allow_cwd:
        cmd.append("--allow-cwd")

    if workdir:
        cmd.extend(["--workdir", workdir])

    cmd.append("--")
    cmd.extend(["claude", "--dangerously-skip-permissions"])

    if system_prompt:
        with open(system_prompt) as f:
            prompt_content = f.read()
        cmd.extend(["--system-prompt", prompt_content])

    if user_prompt:
        cmd.append(user_prompt)

    result = subprocess.run(cmd, capture_output=True, text=True)

    # nono may write session info to either stdout or stderr
    combined = (result.stdout + "\n" + result.stderr).strip()

    if result.returncode != 0:
        print(f"Error starting nono session: {combined}", file=sys.stderr)
        sys.exit(1)

    session_id = _parse_session_id(combined)
    if not session_id:
        print(f"Warning: could not parse session ID from nono output:", file=sys.stderr)
        print(f"  stdout: {result.stdout.strip()}", file=sys.stderr)
        print(f"  stderr: {result.stderr.strip()}", file=sys.stderr)

    return session_id


def _parse_session_id(output):
    """Extract session ID from nono run --detached output.

    Expected format:
        Started detached session 764dce.
        Name: test-parse
        Attach with: nono attach 764dce
    """
    import re
    for line in output.strip().splitlines():
        # "Started detached session <id>."
        m = re.match(r"Started detached session (\S+?)\.?$", line.strip())
        if m:
            return m.group(1)
        # "Attach with: nono attach <id>"
        m = re.match(r"Attach with: nono attach (\S+)", line.strip())
        if m:
            return m.group(1)
    return output.strip()


def ps_json(include_all=True):
    """List nono sessions as parsed JSON."""
    cmd = ["nono", "ps", "--json"]
    if include_all:
        cmd.append("--all")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []

    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return []


def attach(session_id):
    """Attach to a running nono session. Replaces the current process."""
    os.execvp("nono", ["nono", "attach", session_id])
