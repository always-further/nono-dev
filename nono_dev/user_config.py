"""User-level configuration from ~/.config/nono-dev/config.toml."""

import os
import tomllib

USER_CONFIG_PATH = os.path.expanduser("~/.config/nono-dev/config.toml")


def load():
    """Load user-level config, returning a raw dict.

    Returns an empty dict if the file does not exist.
    Merge logic lives in project_config.load().
    """
    if not os.path.isfile(USER_CONFIG_PATH):
        return {}

    with open(USER_CONFIG_PATH, "rb") as f:
        return tomllib.load(f)
