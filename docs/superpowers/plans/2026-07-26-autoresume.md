# autoresume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-dependency Python CLI that wraps an interactive `claude` session in a pseudo-terminal, detects the usage-limit banner, waits for the reset, and injects `continue` to resume — with a max-resumes cap and a log.

**Architecture:** A thin PTY wrapper (`pty_wrapper.py`) forwards stdin/stdout between the user's terminal and a `claude` child, and feeds every output chunk to a `Resumer` (`resumer.py`). The `Resumer` uses pure detection functions (`detector.py`) to spot the limit banner and parse the reset time, then sleeps and sends the resume message. `cli.py` wires everything with real clock/sleep/log callbacks. All I/O-side effects (clock, sleep, send, log, announce) are injected so the logic is unit-testable without real waiting.

**Tech Stack:** Python 3.8+ standard library only (`pty`, `termios`, `tty`, `select`, `signal`, `fcntl`, `struct`, `re`, `argparse`, `datetime`). pytest for tests (dev-only).

## Global Constraints

- **Python 3.8+**, macOS target. **Standard library only — NO third-party runtime dependencies.** (pytest is a dev-only dependency.)
- **All side effects are injected.** Pure functions in `detector.py` never call `datetime.now()`; `now` is always passed in. `Resumer` receives `now`, `sleep`, `send`, `log`, `announce` callbacks.
- **Local naive `datetime`** everywhere (no timezones).
- **Resume message** is `resume_message + "\r"` (the pty's cooked-mode `ICRNL` turns `\r` into newline for the child).
- Package layout:
  ```
  autoresume/{__init__,detector,resumer,pty_wrapper,cli,__main__}.py
  tests/{test_detector,test_resumer,test_pty_integration}.py
  tests/fake_child.py
  pyproject.toml
  README.md
  ```
- Default flags: `--max-resumes 5`, `--poll-interval 15` (minutes), `--reset-buffer 45` (seconds), `--resume-message continue`, `--log-file ~/.autoresume/autoresume.log`.

---

### Task 1: Project scaffold + `detector.strip_ansi`

**Files:**
- Create: `pyproject.toml`
- Create: `autoresume/__init__.py`
- Create: `autoresume/detector.py`
- Create: `tests/__init__.py`
- Create: `tests/test_detector.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `strip_ansi(text: str) -> str` — removes ANSI/CSI/OSC escape sequences from rendered terminal text.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "autoresume"
version = "0.1.0"
description = "Auto-resume unattended interactive Claude Code sessions after a usage-limit reset"
requires-python = ">=3.8"
dependencies = []

[project.scripts]
autoresume = "autoresume.cli:main"

[project.optional-dependencies]
dev = ["pytest>=7"]

[tool.setuptools]
packages = ["autoresume"]
```

- [ ] **Step 2: Create empty package/test init files**

Create `autoresume/__init__.py` with:

```python
__version__ = "0.1.0"
```

Create `tests/__init__.py` as an empty file.

- [ ] **Step 3: Write the failing test**

Create `tests/test_detector.py`:

```python
from autoresume.detector import strip_ansi


def test_strip_ansi_removes_color_codes():
    assert strip_ansi("\x1b[31mhello\x1b[0m") == "hello"


def test_strip_ansi_removes_cursor_and_clear():
    assert strip_ansi("\x1b[2J\x1b[Hfoo") == "foo"


def test_strip_ansi_leaves_plain_text_untouched():
    assert strip_ansi("just text 123") == "just text 123"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_detector.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` (no `strip_ansi`).

- [ ] **Step 5: Write minimal implementation**

Create `autoresume/detector.py`:

```python
import re

_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]"          # CSI sequences (color, cursor, clear)
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC sequences
    r"|\x1b[()][0-9A-Za-z]"                # charset selection
)


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_detector.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml autoresume/__init__.py autoresume/detector.py tests/__init__.py tests/test_detector.py
git commit -m "feat: project scaffold + strip_ansi"
```

---

### Task 2: `detector.parse_reset_time` + `detect_limit`

**Files:**
- Modify: `autoresume/detector.py`
- Modify: `tests/test_detector.py`

**Interfaces:**
- Consumes: `strip_ansi` (same module).
- Produces:
  - `LimitEvent` dataclass with fields `reset_at: Optional[datetime]` and `raw: str`.
  - `parse_reset_time(text: str, now: datetime) -> Optional[datetime]` — parses absolute (`resets 3pm`, `resets at 11:30pm`) and relative (`resets in 2 hours`, `resets in 45 minutes`) phrasings; rolls past absolute times to the next day; returns `None` if unparseable.
  - `detect_limit(text: str, now: datetime) -> Optional[LimitEvent]` — returns a `LimitEvent` when a limit banner is present (with `reset_at=None` if the time is unparseable), else `None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_detector.py`:

```python
from datetime import datetime
from autoresume.detector import parse_reset_time, detect_limit, LimitEvent


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_detector.py -v`
Expected: FAIL with `ImportError` for `parse_reset_time` / `detect_limit` / `LimitEvent`.

- [ ] **Step 3: Write minimal implementation**

Append to `autoresume/detector.py`:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_detector.py -v`
Expected: PASS (all detector tests green).

- [ ] **Step 5: Commit**

```bash
git add autoresume/detector.py tests/test_detector.py
git commit -m "feat: detect limit banner and parse reset time"
```

---

### Task 3: `resumer.Resumer` state machine

**Files:**
- Create: `autoresume/resumer.py`
- Create: `tests/test_resumer.py`

**Interfaces:**
- Consumes: `strip_ansi`, `detect_limit`, `LimitEvent` from `autoresume.detector`.
- Produces: `Resumer` class.
  - Constructor (all keyword-only): `Resumer(*, send, announce, log, now, sleep, max_resumes=5, poll_interval_s=900, reset_buffer_s=45, resume_message="continue", buffer_chars=8192)`.
    - `send(text: str) -> None` — write the resume string to the child.
    - `announce(msg: str) -> None` — surface an inline banner to the user.
    - `log(msg: str) -> None` — append to the log.
    - `now() -> datetime` — current time.
    - `sleep(seconds: float) -> None` — block for `seconds`.
  - `feed(self, chunk: str) -> None` — called by the wrapper with each output chunk. Detects the banner (debounced), and on a fresh limit performs the wait-and-resume, respecting the cap.
  - Public attribute `resume_count: int`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resumer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_resumer.py -v`
Expected: FAIL with `ModuleNotFoundError: autoresume.resumer`.

- [ ] **Step 3: Write minimal implementation**

Create `autoresume/resumer.py`:

```python
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
        self._limit_active = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_resumer.py -v`
Expected: PASS (all resumer tests green).

- [ ] **Step 5: Commit**

```bash
git add autoresume/resumer.py tests/test_resumer.py
git commit -m "feat: Resumer state machine with cap and poll fallback"
```

---

### Task 4: `pty_wrapper.run` + integration test

**Files:**
- Create: `autoresume/pty_wrapper.py`
- Create: `tests/fake_child.py`
- Create: `tests/test_pty_integration.py`

**Interfaces:**
- Consumes: a `make_resumer(send)` factory returning an object with `feed(text: str) -> None` (the `Resumer` from Task 3; `send` writes bytes/str to the child).
- Produces: `run(argv, make_resumer, *, stdin_fd=None, stdout_fd=None) -> int` — spawns `argv` in a pty, forwards I/O both ways, feeds child output to the resumer, returns the child's exit code.

- [ ] **Step 1: Write the fake child**

Create `tests/fake_child.py`:

```python
import sys
import time

# Print a limit banner whose reset is "now", then wait for the injected resume.
sys.stdout.write("Claude usage limit reached. resets in 0 minutes\n")
sys.stdout.flush()

line = sys.stdin.readline()
if "continue" in line:
    sys.stdout.write("GOTRESUME\n")
    sys.stdout.flush()

time.sleep(0.1)
```

- [ ] **Step 2: Write the failing integration test**

Create `tests/test_pty_integration.py`:

```python
import datetime
import os
import pty
import sys
import threading
import time

from autoresume import pty_wrapper
from autoresume.resumer import Resumer


def test_wrapper_injects_continue_on_limit():
    out_master, out_slave = pty.openpty()
    in_r, in_w = os.pipe()

    def make_resumer(send):
        return Resumer(
            send=send,
            announce=lambda m: None,
            log=lambda m: None,
            now=datetime.datetime.now,
            sleep=lambda s: time.sleep(min(s, 0.05)),
            max_resumes=1,
            poll_interval_s=1,
            reset_buffer_s=0,
        )

    child = [sys.executable, os.path.join(os.path.dirname(__file__), "fake_child.py")]
    result = {}

    def target():
        result["code"] = pty_wrapper.run(
            child, make_resumer, stdin_fd=in_r, stdout_fd=out_slave
        )

    t = threading.Thread(target=target)
    t.start()

    collected = b""
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            data = os.read(out_master, 1024)
        except OSError:
            break
        if not data:
            break
        collected += data
        if b"GOTRESUME" in collected:
            break

    t.join(timeout=5)
    os.close(in_w)
    assert b"GOTRESUME" in collected
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_pty_integration.py -v`
Expected: FAIL with `ModuleNotFoundError: autoresume.pty_wrapper`.

- [ ] **Step 4: Write minimal implementation**

Create `autoresume/pty_wrapper.py`:

```python
import fcntl
import os
import pty
import select
import signal
import struct
import sys
import termios
import tty


def _get_winsize(fd):
    data = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 8)
    rows, cols, _, _ = struct.unpack("HHHH", data)
    return rows, cols


def _set_winsize(fd, rows, cols):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def _exit_code(status):
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1


def run(argv, make_resumer, *, stdin_fd=None, stdout_fd=None):
    stdin_fd = sys.stdin.fileno() if stdin_fd is None else stdin_fd
    stdout_fd = sys.stdout.fileno() if stdout_fd is None else stdout_fd

    pid, master_fd = pty.fork()
    if pid == 0:  # child
        os.execvp(argv[0], argv)
        os._exit(1)  # only reached if execvp fails

    def send(text):
        data = text.encode() if isinstance(text, str) else text
        os.write(master_fd, data)

    resumer = make_resumer(send)

    # Match the child pty size to the real terminal, and keep it in sync.
    try:
        _set_winsize(master_fd, *_get_winsize(stdout_fd))
    except OSError:
        pass

    def on_winch(signum, frame):
        try:
            _set_winsize(master_fd, *_get_winsize(stdout_fd))
        except OSError:
            pass

    try:
        signal.signal(signal.SIGWINCH, on_winch)
    except ValueError:
        pass  # not on the main thread (e.g. under test)

    old_attr = None
    try:
        old_attr = termios.tcgetattr(stdin_fd)
        tty.setraw(stdin_fd)
    except termios.error:
        pass  # stdin is not a tty (e.g. a pipe under test)

    try:
        while True:
            try:
                rlist, _, _ = select.select([stdin_fd, master_fd], [], [])
            except (select.error, InterruptedError):
                continue

            if master_fd in rlist:
                try:
                    data = os.read(master_fd, 65536)
                except OSError:
                    data = b""
                if not data:
                    break
                os.write(stdout_fd, data)
                resumer.feed(data.decode(errors="replace"))

            if stdin_fd in rlist:
                data = os.read(stdin_fd, 65536)
                if not data:
                    break
                os.write(master_fd, data)
    finally:
        if old_attr is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attr)
        os.close(master_fd)

    _, status = os.waitpid(pid, 0)
    return _exit_code(status)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_pty_integration.py -v`
Expected: PASS (the fake child receives `continue` and emits `GOTRESUME`).

- [ ] **Step 6: Run the whole suite**

Run: `python -m pytest -v`
Expected: PASS (all detector, resumer, and integration tests green).

- [ ] **Step 7: Commit**

```bash
git add autoresume/pty_wrapper.py tests/fake_child.py tests/test_pty_integration.py
git commit -m "feat: PTY wrapper forwarding I/O and driving the resumer"
```

---

### Task 5: `cli` wiring, entry point, and README

**Files:**
- Create: `autoresume/cli.py`
- Create: `autoresume/__main__.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `Resumer` from `autoresume.resumer`, `run` from `autoresume.pty_wrapper`.
- Produces: `build_parser() -> argparse.ArgumentParser`, `main(argv=None) -> int`. Console entry point `autoresume` (declared in `pyproject.toml`, Task 1).

- [ ] **Step 1: Write the CLI**

Create `autoresume/cli.py`:

```python
import argparse
import datetime
import os
import sys
import time
from pathlib import Path

from .resumer import Resumer
from . import pty_wrapper


def build_parser():
    p = argparse.ArgumentParser(
        prog="autoresume",
        description="Wrap an interactive Claude Code session and auto-resume it "
        "after a usage-limit reset. Usage: autoresume [opts] -- claude [args]",
    )
    p.add_argument("--max-resumes", type=int, default=5,
                   help="stop after this many auto-resumes (default 5)")
    p.add_argument("--poll-interval", type=int, default=15,
                   help="minutes between retries when the reset time is unknown "
                        "(default 15)")
    p.add_argument("--reset-buffer", type=int, default=45,
                   help="seconds to wait past the parsed reset time (default 45)")
    p.add_argument("--resume-message", default="continue",
                   help="text sent to resume the session (default 'continue')")
    p.add_argument("--log-file",
                   default=str(Path.home() / ".autoresume" / "autoresume.log"),
                   help="path to the event log")
    p.add_argument("command", nargs=argparse.REMAINDER,
                   help="the command to run, e.g. -- claude")
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("no command given; use: autoresume -- claude [args]")

    log_path = Path(args.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", buffering=1)

    def log(msg):
        log_file.write(
            "{} {}\n".format(datetime.datetime.now().isoformat(timespec="seconds"), msg)
        )

    def announce(msg):
        # Raw terminal mode needs explicit CR+LF.
        os.write(sys.stdout.fileno(), ("\r\n" + msg + "\r\n").encode())

    def make_resumer(send):
        return Resumer(
            send=send,
            announce=announce,
            log=log,
            now=datetime.datetime.now,
            sleep=time.sleep,
            max_resumes=args.max_resumes,
            poll_interval_s=args.poll_interval * 60,
            reset_buffer_s=args.reset_buffer,
            resume_message=args.resume_message,
        )

    log("start: {}".format(" ".join(command)))
    code = pty_wrapper.run(command, make_resumer)
    log("exit {}".format(code))
    log_file.close()
    return code
```

- [ ] **Step 2: Write the module entry point**

Create `autoresume/__main__.py`:

```python
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Verify `--help` and the no-command error work**

Run: `python -m autoresume --help`
Expected: usage text is printed, exit code 0.

Run: `python -m autoresume`
Expected: error `no command given; use: autoresume -- claude [args]`, exit code 2.

- [ ] **Step 4: Smoke-test end to end against a fake child**

Run:
```bash
python -m autoresume --reset-buffer 0 -- python tests/fake_child.py
```
Expected: within a moment you see `GOTRESUME` printed (the wrapper detected the banner, waited ~0s, and injected `continue`), an `[autoresume] limit detected …` banner appears, and a line was appended to `~/.autoresume/autoresume.log`.

- [ ] **Step 5: Write the README**

Create `README.md`:

```markdown
# autoresume

Auto-resume an unattended interactive Claude Code session after a usage-limit
reset. Wrap your normal command:

    autoresume -- claude

When Claude prints a usage-limit banner ("… limit reached ∙ resets 3pm"),
`autoresume` parses the reset time, waits, and sends `continue` so the session
picks up where it left off. It stops after `--max-resumes` (default 5) to avoid
waiting forever on a weekly limit.

## Install

    pip install -e .

## Usage

    autoresume [options] -- <command...>

Options:

- `--max-resumes N`      stop after N auto-resumes (default 5)
- `--poll-interval M`    minutes between retries when the reset time can't be
                         parsed (default 15)
- `--reset-buffer S`     seconds to wait past the parsed reset time (default 45)
- `--resume-message MSG` text sent to resume (default `continue`)
- `--log-file PATH`      event log (default `~/.autoresume/autoresume.log`)

## How it works

`autoresume` spawns the command inside a pseudo-terminal and forwards your
keyboard and its screen transparently. In the background it strips ANSI from the
output, watches for the limit banner, and injects the resume message at the
reset time. Everything is Python standard library — no dependencies.

## Development

    pip install -e '.[dev]'
    python -m pytest -v

## Scope

Interactive sessions only (not `claude -p` / SDK runs). It does not change your
usage limits — it only removes the babysitting.
```

- [ ] **Step 6: Run the full suite one more time**

Run: `python -m pytest -v`
Expected: PASS (all tests green).

- [ ] **Step 7: Commit**

```bash
git add autoresume/cli.py autoresume/__main__.py README.md
git commit -m "feat: CLI wiring, entry point, and README"
```

---

## Self-Review Notes

- **Spec coverage:** PTY wrapper (Task 4) ✓; detector strip/detect/parse (Tasks 1–2) ✓; Resumer state machine, cap, poll fallback, resume message (Task 3) ✓; inline banner + log observability (Task 3 announce/log + Task 5 wiring) ✓; flags & defaults (Task 5) ✓; `--` invocation (Task 5) ✓; clean exit-code propagation (Task 4) ✓; edge cases — past reset time, relative phrasing, unparseable time, weekly re-limit cap (Tasks 2–3) ✓; testing strategy incl. fake-child integration (Task 4) ✓. Desktop notifications intentionally omitted (non-goal).
- **Type consistency:** `Resumer.feed`/`send`/`now`/`sleep`/`announce`/`log` signatures identical in Tasks 3, 4, 5. `make_resumer(send)` factory identical in Tasks 4 and 5. `detect_limit`/`parse_reset_time`/`LimitEvent`/`strip_ansi` names identical across Tasks 1–3.
- **No placeholders:** every code step contains complete, runnable code.
```
