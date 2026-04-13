"""Install shell integration for nono-dev."""

import os
import sys


SHELL_FUNC = r'''
# nono-dev shell integration
nwt() {
    if [ -z "$1" ]; then
        nono-dev wt list
        return
    fi
    local dir
    dir="$(nono-dev wt cd "$1" 2>/dev/null)"
    if [ $? -eq 0 ] && [ -n "$dir" ]; then
        cd "$dir"
    else
        nono-dev wt cd "$1"
    fi
}

nwts() {
    if [ -z "$1" ]; then
        echo "Usage: nwts <name>" >&2
        return 1
    fi
    local dir
    dir="$(nono-dev wt start "$@" 2>/dev/tty)"
    if [ $? -eq 0 ] && [ -n "$dir" ]; then
        cd "$dir"
    else
        nono-dev wt start "$@"
    fi
}

# nono-dev zsh completions
if [ -n "$ZSH_VERSION" ]; then
    _nono_dev_complete() {
        local -a completions
        completions=(${(f)"$(nono-dev --complete "${(@)words[2,$CURRENT]}" 2>/dev/null)"})
        _describe 'nono-dev' completions
    }
    compdef _nono_dev_complete nono-dev
    compdef _nono_dev_complete nd

    _wt_complete() {
        local -a completions
        completions=(${(f)"$(nono-dev --complete wt cd "${words[2]:-}" 2>/dev/null)"})
        _describe 'worktree' completions
    }
    compdef _wt_complete nwt
    compdef _wt_complete nwts
fi
'''

SHELL_INIT_LINE = 'eval "$(nono-dev shell-init)"'


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "shell-init",
        help="Shell integration (run: eval \"$(nono-dev shell-init)\")",
    )
    parser.add_argument(
        "--install", action="store_true",
        help="Add shell integration to your shell config automatically",
    )
    parser.set_defaults(func=run)


def _detect_shell_rc():
    """Detect the user's shell rc file."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return os.path.expanduser("~/.zshrc")
    if "bash" in shell:
        bashrc = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc):
            return bashrc
        return os.path.expanduser("~/.bash_profile")
    return None


def run(args):
    if args.install:
        rc_file = _detect_shell_rc()
        if not rc_file:
            print("Could not detect shell config file.", file=sys.stderr)
            print(f"Add this to your shell config manually:\n\n  {SHELL_INIT_LINE}")
            sys.exit(1)

        # Check if already installed
        if os.path.exists(rc_file):
            with open(rc_file) as f:
                if "nono-dev shell-init" in f.read():
                    print(f"Shell integration already installed in {rc_file}")
                    return

        with open(rc_file, "a") as f:
            f.write(f"\n{SHELL_INIT_LINE}\n")

        print(f"Shell integration installed in {rc_file}")
        print("Restart your shell or run: source " + rc_file)
        return

    # Default: print the shell function (for eval)
    print(SHELL_FUNC.strip())
