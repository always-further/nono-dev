"""Terminal styling with Catppuccin Mocha palette."""

import re
import sys

# Matches CSI sequences (colors, bold, reset, etc.). Good enough for our
# palette; we never emit cursor-movement sequences.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

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


# -- visible-width helpers ---------------------------------------------------
#
# Python's `str.ljust` / f-string `:<N` pad by raw code-point count, which
# includes the invisible bytes in ANSI escape sequences. That means any
# attempt to lay out styled columns with ljust alone produces staggered
# output -- each `style.*` call adds ~20-24 bytes of invisible prefix/suffix,
# and rows with more styled segments end up visibly shorter than rows with
# fewer. These helpers fix that by sizing padding to the *displayed* width.


def strip_ansi(text):
    """Return `text` with ANSI CSI escape sequences removed."""
    return _ANSI_ESCAPE_RE.sub("", str(text))


def visible_len(text):
    """Return the displayed width of `text`, ignoring ANSI escapes."""
    return len(strip_ansi(text))


def pad_visible(text, width):
    """Right-pad `text` so its *visible* width is at least `width`.

    ANSI escape bytes don't count toward the width. Safe to call on either
    styled or plain text.
    """
    pad = max(0, width - visible_len(text))
    return f"{text}{' ' * pad}"


# Shared column widths for CLI help output. Picked to fit the longest
# command we currently ship (`graph explain`/`graph upgrade` at 13) and
# the longest args spec (`[-m name] <cmd>` at 15) with a small visual
# buffer. Bump these if a longer command/arg is added.
HELP_CMD_WIDTH = 15
HELP_ARGS_WIDTH = 17


def help_row(cmd, args, desc, indent="    "):
    """Format a three-column help row with ANSI-safe alignment.

    Layout:
        <indent><cmd (CMD_WIDTH visible)>  <args (ARGS_WIDTH visible)>  <desc>

    Pass an empty string for `args` when a command takes no positional args;
    the column still pads so the description stays in line with sibling rows.
    """
    cmd_col = pad_visible(value(cmd), HELP_CMD_WIDTH)
    args_col = pad_visible(muted(args) if args else "", HELP_ARGS_WIDTH)
    return f"{indent}{cmd_col}  {args_col}  {dim(desc)}"


# -- status lines ------------------------------------------------------------
#
# Install/dotfiles/setup commands print a series of "  <label>  <message>"
# lines. The labels are short words like ok/run/warn/skip/error, and the
# natural tendency is to hard-code spaces after each one ("  ok    done",
# "  error  failed") -- but that drifts by 1-3 columns depending on label
# length, which is exactly what produced the misaligned `nd install` output.
# `status()` centralises the styling *and* pads every label to the width of
# the longest one so the message column always lines up.


# Widest status label in use ("backup" in dotfiles output). Every label
# gets padded to this visible width so message columns line up. Bump this
# if a longer status label is added -- and update STATUS_CONTINUATION_INDENT
# below to match.
STATUS_LABEL_WIDTH = 6

# Leading-whitespace prefix for continuation lines that should align with
# the message column, not the label. `f"  <label(6)>  <msg>"` puts the
# message at visible column 10 (2 indent + 6 label + 2 gap), so a 10-space
# indent aligns a follow-up line underneath.
STATUS_CONTINUATION_INDENT = " " * 10

# Map status kinds to (palette color, bold). `ok`/`run`/`info`/`brew`/`write`
# share blue so the eye treats them as "normal progress"; warn/note are
# yellow; error/fail are red; backup is teal (value-like).
_STATUS_STYLES = {
    "ok":      ("blue",    False),
    "run":     ("blue",    False),
    "info":    ("blue",    False),
    "brew":    ("blue",    False),
    "write":   ("blue",    False),
    "done":    ("green",   True),
    "skip":    ("subtext", False),
    "warn":    ("yellow",  False),
    "warning": ("yellow",  False),
    "note":    ("yellow",  False),
    "error":   ("red",     True),
    "fail":    ("red",     True),
    "backup":  ("teal",    False),
}


def status(kind, text=None):
    """Styled, width-padded status label for indented setup output.

    Usage:
        print(f"  {status('run')}  uv tool install ...")
        print(f"  {status('ok')}  nono-dev installed")
        print(f"  {status('error')}  uv not found on PATH")
        print(f"  {status('skip')}  already installed")
        print(f"  {status('error', 'fail')}  custom label text")

    The label defaults to `kind` itself; pass `text` to display a different
    word while keeping kind-driven coloring. The returned string is padded
    to STATUS_LABEL_WIDTH *visible* characters, so successive lines align
    regardless of which kind is used.
    """
    color, bold = _STATUS_STYLES.get(kind, ("blue", False))
    label = text if text is not None else kind
    return pad_visible(_c(color, label, bold=bold), STATUS_LABEL_WIDTH)
