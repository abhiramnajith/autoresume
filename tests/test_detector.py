from datetime import datetime
from autoresume.detector import strip_ansi, parse_reset_time, detect_limit, LimitEvent


def test_strip_ansi_removes_color_codes():
    assert strip_ansi("\x1b[31mhello\x1b[0m") == "hello"


def test_strip_ansi_removes_cursor_and_clear():
    assert strip_ansi("\x1b[2J\x1b[Hfoo") == "foo"


def test_strip_ansi_leaves_plain_text_untouched():
    assert strip_ansi("just text 123") == "just text 123"


def test_parse_absolute_time_today():
    now = datetime(2026, 7, 26, 14, 0)
    assert parse_reset_time("resets 3pm", now) == datetime(2026, 7, 26, 15, 0)


def test_parse_absolute_time_with_minutes():
    now = datetime(2026, 7, 26, 20, 0)
    assert parse_reset_time("resets at 11:30pm", now) == datetime(2026, 7, 26, 23, 30)


def test_parse_absolute_time_in_past_rolls_to_next_day():
    now = datetime(2026, 7, 26, 16, 0)
    assert parse_reset_time("resets 3pm", now) == datetime(2026, 7, 27, 15, 0)


def test_parse_noon_and_midnight():
    now = datetime(2026, 7, 26, 6, 0)
    assert parse_reset_time("resets 12pm", now) == datetime(2026, 7, 26, 12, 0)
    now2 = datetime(2026, 7, 26, 6, 0)
    assert parse_reset_time("resets 12am", now2) == datetime(2026, 7, 27, 0, 0)


def test_parse_relative_hours_and_minutes():
    now = datetime(2026, 7, 26, 14, 0)
    assert parse_reset_time("resets in 2 hours", now) == datetime(2026, 7, 26, 16, 0)
    assert parse_reset_time("resets in 45 minutes", now) == datetime(2026, 7, 26, 14, 45)


def test_parse_unparseable_returns_none():
    now = datetime(2026, 7, 26, 14, 0)
    assert parse_reset_time("no time here", now) is None


def test_detect_limit_returns_event_with_reset():
    now = datetime(2026, 7, 26, 14, 0)
    event = detect_limit("Claude usage limit reached. resets 3pm", now)
    assert isinstance(event, LimitEvent)
    assert event.reset_at == datetime(2026, 7, 26, 15, 0)


def test_detect_limit_unknown_time_has_none_reset():
    now = datetime(2026, 7, 26, 14, 0)
    event = detect_limit("usage limit reached", now)
    assert event is not None
    assert event.reset_at is None


def test_detect_limit_returns_none_when_no_banner():
    now = datetime(2026, 7, 26, 14, 0)
    assert detect_limit("everything is fine", now) is None


def test_parse_24_hour_time():
    now = datetime(2026, 7, 26, 14, 0)
    assert parse_reset_time("resets at 15:00", now) == datetime(2026, 7, 26, 15, 0)


def test_parse_24_hour_time_rolls_to_next_day():
    now = datetime(2026, 7, 26, 16, 0)
    assert parse_reset_time("resets 09:30", now) == datetime(2026, 7, 27, 9, 30)


def test_parse_absolute_time_ignores_timezone_suffix():
    now = datetime(2026, 7, 26, 14, 0)
    assert parse_reset_time("resets 3pm (America/New_York)", now) == datetime(
        2026, 7, 26, 15, 0
    )


def test_detect_weekly_limit_reordered_phrasing():
    now = datetime(2026, 7, 26, 14, 0)
    assert detect_limit("You've reached your weekly limit.", now) is not None


def test_detect_weekly_limit_keyword():
    now = datetime(2026, 7, 26, 14, 0)
    assert detect_limit("weekly limit reached", now) is not None


# Real Claude Code banner captured from a live session (2026-07-26):
#   "You've hit your session limit · resets 11am (Asia/Calcutta)"
# Pinned here so the detector stays matched to real output, not assumed wording.
def test_detect_real_session_limit_banner():
    now = datetime(2026, 7, 26, 7, 0)
    banner = "You've hit your session limit · resets 11am (Asia/Calcutta)"
    event = detect_limit(banner, now)
    assert event is not None
    assert event.reset_at == datetime(2026, 7, 26, 11, 0)


def test_detect_session_limit_keyword():
    now = datetime(2026, 7, 26, 7, 0)
    assert detect_limit("You've hit your session limit", now) is not None
