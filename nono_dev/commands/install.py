"""Install nono-dev as a globally available command via uv tool."""

import os
import shutil
import subprocess
import sys

from nono_dev import style


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "install",
        help="Install nono-dev globally via uv tool",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reinstall even if already installed",
    )
    parser.set_defaults(func=run)


def run(args):
    print()
    print(style.header("  Install nono-dev"))

    # Check for uv
    uv = shutil.which("uv")
    if not uv:
        print(f"  {style.error('error')}  uv not found on PATH")
        print()
        print(style.dim("  Install uv first:"))
        print(style.dim("    curl -LsSf https://astral.sh/uv/install.sh | sh"))
        print()
        sys.exit(1)

    # Find project root (directory containing pyproject.toml)
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    pyproject = os.path.join(project_dir, "pyproject.toml")
    if not os.path.isfile(pyproject):
        print(f"  {style.error('error')}  Cannot find pyproject.toml at {project_dir}")
        sys.exit(1)

    # Build uv tool install command
    cmd = [uv, "tool", "install", "--editable", project_dir]
    if args.force:
        cmd.append("--force")

    print(f"  {style.info('run')}    uv tool install --editable {project_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "already installed" in stderr.lower():
            print(f"  {style.muted('skip')}  nono-dev already installed (use --force to reinstall)")
        else:
            print(f"  {style.error('error')}  uv tool install failed:")
            for line in stderr.splitlines()[:5]:
                print(f"         {line}")
            sys.exit(1)
    else:
        print(f"  {style.info('ok')}    nono-dev installed to ~/.local/bin/nono-dev")

    # Install nono-dev sandbox profile
    profile_src = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "profiles", "nono-dev.json",
    )
    profile_dst_dir = os.path.expanduser("~/.config/nono/profiles")
    profile_dst = os.path.join(profile_dst_dir, "nono-dev.json")

    if os.path.isfile(profile_src):
        os.makedirs(profile_dst_dir, exist_ok=True)
        shutil.copy2(profile_src, profile_dst)
        print(f"  {style.info('ok')}    nono-dev profile installed to {profile_dst}")
    else:
        print(f"  {style.warning('warn')}  nono-dev profile not found in package")

    # Verify it's on PATH
    if shutil.which("nono-dev"):
        print(f"  {style.info('ok')}    nono-dev is on PATH")
    else:
        print()
        print(f"  {style.warning('warn')}  ~/.local/bin is not on your PATH")
        print(style.dim("  Add it to your shell config:"))
        print(style.dim('    export PATH="$HOME/.local/bin:$PATH"'))
        print()
        print(style.dim("  Or run: nono-dev dotfiles"))

    print()
