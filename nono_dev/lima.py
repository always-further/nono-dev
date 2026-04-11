"""Thin wrapper around Lima (limactl) and mutagen CLI commands."""

import json
import os
import shutil
import subprocess
import sys


def check_installed():
    """Verify that limactl is available."""
    if not shutil.which("limactl"):
        print(
            "Error: 'limactl' command not found. Install Lima first:\n"
            "  brew install lima",
            file=sys.stderr,
        )
        sys.exit(1)


def check_mutagen_installed():
    """Verify that mutagen is available."""
    if not shutil.which("mutagen"):
        print(
            "Error: 'mutagen' command not found. Install mutagen first:\n"
            "  brew install mutagen-io/mutagen/mutagen",
            file=sys.stderr,
        )
        sys.exit(1)


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
