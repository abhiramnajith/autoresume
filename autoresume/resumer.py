from datetime import timedelta

from .detector import strip_ansi, detect_limit


class Resumer:
    def __init__(
        self,
        *,
        send,
        announce,
        log,
        now,
        max_resumes=5,
        max_polls=10,
        poll_interval_s=1800,
        reset_buffer_s=45,
        resume_message="continue",
        buffer_chars=8192,
    ):
        self._send = send
        self._announce = announce
        self._log = log
        self._now = now
        self.max_resumes = max_resumes
        self.max_polls = max_polls
        self.poll_interval_s = poll_interval_s
        self.reset_buffer_s = reset_buffer_s
        self.resume_message = resume_message
        self.buffer_chars = buffer_chars
        self._buf = ""
        self._limit_active = False
        self._wake_at = None
        self.resume_count = 0
        self.poll_count = 0
        self._last_poll_at = None

    def feed(self, chunk):
        self._buf = (self._buf + strip_ansi(chunk))[-self.buffer_chars:]
        event = detect_limit(self._buf, self._now())
        if event is None:
            self._limit_active = False  # productive output re-arms detection
            return
        if self._limit_active:
            return  # debounce: this banner is already being handled
        self._limit_active = True
        self._arm(event)

    def _arm(self, event):
        if event.reset_at is not None:
            self._arm_known(event)
        else:
            self._arm_poll(event)

    def _arm_known(self, event):
        """Reset time is known: sleep until it, spending one resume."""
        if self.resume_count >= self.max_resumes:
            self._announce(
                "[autoresume] max resumes ({}) reached — leaving session idle".format(
                    self.max_resumes
                )
            )
            self._log("cap-reached")
            return

        self.resume_count += 1
        wait_s = max(0.0, (event.reset_at - self._now()).total_seconds())
        wait_s += self.reset_buffer_s
        self._announce(
            "[autoresume] limit detected — waiting until {} (resume {}/{})".format(
                event.reset_at.strftime("%-I:%M%p"),
                self.resume_count,
                self.max_resumes,
            )
        )
        self._log(
            "limit reset_at={} wait_s={:.0f} raw={!r}".format(
                event.reset_at.isoformat(), wait_s, event.raw
            )
        )
        self._schedule(wait_s)

    def _arm_poll(self, event):
        """Reset time is unknown: retry on a fixed interval.

        Polls have their own budget — they must not spend the resume budget,
        which is sized for known reset times. max_polls * poll_interval_s is
        how long we are willing to keep trying blind (default 10 * 30m = 5h,
        one full session window).
        """
        now = self._now()
        # A gap much larger than the poll interval means the session ran
        # productively in between, so this is a fresh limit — start a new
        # poll budget rather than inheriting the old one.
        if (
            self._last_poll_at is not None
            and (now - self._last_poll_at).total_seconds() > 2 * self.poll_interval_s
        ):
            self.poll_count = 0

        if self.poll_count >= self.max_polls:
            self._announce(
                "[autoresume] polled {} times over {:.0f}h without a reset — "
                "leaving session idle".format(
                    self.max_polls, self.max_polls * self.poll_interval_s / 3600.0
                )
            )
            self._log("poll-budget-exhausted")
            return

        self.poll_count += 1
        self._last_poll_at = now
        wait_s = self.poll_interval_s
        self._announce(
            "[autoresume] limit detected — reset time unknown, retrying in {}m "
            "(poll {}/{})".format(
                int(self.poll_interval_s // 60), self.poll_count, self.max_polls
            )
        )
        self._log(
            "limit reset_at=unknown poll_s={} poll={}/{} raw={!r}".format(
                int(wait_s), self.poll_count, self.max_polls, event.raw
            )
        )
        self._schedule(wait_s)

    def _schedule(self, wait_s):
        self._wake_at = self._now() + timedelta(seconds=wait_s)

    def seconds_until_wake(self):
        """Seconds until the pending resume fires, or None if none is pending."""
        if self._wake_at is None:
            return None
        return max(0.0, (self._wake_at - self._now()).total_seconds())

    def maybe_resume(self):
        """Fire a pending resume if its wake time has arrived."""
        if self._wake_at is None:
            return
        if self._now() >= self._wake_at:
            self._send(self.resume_message + "\r")
            self._log(
                "sent resume (resume {}, poll {})".format(
                    self.resume_count, self.poll_count
                )
            )
            self._buf = ""  # drop the stale banner so it can't re-trigger
            self._wake_at = None

    def cancel_wait(self):
        """Cancel a pending resume (e.g. user pressed Ctrl-C). Returns True if one was pending."""
        if self._wake_at is None:
            return False
        self._wake_at = None
        self._announce("[autoresume] wait cancelled — passing input through")
        self._log("wait-cancelled")
        return True
