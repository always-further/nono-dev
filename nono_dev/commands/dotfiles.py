"""Deploy shipped dotfiles to the local machine."""

import importlib.resources
import os
import shutil

from nono_dev import style


DOTFILES_MAP = {
    ".zprofile": "~/.zprofile",
    ".zshrc": "~/.zshrc",
    ".tmux.conf": "~/.tmux.conf",
    "starship.toml": "~/.config/starship.toml",
}


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "dotfiles",
        help="Deploy shipped dotfiles to the local machine",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files without prompting",
    )
    parser.set_defaults(func=run)


def run(args):
    for src_name, dest_template in DOTFILES_MAP.items():
        dest_path = os.path.expanduser(dest_template)
        dest_dir = os.path.dirname(dest_path)

        if dest_dir and not os.path.isdir(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        ref = importlib.resources.files("nono_dev.dotfiles").joinpath(src_name)
        content = ref.read_text(encoding="utf-8")

        if os.path.exists(dest_path):
            existing = open(dest_path, encoding="utf-8").read()
            if existing == content:
                print(f"  {style.muted('skip')}  {dest_template} (already up to date)")
                continue

            if not args.force:
                backup = dest_path + ".bak"
                shutil.copy2(dest_path, backup)
                print(f"  {style.value('backup')}  {dest_template} -> {dest_template}.bak")

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  {style.info('write')}  {dest_template}")

    print()
    print(style.dim("  Done. Restart your shell or run: source ~/.zshrc"))
