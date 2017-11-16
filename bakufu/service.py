from tornado import gen

from bakufu import logger
from bakufu.process import Process


class Service:
    def __init__(self, name, command,
                 num_processes=1, stop_signal="SIGTERM",
                 **options):
        self.name = name
        self.command = command
        self.num_processes = num_processes
        self.stop_signal = stop_signal
        self._options = options

        self.processes = {}
        self.use_sockets = False

    def start(self):
        for _ in range(self.num_processes):
            self.spawn_process()
        logger.info("%s started" % self.name)

    def spawn_process(self):
        process = Process(
            self.command,
            stop_signal=self.stop_signal,
        )
        process.spawn()
        self.processes[process.pid] = process
        return process

    @gen.coroutine
    def stop(self):
        logger.info("stopping %s service" % self.name)
        for process in self.processes.values():
            process.kill()

        reaping = []
        for pid in list(self.processes):
            process = self.processes.pop(pid)
            reaping.append(process.reap())
        yield reaping

    def watch_processes(self):
        dead_processes = []
        for process in self.processes.values():
            if not process.watch():
                logger.error("%s process is dead: pid=%s" % (self.name, process.pid))
                dead_processes.append(process)

        for process in dead_processes:
            process.spawn()
            logger.info("respawn %s process: pid=%s" % (self.name, process.pid))