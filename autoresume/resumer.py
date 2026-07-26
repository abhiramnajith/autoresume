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
        poll_interval_s=900,
        reset_buffer_s=45,
        resume_message="continue",
        buffer_chars=8192,
    ):
        self._send = send
        self._announce = announce
        self._log = log
        self._now = now
        self.max_resumes = max_resumes
        self.poll_interval_s = poll_interval_s
        self.reset_buffer_s = reset_buffer_s
        self.resume_message = resume_message
        self.buffer_chars = buffer_chars
        self._buf = ""
        self._limit_active = False
        self._wake_at = None
        self.resume_count = 0

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
        if self.resume_count >= self.max_resumes:
            self._announce(
                "[autoresume] max resumes ({}) reached — leaving session idle".format(
                    self.max_resumes
                )
            )
            self._log("cap-reached")
            return

        self.resume_count += 1
        if event.reset_at is not None:
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
        else:
            wait_s = self.poll_interval_s
            self._announce(
                "[autoresume] limit detected — reset time unknown, retrying in {}m "
                "(resume {}/{})".format(
                    self.poll_interval_s // 60, self.resume_count, self.max_resumes
                )
            )
            self._log(
                "limit reset_at=unknown poll_s={} raw={!r}".format(wait_s, event.raw)
            )

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
            self._log("sent resume (resume {})".format(self.resume_count))
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
