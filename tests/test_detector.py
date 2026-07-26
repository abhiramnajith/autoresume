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
