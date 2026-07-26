import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI sequences (color, cursor, clear)
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences
    r"|\x1b[()][0-9A-Za-z]"                # charset selection
)


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


_LIMIT_RE = re.compile(
    r"limit reached"
    r"|(?:usage|session|weekly|daily|rate) limit(?:\s+(?:reached|exceeded))?"
    r"|(?:hit|reached|exceeded) your (?:\w+\s+){0,3}limit",
    re.IGNORECASE,
)
# A real banner attaches its reset clause DIRECTLY to the limit phrase, with
# only separators in between, e.g. "session limit · resets 11am". Requiring the
# reset clause immediately after the phrase (no intervening words) rejects prose
# that merely discusses limits, e.g. "a weekly limit. The window resets at 3pm".
# See detect_limit().
_AFTER_LIMIT_RE = re.compile(
    r"[\s·∙•|,:.\-–—/()]*(?:resets\b|reset\s+(?:at|in)\b)", re.IGNORECASE
)
_RESET_WINDOW = 120
_REL_RE = re.compile(
    r"reset[s]?\s+in\s+(\d+)\s*(hour|hr|minute|min)s?", re.IGNORECASE
)
_ABS12_RE = re.compile(
    r"reset[s]?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", re.IGNORECASE
)
_ABS24_RE = re.compile(
    r"reset[s]?\s+(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)(?!\s*[ap]\.?m)", re.IGNORECASE
)


@dataclass
class LimitEvent:
    reset_at: Optional[datetime]
    raw: str


def parse_reset_time(text: str, now: datetime) -> Optional[datetime]:
    m = _REL_RE.search(text)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith(("hour", "hr")):
            return now + timedelta(hours=n)
        return now + timedelta(minutes=n)

    m = _ABS12_RE.search(text)
    if m:
        hour = int(m.group(1)) % 12
        minute = int(m.group(2) or 0)
        if m.group(3).lower() == "p":
            hour += 12
        return _next_occurrence(now, hour, minute)

    m = _ABS24_RE.search(text)
    if m:
        return _next_occurrence(now, int(m.group(1)), int(m.group(2)))

    return None


def _next_occurrence(now, hour, minute):
    cand = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(days=1)
    return cand


def detect_limit(text: str, now: datetime) -> Optional[LimitEvent]:
    # A real banner attaches its reset clause directly to the limit phrase
    # ("session limit · resets 11am"). Only fire when a reset clause immediately
    # follows the phrase (separators but no words between) — so prose that merely
    # mentions limits, or a limit phrase and a "resets" from an unrelated
    # sentence, does not false-trigger.
    for m in _LIMIT_RE.finditer(text):
        if _AFTER_LIMIT_RE.match(text, m.end()):
            window = text[m.start():m.end() + _RESET_WINDOW]
            return LimitEvent(
                reset_at=parse_reset_time(window, now),
                raw=window.strip()[:160],
            )
    return None
