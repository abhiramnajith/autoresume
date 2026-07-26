import re

_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI sequences (color, cursor, clear)
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences
    r"|\x1b[()][0-9A-Za-z]"                # charset selection
)


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)
