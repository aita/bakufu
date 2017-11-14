import errno
import os
import signal
import sys
from enum import Enum
from subprocess import Popen, PIPE
from tornado import gen

from bakufu import logger


class ProcessState(Enum):
    stopped = "stopped"
    starting = "starting"
    running = "running"
    stopping = "stopping"


class Service:
    def __init__(self, name, command, num_processes=1, stop_signal="SIGTERM", **options):
        self.name = name
        self.command = command
        self.num_processes = num_processes
        self.stop_signal = stop_signal
        self._options = options

        self.processes = {}
        self.status = ProcessState.stopped
        self.use_sockets = False

    @gen.coroutine
    def start(self):
        self.status = ProcessState.starting
        for _ in range(self.num_processes):
            self.spawn_process()
        self.status = ProcessState.running
        logger.info("%s started" % self.name)

    def spawn_process(self):
        process = Popen(
            self.command,
            shell=True,
            # stdout=PIPE,
            # stderr=PIPE,
            stdout=sys.stdout,
            stderr=sys.stderr,
            close_fds=not self.use_sockets,
        )
        self.processes[process.pid] = process

    @gen.coroutine
    def stop(self):
        if self.status == ProcessState.stopped:
            return

        logger.info("stopping the %s service" % self.name)
        self.status.status = ProcessState.stopping
        for process in self.processes.values():
            process.send_signal(getattr(signal, self.stop_signal))

        yield self.reap_processes()
        logger.info("all %s processes stopped" % self.name)

    @gen.coroutine
    def reap_processes(self):
        for pid in list(self.processes):
            yield self.reap_process(pid)

    @gen.coroutine
    def reap_process(self, pid):
        process = self.processes.pop(pid)
        while True:
            try:
                pid_, _ = os.waitpid(pid, os.WNOHANG)
                if pid_ != pid:
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

        if process.poll() is None:
            logger.warn("process[pid=%d] is still alive" % pid)
            process.terminate()
        logger.info("process[pid=%d] exited with code %d" % (pid, process.returncode))
