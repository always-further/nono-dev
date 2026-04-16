"""Show or switch the project directory synced into a VM."""

import argparse
import os
import sys

from nono_dev import lima, project_config
from nono_dev.config import DEFAULT_VM_NAME


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "mount", help="Show or switch the synced project directory",
    )
    parser.add_argument(
        "arg1", nargs="?", default=None, metavar="[vm] [path]",
        help="VM name, path, or omit to show current mount",
    )
    parser.add_argument(
        "arg2", nargs="?", default=None, metavar="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-m", "--name", dest="name_flag", default=None,
        help="VM name (alias for positional vm)",
    )
    parser.add_argument(
        "--user", default=None,
        help="Username in the VM (default: current macOS user)",
    )
    parser.set_defaults(func=run)


def _looks_like_path(s):
    """Heuristic: does this positional look like a filesystem path?"""
    if s is None:
        return False
    if s.startswith(("/", "./", "../", "~")):
        return True
    return os.sep in s or os.path.isdir(s)


def run(args):
    lima.check_installed()
    lima.check_mutagen_installed()

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    # Disambiguate positionals:
    #   mount                -> show default VM mount
    #   mount <vm>           -> show that VM's mount
    #   mount <path>         -> switch default VM to path
    #   mount <vm> <path>    -> switch named VM to path
    # Path detection by shape (slash, ~, or existing directory).
    vm_arg = args.name_flag
    path_arg = None
    if args.arg2 is not None:
        vm_arg = vm_arg or args.arg1
        path_arg = args.arg2
    elif args.arg1 is not None:
        if _looks_like_path(args.arg1):
            path_arg = args.arg1
        else:
            vm_arg = vm_arg or args.arg1

    vm_name = lima.resolve_vm_name(vm_arg, DEFAULT_VM_NAME, lima_home=lima_home)
    args.path = path_arg  # keep downstream code happy

    # Show current mount
    if args.path is None:
        info = lima.sync_info(vm_name, lima_home=lima_home)
        if info:
            host_path, guest_url = info
            print(f"  VM:     {vm_name}")
            print(f"  Host:   {host_path}")
            print(f"  Guest:  {guest_url}")
        else:
            print(f"No active sync session for '{vm_name}'.")
        return

    # Switch to new path
    new_path = os.path.abspath(args.path)
    if not os.path.isdir(new_path):
        print(f"Error: '{new_path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    username = args.user or os.environ.get("USER", "dev")
    guest_project = f"/home/{username}.guest/project"

    info = lima.sync_info(vm_name, lima_home=lima_home)
    if info and info[0] == new_path:
        print(f"Already syncing '{new_path}' on '{vm_name}'.")
        return

    if info:
        print(f"Stopping sync of {info[0]}...")
    lima.stop_sync(vm_name, lima_home=lima_home)

    print(f"Starting sync of {new_path} -> ~/project on '{vm_name}'...")
    lima.start_sync(vm_name, new_path, guest_project, lima_home=lima_home)
    print("Done.")
