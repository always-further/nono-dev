"""Show or switch the project directory synced into a VM."""

import os
import sys

from nono_dev import lima, project_config
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "mount", help="Show or switch the synced project directory",
    )
    parser.add_argument(
        "path", nargs="?", default=None,
        help="Host directory to sync (omit to show current)",
    )
    parser.add_argument(
        "--name", default=DEFAULT_VM_NAME,
        help=f"VM name (default: {DEFAULT_VM_NAME})",
    )
    parser.add_argument(
        "--user", default=None,
        help="Username in the VM (default: current macOS user)",
    )
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()
    lima.check_mutagen_installed()

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    vm_name = args.name

    if not lima.vm_exists(vm_name, lima_home=lima_home):
        print(f"VM '{vm_name}' does not exist.")
        sys.exit(1)

    # Show current mount
    if args.path is None:
        info = lima.sync_info(vm_name)
        if info:
            host_path, guest_url = info
            print(f"  Host:   {host_path}")
            print(f"  Guest:  {guest_url}")
        else:
            print("No active sync session.")
        return

    # Switch to new path
    new_path = os.path.abspath(args.path)
    if not os.path.isdir(new_path):
        print(f"Error: '{new_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    username = args.user or os.environ.get("USER", "dev")
    guest_project = f"/home/{username}.guest/project"

    info = lima.sync_info(vm_name)
    if info and info[0] == new_path:
        print(f"Already syncing '{new_path}'.")
        return

    if info:
        print(f"Stopping sync of {info[0]}...")
    lima.stop_sync(vm_name)

    print(f"Starting sync of {new_path} → ~/project...")
    lima.start_sync(vm_name, new_path, guest_project, lima_home=lima_home)
    print("Done.")
