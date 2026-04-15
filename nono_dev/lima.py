"""Thin wrapper around Lima (limactl) and mutagen CLI commands."""

import json
import os
import shutil
import subprocess
import sys


def _brew_install(formula, check_cmd=None):
    """Install a Homebrew formula if the command is not already available."""
    cmd = check_cmd or formula.split("/")[-1]
    if shutil.which(cmd):
        return
    if not shutil.which("brew"):
        print(
            f"Error: '{cmd}' not found and Homebrew is not installed.\n"
            f"  Install Homebrew first: https://brew.sh",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Installing {formula} via Homebrew...")
    result = subprocess.run(["brew", "install", formula])
    if result.returncode != 0:
        print(f"Error: failed to install {formula}.", file=sys.stderr)
        sys.exit(1)


def check_installed():
    """Ensure limactl is available, installing via Homebrew if needed."""
    _brew_install("lima", check_cmd="limactl")


def check_mutagen_installed():
    """Ensure mutagen is available, installing via Homebrew if needed."""
    _brew_install("mutagen-io/mutagen/mutagen", check_cmd="mutagen")


def vm_exists(name):
    """Check whether a VM with the given name exists."""
    result = subprocess.run(
        ["limactl", "list", "--json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False
    try:
        # limactl list --json outputs one JSON object per line
        for line in result.stdout.strip().splitlines():
            vm = json.loads(line)
            if vm.get("name") == name:
                return True
        return False
    except (json.JSONDecodeError, TypeError):
        return False


def vm_status(name):
    """Return the status of a VM (e.g. 'Running', 'Stopped'), or None."""
    result = subprocess.run(
        ["limactl", "list", "--json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    try:
        for line in result.stdout.strip().splitlines():
            vm = json.loads(line)
            if vm.get("name") == name:
                return vm.get("status")
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def create_vm(name, lima_config_path):
    """Create a Lima VM from a YAML config file."""
    result = subprocess.run(
        ["limactl", "create", "--tty=false", "--name", name, lima_config_path],
    )
    if result.returncode != 0:
        sys.exit(1)


def start_vm(name):
    """Start a Lima VM."""
    result = subprocess.run(
        ["limactl", "start", name],
    )
    if result.returncode != 0:
        sys.exit(1)


def run_in_vm(name, command):
    """Run a command inside a VM as root."""
    result = subprocess.run(
        ["limactl", "shell", name, "sudo", "bash", "-c", command],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    return result


def run_in_vm_as_user(name, username, command):
    """Run a command inside a VM as a specific user."""
    result = subprocess.run(
        ["limactl", "shell", name, "sudo", "-u", username, "bash", "-c", command],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    return result


def stop_vm(name):
    """Stop a running Lima VM."""
    subprocess.run(["limactl", "stop", name], capture_output=True, text=True)


def delete_vm(name):
    """Delete a Lima VM."""
    subprocess.run(["limactl", "delete", "--force", name], check=True)


def list_vms():
    """List all Lima VMs and print the output."""
    subprocess.run(["limactl", "list"], check=True)


def list_vms_json():
    """List all Lima VMs and return parsed JSON."""
    result = subprocess.run(
        ["limactl", "list", "--json"],
        capture_output=True, text=True, check=True,
    )
    vms = []
    for line in result.stdout.strip().splitlines():
        vms.append(json.loads(line))
    return vms


def ssh_config_path(vm_name):
    """Absolute path to Lima's per-VM SSH config file."""
    return os.path.expanduser(f"~/.lima/{vm_name}/ssh.config")


def ssh_host(vm_name):
    """The SSH host alias Lima defines inside its per-VM ssh.config."""
    return f"lima-{vm_name}"


def ssh_argv(vm_name, remote_command=None):
    """Build an ssh argv for a VM using Lima's per-VM config directly.

    Uses `-F <lima ssh.config>` so we don't depend on the user's
    `~/.ssh/config` having been patched with an `Include` line. This
    works even on hosts that have never started a mutagen sync.
    """
    argv = ["ssh", "-F", ssh_config_path(vm_name), ssh_host(vm_name)]
    if remote_command is not None:
        argv.append(remote_command)
    return argv


def resolve_vm_name(name, default):
    """Resolve the target VM name.

    - If `name` is given explicitly and that VM exists, use it.
    - If `name` is given explicitly and that VM does NOT exist, error
      (never silently fall back — destructive commands must fail closed).
    - If `name` is not given (None/empty), auto-select: prefer `default`
      if it exists, else the sole VM if exactly one exists, else error.
    """
    try:
        vms = list_vms_json()
    except (subprocess.CalledProcessError, FileNotFoundError):
        vms = []
    vm_names = [v["name"] for v in vms if v.get("name")]

    # Explicit name — must exist. No fallback.
    if name:
        if name in vm_names:
            return name
        available = ", ".join(vm_names) if vm_names else "(none)"
        print(
            f"Error: VM '{name}' does not exist. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    # No explicit name — auto-select.
    if default in vm_names:
        return default

    if len(vm_names) == 1:
        return vm_names[0]

    if not vm_names:
        print("Error: no Lima VMs exist. Create one with: nd vm create", file=sys.stderr)
        sys.exit(1)

    print(
        f"Error: multiple VMs exist, specify one with --name/-m.\n"
        f"       Available: {', '.join(vm_names)}",
        file=sys.stderr,
    )
    sys.exit(1)


# -- Mutagen sync helpers --

def _sync_session_name(vm_name):
    """Return the mutagen sync session name for a VM."""
    return f"{vm_name}-sync"


def _ensure_ssh_include(vm_name):
    """Ensure ~/.ssh/config includes Lima's SSH config for the VM.

    This lets SSH-based tools (mutagen, rsync, etc.) resolve the
    lima-<name> hostname without extra flags.
    """
    lima_ssh_config = os.path.expanduser(f"~/.lima/{vm_name}/ssh.config")
    ssh_dir = os.path.expanduser("~/.ssh")
    ssh_config = os.path.join(ssh_dir, "config")

    os.makedirs(ssh_dir, mode=0o700, exist_ok=True)

    include_line = f"Include {lima_ssh_config}"

    if os.path.exists(ssh_config):
        with open(ssh_config) as f:
            content = f.read()
        if include_line in content:
            return
        # Include must be at the top of ssh config
        with open(ssh_config, "w") as f:
            f.write(f"{include_line}\n{content}")
    else:
        with open(ssh_config, "w") as f:
            f.write(f"{include_line}\n")
        os.chmod(ssh_config, 0o600)


def start_sync(vm_name, host_path, guest_path):
    """Start a mutagen sync session from host to VM via SSH."""
    check_mutagen_installed()
    session_name = _sync_session_name(vm_name)

    # Ensure SSH can resolve lima-<name>
    _ensure_ssh_include(vm_name)

    # Terminate any stale session with the same name
    subprocess.run(
        ["mutagen", "sync", "terminate", session_name],
        capture_output=True, text=True,
    )

    ssh_host = f"lima-{vm_name}"
    result = subprocess.run(
        [
            "mutagen", "sync", "create",
            "--name", session_name,
            "--ignore-vcs",
            "--default-file-mode", "0644",
            "--default-directory-mode", "0755",
            host_path,
            f"{ssh_host}:{guest_path}",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"Error starting sync: {msg}", file=sys.stderr)
        sys.exit(1)


def stop_sync(vm_name):
    """Terminate the mutagen sync session for a VM."""
    session_name = _sync_session_name(vm_name)
    subprocess.run(
        ["mutagen", "sync", "terminate", session_name],
        capture_output=True, text=True,
    )


def sync_status(vm_name):
    """Print the mutagen sync status for a VM."""
    session_name = _sync_session_name(vm_name)
    subprocess.run(
        ["mutagen", "sync", "list", session_name],
    )


def sync_info(vm_name):
    """Return (host_path, guest_url) for the current sync session, or None."""
    session_name = _sync_session_name(vm_name)
    result = subprocess.run(
        ["mutagen", "sync", "list", "--long", session_name],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None

    alpha = beta = None
    section = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped == "Alpha:":
            section = "alpha"
        elif stripped == "Beta:":
            section = "beta"
        elif stripped.startswith("URL:") and section in ("alpha", "beta"):
            url = stripped.split(":", 1)[1].strip()
            if section == "alpha":
                alpha = url
            else:
                beta = url
            section = None  # consume URL once per section
    if alpha and beta:
        return (alpha, beta)
    return None
