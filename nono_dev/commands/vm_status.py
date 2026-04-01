"""Show OrbStack VM status."""

from nono_dev import orbstack


def add_parser(subparsers):
    parser = subparsers.add_parser("vm-status", help="Show OrbStack VM status")
    parser.set_defaults(func=run)


def run(args):
    orbstack.check_installed()
    orbstack.list_vms()
