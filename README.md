# autoresume

[![CI](https://github.com/abhiramnajith/autoresume/actions/workflows/ci.yml/badge.svg)](https://github.com/abhiramnajith/autoresume/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)

Auto-resume an unattended interactive Claude Code session after a usage-limit
reset. Wrap your normal command:

    autoresume -- claude

When Claude prints a usage-limit banner ("… limit reached ∙ resets 3pm"),
`autoresume` parses the reset time, waits, and sends `continue` so the session
picks up where it left off. It stops after `--max-resumes` (default 5) to avoid
waiting forever on a weekly limit.

![autoresume demo](demo/autoresume.gif)

> The demo above uses a scripted stand-in for `claude` (`demo/bin/claude`) and a
> short `--reset-buffer` so the wait is watchable — no real usage limit needed.
> Regenerate it from the repo root with [`vhs`](https://github.com/charmbracelet/vhs):
> `vhs demo/autoresume.tape`.

## Requirements

- **Python 3.8+** — standard library only, no third-party dependencies.
- **macOS or Linux** — uses a pseudo-terminal (CI runs on both).

## Install

### Recommended: isolated install on your PATH

Give the tool its own virtual environment and symlink its entry point onto your
`PATH` (this is what `pipx` does, done by hand — no extra tooling needed):

```sh
# 1. get the code
git clone https://github.com/abhiramnajith/autoresume.git
cd autoresume

# 2. isolated venv + install
python3 -m venv ~/.local/share/autoresume/venv
~/.local/share/autoresume/venv/bin/pip install .

# 3. put it on your PATH
mkdir -p ~/.local/bin
ln -sf ~/.local/share/autoresume/venv/bin/autoresume ~/.local/bin/autoresume

# 4. verify
autoresume --help
```

If `~/.local/bin` isn't already on your `PATH`, add this to your shell profile
(`~/.zshrc` / `~/.bashrc`):

```sh
export PATH="$HOME/.local/bin:$PATH"
```

### With pipx

```sh
pipx install git+https://github.com/abhiramnajith/autoresume.git
```

### Run without installing

```sh
git clone https://github.com/abhiramnajith/autoresume.git
cd autoresume
python3 -m autoresume -- claude
```

## Usage

    autoresume [options] -- <command...>

Options:

- `--max-resumes N`      stop after N auto-resumes (default 5)
- `--poll-window H`      hours to keep retrying when the reset time can't be
                         parsed (default 5)
- `--max-polls N`        retries spread evenly across `--poll-window`
                         (default 10, i.e. every 30 minutes for 5 hours)
- `--reset-buffer S`     seconds to wait past the parsed reset time (default 45)
- `--resume-message MSG` text sent to resume (default `continue`)
- `--log-file PATH`      event log (default `~/.autoresume/autoresume.log`)

## Maintenance

**Update** to the latest version:

```sh
# recommended install
cd autoresume && git pull
~/.local/share/autoresume/venv/bin/pip install --force-reinstall .

# pipx
pipx install --force git+https://github.com/abhiramnajith/autoresume.git
```

**Uninstall:**

```sh
# recommended install
rm -rf ~/.local/share/autoresume ~/.local/bin/autoresume

# pipx
pipx uninstall autoresume
```

The event log lives at `~/.autoresume/autoresume.log` (override with
`--log-file`); delete it any time.

## How it works

`autoresume` spawns the command inside a pseudo-terminal and forwards your
keyboard and its screen transparently. In the background it strips ANSI from the
output, watches for the limit banner, and injects the resume message at the
reset time. Everything is Python standard library — no dependencies.

Two kinds of waits, with separate budgets:

- **Reset time known** — sleeps until that time (plus `--reset-buffer`) and
  spends one of `--max-resumes`.
- **Reset time unknown** — retries blind every `--poll-window / --max-polls`
  (30 minutes by default) and spends one *poll*, never a resume. After
  `--max-polls` tries without a reset it leaves the session idle. A long
  productive stretch between limits starts a fresh poll budget.

## Development

    pip install -e '.[dev]'
    python -m pytest -v

## Scope

Interactive sessions only (not `claude -p` / SDK runs). It does not change your
usage limits — it only removes the babysitting.
