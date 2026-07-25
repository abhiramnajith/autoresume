# autoresume — Claude Code auto-resume wrapper

**Date:** 2026-07-26
**Status:** Approved design

## Problem

When an unattended interactive Claude Code session hits the subscription usage
limit ("5-hour limit reached ∙ resets 3pm"), it pauses and waits for a human to
come back and type `continue`. For overnight / AFK work this wastes the entire
reset window. Claude Code has no built-in auto-resume (multiple open feature
requests, none shipped as of mid-2026). Existing community tools are mostly
tmux-based screen-scrapers. We want our own, self-contained tool.

## Goal

A single-purpose CLI that transparently wraps an interactive `claude` session,
detects the usage-limit banner, waits for the reset, and sends `continue` to
resume — with a safety cap and a log — so unattended sessions finish on their own.

## Non-goals

- Headless / scripted (`claude -p`, SDK) runs. Interactive sessions only.
- Changing or circumventing actual usage limits. This only removes babysitting.
- tmux integration. We use a self-contained PTY wrapper instead.
- Desktop notifications (explicitly out of scope for v1).

## Approach

Python 3, **standard library only (zero external dependencies)**. Invoked as a
prefix on the normal command:

```
autoresume -- claude [any claude args...]
```

It spawns Claude inside a **pseudo-terminal**, forwarding the user's keystrokes
and Claude's rendered screen in both directions so it behaves identically to
running `claude` directly. In the background it watches the output stream; on a
detected limit banner it parses the reset time, waits, and injects `continue`↵.

## Architecture

Split into focused modules so the logic is unit-testable and the untestable I/O
glue stays thin.

| Module | Responsibility | Testable |
|---|---|---|
| `detector.py` | `strip_ansi(text)` and `detect_limit(text, now) -> LimitEvent \| None`. Pure functions. Regexes for the limit banner and reset-time phrasings; returns event type + resolved reset `datetime` (or `None` when the time is unparseable). | Pure unit tests |
| `resumer.py` | State machine (RUNNING → LIMIT_DETECTED → WAITING → resume). Owns the max-resumes cap, wait scheduling, and the poll-retry fallback. Clock and sleep are injected. | Pure unit tests |
| `pty_wrapper.py` | I/O plumbing: `pty.fork`, raw-mode stdin (`termios`/`tty`), `select` loop forwarding both directions, SIGWINCH window-resize passthrough (`TIOCGWINSZ`/`TIOCSWINSZ`), clean teardown and exit-code propagation. | 1 integration test |
| `cli.py` | Argument parsing, wiring the pieces together, log setup. | Thin |

Entry point: `python -m autoresume ...` / an `autoresume` console script.

## Data flow / core loop

1. `select()` over `[stdin, pty_master]`.
2. stdin bytes → written to the pty (user keystrokes reach Claude).
3. pty bytes → written to stdout (user sees Claude) **and** appended to a rolling
   ~8 KB buffer that is ANSI-stripped and passed to `detector.detect_limit()`.
4. On a detected limit (debounced — one banner triggers once):
   - compute the wait,
   - print an inline banner into the terminal stream, e.g.
     `[autoresume] limit detected — waiting until 3:00pm (resume 1/5)`,
   - sleep until reset time + `--reset-buffer`,
   - write `continue\r` to the pty.
5. If the reset time is **unparseable**, fall back to poll-retry: send the resume
   message every `--poll-interval` minutes (default 15) until activity resumes or
   the cap is hit.
6. The loop re-arms. A re-limit (weekly cap or immediate re-limit) counts against
   `--max-resumes` (default 5); when the cap is reached the tool stops resuming,
   logs it, and leaves the session alive for the user.

## Behavior details

- **Resume message:** `continue`, overridable via `--resume-message`.
- **Flags & defaults:**
  - `--max-resumes 5`
  - `--poll-interval 15` (minutes; unparseable-time fallback)
  - `--reset-buffer 45` (seconds added after the parsed reset time, for safety)
  - `--resume-message continue`
  - `--log-file ~/.autoresume/autoresume.log`
- **Observability:** timestamped **log file** + **inline terminal banners**. No
  desktop notifications.
- **Invocation:** everything after `--` is the command to run.
- **Clean exit:** when Claude exits, restore the terminal mode and propagate its
  exit code.

## Detection specifics

- Maintain a rolling ANSI-stripped buffer of recent output (Claude's TUI redraws,
  so we strip escapes and match on the live rendered text).
- Banner regexes cover known phrasings: "usage limit reached", "5-hour limit
  reached", "Claude usage limit reached", weekly-limit wording.
- Reset-time parsing covers:
  - absolute times: `resets 3pm`, `resets at 11:30pm`, `resets 3:00 PM`
  - relative: `resets in 2 hours`, `resets in 45 minutes`
  - a reset time already in the past (e.g. `3pm` seen at 4pm) rolls to the next
    day.
- Detect only on freshly-arrived output, with a debounce cooldown so a redrawn
  banner does not double-fire.

## Edge cases

- Past reset time → next occurrence.
- Relative vs absolute reset phrasing.
- Unparseable time → poll-retry fallback.
- Repeated / weekly re-limits → bounded by the max-resumes cap.
- Cap reached → stop, log, keep the session alive for manual takeover.

## Testing strategy (TDD)

- **Unit — `detector`:** captured banner strings across the 5-hour and weekly
  limits and every reset-time format, asserting the resolved `datetime` (with an
  injected `now`) or `None`.
- **Unit — `resumer`:** state-machine transitions with an injected fake clock —
  no real sleeping. Covers cap enforcement and the poll-retry fallback.
- **Integration — `pty_wrapper`:** a **fake child script** that prints a
  simulated limit banner, then reads stdin expecting `continue`, then prints
  `resumed`. Run under the real wrapper; assert the injection reaches the child.

## Project layout

```
autoresume/
  autoresume/
    __init__.py
    __main__.py
    cli.py
    detector.py
    resumer.py
    pty_wrapper.py
  tests/
    test_detector.py
    test_resumer.py
    test_pty_integration.py
  docs/superpowers/specs/2026-07-26-autoresume-design.md
  README.md
  pyproject.toml
```
