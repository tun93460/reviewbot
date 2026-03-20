"""ANSI terminal styling — applied only when the stream is a TTY.

Colors are suppressed when:
  - The stream is not a TTY (e.g. piped to Claude or another process)
  - The NO_COLOR environment variable is set
"""
import os
import sys

_NO_COLOR = bool(os.environ.get("NO_COLOR"))

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RED    = "\033[31m"
_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"


def _c(code: str, text: str, stream) -> str:
    if _NO_COLOR or not (hasattr(stream, "isatty") and stream.isatty()):
        return text
    return f"{code}{text}{_RESET}"


def bold(text: str, stream=sys.stdout)   -> str: return _c(_BOLD,   text, stream)
def dim(text: str, stream=sys.stdout)    -> str: return _c(_DIM,    text, stream)
def red(text: str, stream=sys.stdout)    -> str: return _c(_RED,    text, stream)
def green(text: str, stream=sys.stdout)  -> str: return _c(_GREEN,  text, stream)
def yellow(text: str, stream=sys.stdout) -> str: return _c(_YELLOW, text, stream)
def cyan(text: str, stream=sys.stdout)   -> str: return _c(_CYAN,   text, stream)


_PIPELINE_COLORS = {
    "success": green,
    "passed":  green,
    "failed":  red,
    "canceled": red,
    "running": yellow,
    "pending": yellow,
    "created": dim,
    "skipped": dim,
    "manual":  dim,
}


def pipeline(status: str | None, stream=sys.stdout) -> str:
    """Return status string styled by pipeline result."""
    if not status:
        return ""
    fn = _PIPELINE_COLORS.get(status, lambda t, s=sys.stdout: t)
    return fn(status, stream)
