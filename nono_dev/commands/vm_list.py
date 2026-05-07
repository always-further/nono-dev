"""List Lima VMs."""

from nono_dev import lima, project_config


def add_parser(subparsers):
    parser = subparsers.add_parser("list", help="List VMs")
    parser.set_defaults(func=run)


def run(args):
    lima.check_installed()

    config = project_config.load()
    lima_home = project_config.get_lima_home(config)

    lima.list_vms(lima_home=lima_home)
