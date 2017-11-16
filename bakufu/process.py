import sys
import errno
import os
import psutil
import signal
import time
from enum import Enum
from subprocess import PIPE
from tornado import gen

from bakufu import logger


class ProcessStatus(Enum):
    stopped = "stopped"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    backoff = "backoff"
    fatal = "fatal"


class Process:
    def __init__(self, command, use_sockets=False, stop_signal="SIGTERM", max_retry=5):
        self.command = command
        self.use_sockets = use_sockets
        self.stop_signal = stop_signal
        self.max_retry = max_retry

        self.status = ProcessStatus.stopped
        self.worker = None
        self.backoff = 0
        self.laststart = 0
        self.laststop = 0

    @property
    def pid(self):
        if self.worker is None:
            return None
        return self.worker.pid

    def spawn(self):
        if self.status == ProcessStatus.running:
            return
        if self.status == ProcessStatus.fatal:
            return

        if self.status != ProcessStatus.backoff:
            self.status = ProcessStatus.starting
        try:
            self.worker = psutil.Popen(
                self.command,
                shell=True,
                # stdout=PIPE,
                # stderr=PIPE,
                stdout=sys.stdout,
                stderr=sys.stderr,
                close_fds=not self.use_sockets,
            )
            self.status = ProcessStatus.running
            self.laststart = time.time()
        except OSError as e:
            self.status = ProcessStatus.backoff
            self.backoff += 1

        if self.backoff >= self.max_retry:
            # give up retrying
            self.status = ProcessStatus.fatal

    def kill(self):
        if self.status == ProcessStatus.stopped:
            return

        self.status = ProcessStatus.stopping
        if self.worker:
            self.worker.send_signal(getattr(signal, self.stop_signal))

    @gen.coroutine
    def reap(self):
        if self.worker is None:
            return

        while True:
            try:
                pid, _ = os.waitpid(self.pid, os.WNOHANG)
                if pid != self.pid:
                    # the child process is still alive
                    yield gen.sleep(0.001)
                    continue
                else:
                    break
            except OSError as e:
                if e.errno == errno.EINTR:
                    # waitpid was interuppted
                    continue
                elif e.errno == errno.ECHILD:
                    # the child has gone
                    break
                else:
                    raise e

        # TODO: get exit code
        self.status = ProcessStatus.stopped
        self.worker = None
        self.backoff = 0
        self.laststop = time.time()

    def is_active(self):
        try:
            if self.worker.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                return False
        except psutil.NoSuchProcess:
            return False

        return self.worker.is_running()

    def watch(self):
        if self.status != ProcessStatus.running:
            return True
        if self.is_active():
            return True

        self.laststop = time.time()
        try:
            if self.worker.is_running():
                self.worker.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        delay = self.laststop - self.laststart
        if delay < 3:
            logger.error("process exited too quickly: pid=%s" % self.pid)
            self.status = ProcessStatus.backoff
            self.backoff += 1
        else:
            self.status = ProcessStatus.stopped
        return False

