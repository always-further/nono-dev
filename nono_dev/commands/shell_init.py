"""Output shell functions for nono-dev integration."""


SHELL_INIT = r'''
# nono-dev shell integration
wt() {
    if [ -z "$1" ]; then
        echo "Usage: wt <name>" >&2
        return 1
    fi
    local dir
    dir="$(nono-dev wt cd "$1")"
    if [ $? -eq 0 ] && [ -n "$dir" ]; then
        cd "$dir"
    fi
}
'''


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "shell-init",
        help="Print shell functions (add to .zshrc/.bashrc)",
    )
    parser.set_defaults(func=run)


def run(_args):
    print(SHELL_INIT.strip())
