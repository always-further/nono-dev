"""Show OrbStack VM status."""

from nono_dev import orbstack


def add_parser(subparsers):
    parser = subparsers.add_parser("status", help="Show VM status")
    parser.set_defaults(func=run)


def run(args):
    orbstack.check_installed()
    orbstack.list_vms()
