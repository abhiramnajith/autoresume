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
