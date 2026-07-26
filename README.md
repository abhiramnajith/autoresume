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
