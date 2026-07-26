"""A scripted stand-in for `claude`, used ONLY to record the demo GIF.

It mimics a Claude Code session that hits a usage limit, so the recording can
show autoresume detecting the banner, waiting, and resuming — without needing
to actually exhaust a real usage limit. It prints a limit banner, then blocks
reading stdin until autoresume injects the resume message.
"""
import sys
import time


def out(text, pause=0.0):
    sys.stdout.write(text)
    sys.stdout.flush()
    if pause:
        time.sleep(pause)


out("\x1b[38;5;208m✻\x1b[0m Welcome to \x1b[1mClaude Code\x1b[0m\r\n\r\n", 0.7)
out("\x1b[2m> refactor the auth module and add tests\x1b[0m\r\n", 0.9)
out("\x1b[2m⋯ working…\x1b[0m\r\n", 1.0)
out("\x1b[32m✓\x1b[0m updated \x1b[1msrc/auth.py\x1b[0m\r\n", 0.8)

# Simulated usage-limit banner.
out("\r\n\x1b[1m\x1b[38;5;208m✳ Claude usage limit reached\x1b[0m ∙ resets in 0 minutes\r\n", 0.3)

# Block until autoresume injects the resume message.
line = sys.stdin.readline()
if "continue" in line:
    out("\x1b[2m⋯ resuming…\x1b[0m\r\n", 0.9)
    out("\x1b[32m✓\x1b[0m added \x1b[1mtests/test_auth.py\x1b[0m — 6 passing\r\n", 0.7)
    out("\x1b[1m\x1b[32m✓ done\x1b[0m\r\n", 0.4)

time.sleep(0.6)
