"""Thin wrapper around OrbStack CLI commands."""

import json
import shutil
import subprocess
import sys


def check_installed():
    """Verify that the orb CLI is available."""
    if not shutil.which("orb"):
        print("Error: 'orb' command not found. Install OrbStack first.", file=sys.stderr)
        sys.exit(1)


def vm_exists(name):
    """Check whether a VM with the given name exists."""
    result = subprocess.run(
        ["orbctl", "list", "-f", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False
    try:
        vms = json.loads(result.stdout)
        return any(vm.get("name") == name for vm in vms)
    except (json.JSONDecodeError, TypeError):
        return False


def create_vm(os_name, name, cloud_init_path):
    """Create an OrbStack VM with the given cloud-init config."""
    result = subprocess.run(
        ["orb", "create", os_name, name, "--user-data", cloud_init_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"Error creating VM: {msg}", file=sys.stderr)
        sys.exit(1)


def run_in_vm(name, command):
    """Run a command inside a VM as root."""
    result = subprocess.run(
        ["orb", "run", "-m", name, "-u", "root", "bash", "-c", command],
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
        ["orb", "run", "-m", name, "-u", username, "bash", "-c", command],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    return result


def delete_vm(name):
    """Delete an OrbStack VM."""
    subprocess.run(["orbctl", "delete", name], check=True)


def list_vms():
    """List all OrbStack VMs and print the output."""
    subprocess.run(["orbctl", "list"], check=True)


def list_vms_json():
    """List all OrbStack VMs and return parsed JSON."""
    result = subprocess.run(
        ["orbctl", "list", "-f", "json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)
