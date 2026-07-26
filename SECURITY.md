# Security Policy

## Supported versions

`autoresume` is a small, single-purpose tool. Security fixes are applied to the
latest `main` only.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report privately through GitHub's
[private vulnerability reporting](https://github.com/abhiramnajith/autoresume/security/advisories/new)
(the repo's **Security → Report a vulnerability**). You'll get an acknowledgement
within a few days, and we'll coordinate a fix and disclosure.

## Scope notes

`autoresume` wraps an interactive `claude` session in a pseudo-terminal and
injects the literal text `continue` after a usage-limit reset. It makes no
network calls, handles no credentials, and has no third-party runtime
dependencies. The trust boundary is the terminal I/O it forwards between your
shell and the wrapped child process — treat the output it parses (the child's
rendered text) as untrusted, which the detector already does (it only matches a
fixed banner pattern and never executes anything from that text).
