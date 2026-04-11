"""Show Lima VM status."""

from nono_dev import lima


def add_parser(subparsers):
    parser = subparsers.add_parser("status", help="Show Lima VM status")
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()
    lima.list_vms()
