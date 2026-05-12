"""Thin wrapper around the nono sandbox CLI."""

import json
import os
import shutil
import subprocess
import sys

# Known agent CLI conventions. Any key can be overridden via [agent] config.
_AGENT_DEFAULTS = {
    "claude": {
        "profile": "claude-code",
        "auto_approve_flag": "--dangerously-skip-permissions",
        "system_prompt_flag": "--system-prompt",
    },
    "codex": {
        "profile": "claude-code",
        "auto_approve_flag": "--full-auto",
        "system_prompt_flag": None,
    },
}

_AGENT_FALLBACK = {
    "profile": "claude-code",
    "auto_approve_flag": None,
    "system_prompt_flag": None,
}


def get_agent_config(config):
    """Resolve agent settings from project config with known-agent defaults."""
    agent_cfg = config.get("agent", {})
    binary = agent_cfg.get("binary", "claude")
    known = _AGENT_DEFAULTS.get(binary, _AGENT_FALLBACK)
    return {
        "binary": binary,
        "profile": agent_cfg.get("profile") or known["profile"],
        "auto_approve_flag": agent_cfg.get("auto_approve_flag") or known.get("auto_approve_flag"),
        "system_prompt_flag": agent_cfg.get("system_prompt_flag") or known.get("system_prompt_flag"),
    }


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
    agent_config=None,
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
    agent = agent_config or _AGENT_DEFAULTS["claude"]
    profile = agent["profile"]
    binary = agent["binary"]
    auto_approve_flag = agent.get("auto_approve_flag")
    system_prompt_flag = agent.get("system_prompt_flag")

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

    # Grant read access to gh CLI and git configs for GitHub operations
    gh_config = os.path.expanduser("~/.config/gh")
    if os.path.isdir(gh_config):
        cmd.extend(["--read", gh_config])
    for git_cfg in ["~/.gitconfig", "~/.gitconfig.local"]:
        path = os.path.expanduser(git_cfg)
        if os.path.exists(path):
            cmd.extend(["--read-file", path])
    ssh_dir = os.path.expanduser("~/.ssh")
    if os.path.isdir(ssh_dir):
        cmd.extend(["--read", ssh_dir])

    if allow_cwd:
        cmd.append("--allow-cwd")

    if workdir:
        cmd.extend(["--workdir", workdir])

    cmd.append("--")
    cmd.append(binary)
    if auto_approve_flag:
        cmd.append(auto_approve_flag)

    prompt_content = None
    if system_prompt:
        with open(system_prompt) as f:
            prompt_content = f.read()

    if system_prompt_flag and prompt_content:
        cmd.extend([system_prompt_flag, prompt_content])
        if user_prompt:
            cmd.append(user_prompt)
    elif prompt_content:
        # Agent has no --system-prompt flag; prepend to the user prompt.
        merged_prompt = f"{prompt_content}\n\n{user_prompt}" if user_prompt else prompt_content
        cmd.append(merged_prompt)
    elif user_prompt:
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
