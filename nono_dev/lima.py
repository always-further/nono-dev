"""Thin wrapper around Lima (limactl) and mutagen CLI commands."""

import json
import os
import select
import shutil
import subprocess
import sys
import time


def _lima_env(lima_home=None):
    """Return an env dict with LIMA_HOME set, or None for default."""
    if lima_home is None:
        return None
    env = os.environ.copy()
    env["LIMA_HOME"] = lima_home
    return env


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


def vm_exists(name, lima_home=None):
    """Check whether a VM with the given name exists."""
    result = subprocess.run(
        ["limactl", "list", "--json"],
        capture_output=True, text=True,
        env=_lima_env(lima_home),
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


def vm_status(name, lima_home=None):
    """Return the status of a VM (e.g. 'Running', 'Stopped'), or None."""
    result = subprocess.run(
        ["limactl", "list", "--json"],
        capture_output=True, text=True,
        env=_lima_env(lima_home),
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


def create_vm(name, lima_config_path, lima_home=None):
    """Create a Lima VM from a YAML config file."""
    result = subprocess.run(
        ["limactl", "create", "--tty=false", "--name", name, lima_config_path],
        env=_lima_env(lima_home),
    )
    if result.returncode != 0:
        sys.exit(1)


def start_vm(name, lima_home=None):
    """Start a Lima VM."""
    status = vm_status(name, lima_home=lima_home)
    if status == "Running":
        print(f"VM '{name}' is already running.")
        return

    process = subprocess.Popen(
        ["limactl", "start", name],
        env=_lima_env(lima_home),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    ready_prefix = "READY. Run `limactl shell "
    last_output = time.monotonic()
    last_heartbeat = 0.0
    while True:
        ready, _, _ = select.select([process.stdout], [], [], 1.0)
        if ready:
            line = process.stdout.readline()
            if not line:
                break
            last_output = time.monotonic()
            line = line.replace('\\"', '"')
            if ready_prefix in line:
                print("READY. Run `nono-dev vm connect` to open the shell.")
            else:
                print(line, end="")
            continue

        now = time.monotonic()
        if now - last_output >= 15 and now - last_heartbeat >= 15:
            print("VM still starting; waiting for guest boot/provisioning to finish...")
            last_heartbeat = now

        if process.poll() is not None:
            break
    if process.wait() != 0:
        sys.exit(1)


def run_in_vm(name, command, lima_home=None):
    """Run a command inside a VM as root."""
    result = subprocess.run(
        ["limactl", "shell", name, "sudo", "bash", "-c", command],
        capture_output=True, text=True,
        env=_lima_env(lima_home),
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    return result


def run_in_vm_as_user(name, username, command, lima_home=None):
    """Run a command inside a VM as a specific user."""
    result = subprocess.run(
        ["limactl", "shell", name, "sudo", "-u", username, "bash", "-c", command],
        capture_output=True, text=True,
        env=_lima_env(lima_home),
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip()
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)
    return result


def stop_vm(name, lima_home=None):
    """Stop a running Lima VM."""
    subprocess.run(
        ["limactl", "stop", name],
        capture_output=True, text=True,
        env=_lima_env(lima_home),
    )


def force_stop_vm(name, lima_home=None):
    """Force-stop a Lima VM (used to clear a Broken state)."""
    subprocess.run(
        ["limactl", "stop", "--force", name],
        capture_output=True, text=True,
        env=_lima_env(lima_home),
    )


def delete_vm(name, lima_home=None):
    """Delete a Lima VM."""
    subprocess.run(
        ["limactl", "delete", "--force", name],
        check=True,
        env=_lima_env(lima_home),
    )


def list_vms(lima_home=None):
    """List all Lima VMs and print the output."""
    subprocess.run(["limactl", "list"], check=True, env=_lima_env(lima_home))


def list_vms_json(lima_home=None):
    """List all Lima VMs and return parsed JSON."""
    result = subprocess.run(
        ["limactl", "list", "--json"],
        capture_output=True, text=True, check=True,
        env=_lima_env(lima_home),
    )
    vms = []
    for line in result.stdout.strip().splitlines():
        vms.append(json.loads(line))
    return vms


def ssh_config_path(vm_name, lima_home=None):
    """Absolute path to Lima's per-VM SSH config file."""
    base = lima_home or os.path.expanduser("~/.lima")
    return os.path.join(base, vm_name, "ssh.config")


def ssh_host(vm_name):
    """The SSH host alias Lima defines inside its per-VM ssh.config."""
    return f"lima-{vm_name}"


def ssh_argv(vm_name, remote_command=None, lima_home=None):
    """Build an ssh argv for a VM using Lima's per-VM config directly.

    Uses `-F <lima ssh.config>` so we don't depend on the user's
    `~/.ssh/config` having been patched with an `Include` line. This
    works even on hosts that have never started a mutagen sync.
    """
    argv = ["ssh", "-F", ssh_config_path(vm_name, lima_home=lima_home), ssh_host(vm_name)]
    if remote_command is not None:
        argv.append(remote_command)
    return argv


def resolve_vm_name(name, default, lima_home=None):
    """Resolve the target VM name.

    - If `name` is given explicitly and that VM exists, use it.
    - If `name` is given explicitly and that VM does NOT exist, error
      (never silently fall back — destructive commands must fail closed).
    - If `name` is not given (None/empty), auto-select: prefer `default`
      if it exists, else the sole VM if exactly one exists, else error.
    """
    try:
        vms = list_vms_json(lima_home=lima_home)
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


def _ensure_ssh_include(vm_name, lima_home=None):
    """Ensure ~/.ssh/config includes Lima's SSH config for the VM.

    This lets SSH-based tools (mutagen, rsync, etc.) resolve the
    lima-<name> hostname without extra flags.
    """
    base = lima_home or os.path.expanduser("~/.lima")
    lima_ssh_config = os.path.join(base, vm_name, "ssh.config")
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


def start_sync(vm_name, host_path, guest_path, lima_home=None):
    """Start a mutagen sync session from host to VM via SSH."""
    check_mutagen_installed()
    session_name = _sync_session_name(vm_name)

    # Ensure SSH can resolve lima-<name>
    _ensure_ssh_include(vm_name, lima_home=lima_home)

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
            "--ignore", ".worktrees/",
            "--ignore", "node_modules/",
            "--ignore", "target/",
            "--ignore", ".venv/",
            "--ignore", "__pycache__/",
            "--ignore", ".next/",
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


def stop_sync(vm_name, lima_home=None):
    """Terminate the mutagen sync session for a VM."""
    if not shutil.which("mutagen"):
        return

    session_name = _sync_session_name(vm_name)
    subprocess.run(
        ["mutagen", "sync", "terminate", session_name],
        capture_output=True, text=True,
    )


def sync_status(vm_name, lima_home=None):
    """Print the mutagen sync status for a VM."""
    session_name = _sync_session_name(vm_name)
    subprocess.run(
        ["mutagen", "sync", "list", session_name],
    )


def sync_info(vm_name, lima_home=None):
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
