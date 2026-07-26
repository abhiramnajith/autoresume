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
