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


_LIMIT_RE = re.compile(r"limit reached|usage limit", re.IGNORECASE)
_REL_RE = re.compile(
    r"reset[s]?\s+in\s+(\d+)\s*(hour|hr|minute|min)s?", re.IGNORECASE
)
_ABS_RE = re.compile(
    r"reset[s]?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", re.IGNORECASE
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

    m = _ABS_RE.search(text)
    if m:
        hour = int(m.group(1)) % 12
        minute = int(m.group(2) or 0)
        if m.group(3).lower() == "p":
            hour += 12
        cand = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if cand <= now:
            cand += timedelta(days=1)
        return cand

    return None


def detect_limit(text: str, now: datetime) -> Optional[LimitEvent]:
    m = _LIMIT_RE.search(text)
    if not m:
        return None
    return LimitEvent(reset_at=parse_reset_time(text, now), raw=m.group(0))
