"""Terminal styling with Catppuccin Mocha palette."""

import sys

# Catppuccin Mocha palette (true color)
_COLORS = {
    "mauve": "\033[38;2;203;166;247m",
    "blue": "\033[38;2;137;180;250m",
    "green": "\033[38;2;166;227;161m",
    "yellow": "\033[38;2;249;226;175m",
    "peach": "\033[38;2;250;179;135m",
    "red": "\033[38;2;243;139;168m",
    "teal": "\033[38;2;148;226;213m",
    "lavender": "\033[38;2;180;190;254m",
    "text": "\033[38;2;205;214;244m",
    "subtext": "\033[38;2;166;173;200m",
    "overlay": "\033[38;2;108;112;134m",
    "surface": "\033[38;2;69;71;90m",
}

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _supports_color():
    """Check if the terminal supports color."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True


def _c(color, text, bold=False):
    """Colorize text if terminal supports it."""
    if not _supports_color():
        return text
    prefix = _BOLD if bold else ""
    return f"{_COLORS.get(color, '')}{prefix}{text}{_RESET}"


def _dim(text):
    if not _supports_color():
        return text
    return f"{_DIM}{text}{_RESET}"


# Semantic helpers
def header(text):
    """Section header."""
    return _c("mauve", text, bold=True)


def success(text):
    """Success message."""
    return _c("green", text, bold=True)


def error(text):
    """Error message."""
    return _c("red", text, bold=True)


def warning(text):
    """Warning message."""
    return _c("yellow", text)


def info(text):
    """Info/status message."""
    return _c("blue", text)


def label(text):
    """Label text (keys, field names)."""
    return _c("lavender", text)


def value(text):
    """Value text (paths, IDs)."""
    return _c("teal", text)


def muted(text):
    """Muted/secondary text."""
    return _c("subtext", text)


def dim(text):
    """Dimmed text."""
    return _dim(text)


def prompt_text(text):
    """Prompt/question text."""
    return _c("peach", text, bold=True)


def commit_title(text):
    """Commit message title."""
    return _c("green", text, bold=True)


def commit_body(text):
    """Commit message body."""
    return _c("text", text)


def banner(text):
    """Banner/branding text."""
    return _c("mauve", text, bold=True)


def table_header(text):
    """Table header row."""
    return _c("lavender", text, bold=True)


def status_running(text="running"):
    return _c("green", text)


def status_stopped(text="stopped"):
    return _c("overlay", text)


def status_detached(text="detached"):
    return _c("yellow", text)


def status_attached(text="attached"):
    return _c("green", text)


def changes_positive(text):
    return _c("green", text)


def changes_negative(text):
    return _c("red", text)


def format_changes(adds, dels):
    """Format +N -M with colors."""
    parts = []
    if _supports_color():
        parts.append(changes_positive(f"+{adds}"))
        parts.append(changes_negative(f"-{dels}"))
    else:
        parts.append(f"+{adds}")
        parts.append(f"-{dels}")
    return " ".join(parts)
