from __future__ import annotations

import os
import pty
import select
import signal
import subprocess
import sys
from collections.abc import Callable, Sequence

from triage.ports.process_runner import ProcessRunner

OnBytes = Callable[[bytes], None]


class PtyProcessRunner(ProcessRunner):
    def __init__(self) -> None:
        self._pids: set[int] = set()

    def spawn(self, argv: Sequence[str], cwd: str | None = None) -> int:
        proc = subprocess.Popen(
            list(argv),
            cwd=cwd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._pids.add(proc.pid)
        return proc.pid

    def is_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            self._pids.discard(pid)
            return False

    def terminate(self, pid: int) -> None:
        if pid <= 0:
            return
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                self._pids.discard(pid)
                return
        self._pids.discard(pid)

    def terminate_all(self) -> None:
        for pid in list(self._pids):
            self.terminate(pid)


def run_pty(
    argv: Sequence[str],
    on_bytes: OnBytes | None = None,
    cwd: str | None = None,
    on_pid: Callable[[int], None] | None = None,
) -> int:
    """Foreground PTY wrap. Echoes to this terminal; on_bytes sees raw output."""
    pid, fd = pty.fork()
    if pid == 0:
        if cwd:
            os.chdir(cwd)
        os.execvp(argv[0], list(argv))
        os._exit(127)
    if on_pid:
        on_pid(pid)

    def _forward(signum, _frame) -> None:
        try:
            os.kill(pid, signum)
        except OSError:
            pass

    prev_int = signal.signal(signal.SIGINT, _forward)
    prev_term = signal.signal(signal.SIGTERM, _forward)
    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if fd in ready:
                try:
                    chunk = os.read(fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                try:
                    os.write(sys.stdout.fileno(), chunk)
                except OSError:
                    pass
                if on_bytes:
                    on_bytes(chunk)
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited:
                return _exit_code(status)

        _, status = os.waitpid(pid, 0)
        return _exit_code(status)
    finally:
        signal.signal(signal.SIGINT, prev_int)
        signal.signal(signal.SIGTERM, prev_term)


def _exit_code(status: int) -> int:
    if hasattr(os, "waitstatus_to_exitcode"):
        return os.waitstatus_to_exitcode(status)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return 1
