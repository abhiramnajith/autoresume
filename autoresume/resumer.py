from .detector import strip_ansi, detect_limit


class Resumer:
    def __init__(
        self,
        *,
        send,
        announce,
        log,
        now,
        sleep,
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
        self._sleep = sleep
        self.max_resumes = max_resumes
        self.poll_interval_s = poll_interval_s
        self.reset_buffer_s = reset_buffer_s
        self.resume_message = resume_message
        self.buffer_chars = buffer_chars
        self._buf = ""
        self._limit_active = False
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
        self._handle_limit(event)

    def _handle_limit(self, event):
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
                "limit reset_at={} wait_s={:.0f}".format(
                    event.reset_at.isoformat(), wait_s
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
            self._log("limit reset_at=unknown poll_s={}".format(wait_s))

        self._sleep(wait_s)
        self._send(self.resume_message + "\r")
        self._log("sent resume (resume {})".format(self.resume_count))
        self._buf = ""            # drop the stale banner so it can't re-trigger
