from datetime import datetime, timedelta
from autoresume.resumer import Resumer


class Recorder:
    """Captures Resumer side effects and provides a manually-advanced fake clock."""

    def __init__(self, start):
        self.sent = []
        self.announced = []
        self.logged = []
        self._now = start

    def send(self, text):
        self.sent.append(text)

    def announce(self, msg):
        self.announced.append(msg)

    def log(self, msg):
        self.logged.append(msg)

    def now(self):
        return self._now

    def advance(self, seconds):
        self._now = self._now + timedelta(seconds=seconds)


def make_resumer(rec, **kw):
    return Resumer(
        send=rec.send, announce=rec.announce, log=rec.log,
        now=rec.now, reset_buffer_s=0, **kw,
    )


def test_arms_wait_but_does_not_send_until_due():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec)
    r.feed("Claude usage limit reached. resets 3pm")
    # armed for ~1 hour, nothing sent yet
    assert abs(r.seconds_until_wake() - 3600) < 2
    assert rec.sent == []
    r.maybe_resume()          # not due yet
    assert rec.sent == []
    rec.advance(3600)
    r.maybe_resume()          # now due
    assert rec.sent == ["continue\r"]
    assert r.seconds_until_wake() is None
    assert r.resume_count == 1


def test_debounces_repeated_banner_in_buffer():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec)
    r.feed("usage limit reached. resets 3pm")
    r.feed("usage limit reached. resets 3pm")  # same banner again
    rec.advance(3600)
    r.maybe_resume()
    assert rec.sent == ["continue\r"]  # only one resume


def test_stops_at_max_resumes():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec, max_resumes=2)
    for _ in range(3):
        r.feed("usage limit reached. resets 3pm")
        # advance by the actual armed wait (not a fixed 3600s): a repeated
        # "resets 3pm" banner rolls to the next day once `now` reaches 15:00,
        # so a hardcoded advance would never let the second resume fire.
        rec.advance(r.seconds_until_wake() or 3600)
        r.maybe_resume()
        r.feed("working normally now")  # re-arm between banners
    assert len(rec.sent) == 2
    assert any("max resumes" in a.lower() for a in rec.announced)


def test_unknown_reset_time_uses_poll_interval():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec, poll_interval_s=900)
    r.feed("usage limit reached — resets shortly")  # banner, but time unparseable
    assert abs(r.seconds_until_wake() - 900) < 2
    assert rec.sent == []
    rec.advance(900)
    r.maybe_resume()
    assert rec.sent == ["continue\r"]


def test_custom_resume_message_and_reset_buffer():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = Resumer(
        send=rec.send, announce=rec.announce, log=rec.log, now=rec.now,
        reset_buffer_s=30, resume_message="please continue",
    )
    r.feed("usage limit reached. resets in 10 minutes")
    assert abs(r.seconds_until_wake() - (600 + 30)) < 2
    rec.advance(600 + 30)
    r.maybe_resume()
    assert rec.sent == ["please continue\r"]


def test_cancel_wait_prevents_resume():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec)
    r.feed("usage limit reached. resets 3pm")
    assert r.seconds_until_wake() is not None
    assert r.cancel_wait() is True
    assert r.seconds_until_wake() is None
    rec.advance(3600)
    r.maybe_resume()
    assert rec.sent == []  # cancelled, never sent
    assert any("cancelled" in a.lower() for a in rec.announced)
    assert r.cancel_wait() is False  # nothing pending now


def test_polls_do_not_spend_the_resume_budget():
    """Unknown reset times must not burn max_resumes (the old bug: 5 polls
    exhausted the budget in 5 * poll_interval and gave up before the reset)."""
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec, max_resumes=5, max_polls=10, poll_interval_s=1800)
    for _ in range(10):
        r.feed("usage limit reached — resets shortly")
        rec.advance(r.seconds_until_wake())
        r.maybe_resume()
        r.feed("still limited")  # no banner in this chunk: re-arms detection
    assert len(rec.sent) == 10          # polled the full 10 times (5 hours)
    assert r.resume_count == 0          # ...without spending a resume
    assert r.poll_count == 10


def test_poll_budget_is_capped():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec, max_polls=3, poll_interval_s=1800)
    for _ in range(5):
        r.feed("usage limit reached — resets shortly")
        rec.advance(r.seconds_until_wake() or 1800)
        r.maybe_resume()
        r.feed("still limited")
    assert len(rec.sent) == 3
    assert any("without a reset" in a for a in rec.announced)


def test_poll_budget_resets_after_productive_gap():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec, max_polls=2, poll_interval_s=1800)
    r.feed("usage limit reached — resets shortly")
    rec.advance(r.seconds_until_wake())
    r.maybe_resume()
    r.feed("working normally now")
    rec.advance(6 * 3600)  # long productive stretch
    r.feed("usage limit reached — resets shortly")
    assert r.poll_count == 1  # fresh budget, not 2
