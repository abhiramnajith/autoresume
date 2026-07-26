from datetime import datetime, timedelta
from autoresume.resumer import Resumer


class Recorder:
    """Captures Resumer side effects and provides an advancing fake clock."""

    def __init__(self, start):
        self.sent = []
        self.announced = []
        self.logged = []
        self.slept = []
        self._now = start

    def send(self, text):
        self.sent.append(text)

    def announce(self, msg):
        self.announced.append(msg)

    def log(self, msg):
        self.logged.append(msg)

    def now(self):
        return self._now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self._now = self._now + timedelta(seconds=seconds)


def make_resumer(rec, **kw):
    return Resumer(
        send=rec.send, announce=rec.announce, log=rec.log,
        now=rec.now, sleep=rec.sleep, reset_buffer_s=0, **kw,
    )


def test_resumes_after_parsed_reset_time():
    start = datetime(2026, 7, 26, 14, 0)
    rec = Recorder(start)
    r = make_resumer(rec)
    r.feed("Claude usage limit reached. resets 3pm")
    # slept ~1 hour (3600s) then sent the resume message
    assert rec.slept and abs(rec.slept[0] - 3600) < 2
    assert rec.sent == ["continue\r"]
    assert r.resume_count == 1


def test_debounces_repeated_banner_in_buffer():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec)
    r.feed("usage limit reached. resets 3pm")
    r.feed("usage limit reached. resets 3pm")  # same banner again
    assert rec.sent == ["continue\r"]  # only one resume


def test_stops_at_max_resumes():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec, max_resumes=2)
    for _ in range(3):
        r.feed("usage limit reached. resets 3pm")
        r.feed("working normally now")  # re-arm between banners
    assert len(rec.sent) == 2
    assert any("max resumes" in a.lower() for a in rec.announced)


def test_unknown_reset_time_uses_poll_interval():
    rec = Recorder(datetime(2026, 7, 26, 14, 0))
    r = make_resumer(rec, poll_interval_s=900)
    r.feed("usage limit reached")  # no parseable time
    assert rec.slept == [900]
    assert rec.sent == ["continue\r"]


def test_custom_resume_message_and_reset_buffer():
    start = datetime(2026, 7, 26, 14, 0)
    rec = Recorder(start)
    r = Resumer(
        send=rec.send, announce=rec.announce, log=rec.log,
        now=rec.now, sleep=rec.sleep, reset_buffer_s=30,
        resume_message="please continue",
    )
    r.feed("usage limit reached. resets in 10 minutes")
    assert abs(rec.slept[0] - (600 + 30)) < 2
    assert rec.sent == ["please continue\r"]
