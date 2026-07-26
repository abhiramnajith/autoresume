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
