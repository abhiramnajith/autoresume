from autoresume.detector import strip_ansi


def test_strip_ansi_removes_color_codes():
    assert strip_ansi("\x1b[31mhello\x1b[0m") == "hello"


def test_strip_ansi_removes_cursor_and_clear():
    assert strip_ansi("\x1b[2J\x1b[Hfoo") == "foo"


def test_strip_ansi_leaves_plain_text_untouched():
    assert strip_ansi("just text 123") == "just text 123"
