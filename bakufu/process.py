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
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    BACKOFF = "backoff"
    FATAL = "fatal"


class Process:
    def __init__(self, command, use_sockets=False, stop_signal="SIGTERM", max_retry=5):
        self.command = command
        self.use_sockets = use_sockets
        self.stop_signal = stop_signal
        self.max_retry = max_retry

        self.status = ProcessStatus.STOPPED
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
        if self.status in (ProcessStatus.RUNNING, ProcessStatus.FATAL):
            return

        if self.status != ProcessStatus.BACKOFF:
            self.status = ProcessStatus.STARTING

        while self.backoff <= self.max_retry:
            worker = None
            try:
                worker = psutil.Popen(
                    self.command,
                    shell=True,
                    # stdout=PIPE,
                    # stderr=PIPE,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    close_fds=not self.use_sockets,
                )
            except OSError as e:
                self.status = ProcessStatus.BACKOFF
                self.backoff += 1

            if worker is not None:
                self.worker = worker
                self.status = ProcessStatus.RUNNING
                self.laststart = time.time()
                return
        # give up retrying
        self.status = ProcessStatus.FATAL

    def kill(self):
        if self.status == ProcessStatus.STOPPED:
            return

        self.status = ProcessStatus.STOPPING
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
        self.status = ProcessStatus.STOPPED
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
        if self.status != ProcessStatus.RUNNING:
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
            self.status = ProcessStatus.BACKOFF
            self.backoff += 1
        else:
            self.status = ProcessStatus.STOPPED
            self.backoff = 0
        return False

