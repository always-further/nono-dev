"""Deploy shipped dotfiles and install shell tools on the local machine."""

import importlib.resources
import os
import platform
import shutil
import subprocess
from nono_dev import style


DOTFILES_MAP = {
    ".zprofile": "~/.zprofile",
    ".zshrc": "~/.zshrc",
    ".tmux.conf": "~/.tmux.conf",
    # starship.toml is handled separately via preset picker
}

# Starship presets to offer (curated subset + our shipped config)
STARSHIP_PRESETS = [
    ("nono-dev", "Custom nono-dev prompt (shipped)"),
    ("catppuccin-powerline", "Catppuccin Mocha powerline"),
    ("tokyo-night", "Tokyo Night color scheme"),
    ("pastel-powerline", "Pastel colored powerline"),
    ("bracketed-segments", "Bracketed info segments"),
    ("gruvbox-rainbow", "Gruvbox rainbow powerline"),
    ("jetpack", "Jetpack inspired prompt"),
    ("pure-preset", "Minimal Pure-style prompt"),
]

# Tools to install via Homebrew on macOS
BREW_PACKAGES = ["starship", "eza", "tmux", "z", "zsh-autosuggestions"]

# Nerd Font cask (required for starship preset icons)
NERD_FONT_CASK = "font-meslo-lg-nerd-font"
NERD_FONT_NAME = "MesloLGS Nerd Font"


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "dotfiles",
        help="Deploy shipped dotfiles and shell tools to the local machine",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing files without prompting",
    )
    parser.add_argument(
        "--no-install", action="store_true",
        help="Only deploy dotfiles, skip tool installation",
    )
    parser.add_argument(
        "--preset", metavar="NAME",
        help="Starship preset to use (skip interactive picker)",
    )
    parser.set_defaults(func=run)


def _has_command(name):
    """Check if a command is available on PATH."""
    return shutil.which(name) is not None


def _is_installed(name):
    """Check if a package is installed (command on PATH or brew package)."""
    if shutil.which(name) is not None:
        return True
    # Some packages (like z) are shell scripts, not binaries
    if _has_command("brew"):
        result = subprocess.run(
            ["brew", "list", name],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    return False


def _install_tools():
    """Install shell tools via Homebrew (macOS only)."""
    if platform.system() != "Darwin":
        print(style.dim("  Skipping tool install (not macOS)"))
        return

    if not _has_command("brew"):
        print()
        print(f"  {style.warning('warn')}  Homebrew not found. Install it first:")
        print(style.dim("         https://brew.sh"))
        print()
        print(style.dim("  Then re-run: nono-dev dotfiles"))
        return

    missing = [pkg for pkg in BREW_PACKAGES if not _is_installed(pkg)]
    if not missing:
        print(f"  {style.muted('skip')}  All tools already installed")
    else:
        print(f"  {style.info('brew')}  Installing: {', '.join(missing)}")
        result = subprocess.run(
            ["brew", "install"] + missing,
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  {style.warning('warn')}  brew install failed:")
            for line in result.stderr.strip().splitlines()[:5]:
                print(f"         {line}")
        else:
            for pkg in missing:
                if _is_installed(pkg):
                    print(f"  {style.info('ok')}    {pkg}")
                else:
                    print(f"  {style.warning('warn')}  {pkg} not found after install")

    # Install Nerd Font for starship icons
    font_check = subprocess.run(
        ["brew", "list", "--cask", NERD_FONT_CASK],
        capture_output=True, text=True,
    )
    if font_check.returncode == 0:
        print(f"  {style.muted('skip')}  {NERD_FONT_CASK} (already installed)")
    else:
        print(f"  {style.info('brew')}  Installing: {NERD_FONT_CASK}")
        result = subprocess.run(
            ["brew", "install", "--cask", NERD_FONT_CASK],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  {style.warning('warn')}  Font install failed:")
            for line in result.stderr.strip().splitlines()[:5]:
                print(f"         {line}")
        else:
            print(f"  {style.info('ok')}    {NERD_FONT_CASK}")
            print()
            print(f"  {style.warning('note')}  Set your terminal font to {style.value(NERD_FONT_NAME)}")
            print(style.dim("         Terminal.app: Preferences > Profiles > Font > Change"))
            print(style.dim("         iTerm2: Preferences > Profiles > Text > Font"))


def _deploy_dotfiles(args):
    """Deploy shipped dotfiles to home directory."""
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


def _pick_starship_preset(args):
    """Let the user choose a starship preset, then apply it."""
    if not _has_command("starship"):
        print(f"  {style.muted('skip')}  starship not installed, skipping preset")
        return

    dest_path = os.path.expanduser("~/.config/starship.toml")
    dest_dir = os.path.dirname(dest_path)
    if dest_dir and not os.path.isdir(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    # If --preset given, skip interactive picker
    preset_name = args.preset
    if preset_name:
        valid_names = [p[0] for p in STARSHIP_PRESETS]
        if preset_name not in valid_names:
            print(f"  {style.error('error')}  Unknown preset: {preset_name}")
            print(f"  {style.dim('  Available:')} {', '.join(valid_names)}")
            return
    else:
        # Interactive picker
        print()
        print(style.header("  Starship Preset"))
        print()
        for i, (name, desc) in enumerate(STARSHIP_PRESETS, 1):
            num = style.info(f"  {i})")
            print(f"  {num} {style.value(name)}")
            print(f"       {style.dim(desc)}")
        print()

        try:
            choice = input(f"  {style.prompt_text('Pick a preset')} [1-{len(STARSHIP_PRESETS)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print(f"  {style.muted('skip')}  starship preset (no selection)")
            return

        if not choice:
            print(f"  {style.muted('skip')}  starship preset (no selection)")
            return

        try:
            idx = int(choice) - 1
            if not 0 <= idx < len(STARSHIP_PRESETS):
                raise ValueError
        except ValueError:
            print(f"  {style.error('error')}  Invalid choice: {choice}")
            return

        preset_name = STARSHIP_PRESETS[idx][0]

    # Apply the preset
    if preset_name == "nono-dev":
        # Use our shipped config
        ref = importlib.resources.files("nono_dev.dotfiles").joinpath("starship.toml")
        content = ref.read_text(encoding="utf-8")

        if os.path.exists(dest_path) and not args.force:
            backup = dest_path + ".bak"
            shutil.copy2(dest_path, backup)
            print(f"  {style.value('backup')}  ~/.config/starship.toml -> ~/.config/starship.toml.bak")

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  {style.info('write')}  ~/.config/starship.toml ({style.value('nono-dev')})")
    else:
        # Use starship preset command
        if os.path.exists(dest_path) and not args.force:
            backup = dest_path + ".bak"
            shutil.copy2(dest_path, backup)
            print(f"  {style.value('backup')}  ~/.config/starship.toml -> ~/.config/starship.toml.bak")

        result = subprocess.run(
            ["starship", "preset", preset_name, "-o", dest_path],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  {style.error('error')}  Failed to apply preset: {preset_name}")
            if result.stderr.strip():
                for line in result.stderr.strip().splitlines()[:3]:
                    print(f"         {line}")
            return
        print(f"  {style.info('write')}  ~/.config/starship.toml ({style.value(preset_name)})")


def run(args):
    if not args.no_install:
        print()
        print(style.header("  Shell Tools"))
        _install_tools()

    print()
    print(style.header("  Dotfiles"))
    _deploy_dotfiles(args)

    _pick_starship_preset(args)

    print()
    print(style.dim("  Done. Restart your shell or run: source ~/.zshrc"))
