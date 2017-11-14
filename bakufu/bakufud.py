import argparse
import logging
import signal
import sys
from tornado import gen
from tornado.ioloop import IOLoop

from bakufu import __version__, logger
from bakufu import config
from bakufu.service import Service


LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG
}


SIGNALS = ["SIG%s" % name for name in "HUP QUIT INT TERM CHLD".split()]
SIGNAMES = {getattr(signal, name): name for name in SIGNALS}


class Bakufu:
    def __init__(self, services, ioloop):
        self.services = services

        self.ioloop = ioloop
        self.init_signal_handler()

    def init_signal_handler(self):
        for signame in SIGNALS:
            signal.signal(getattr(signal, signame), self.signal)

    def start(self):
        for service in self.services:
            service.start()
        self.ioloop.start()

    def signal(self, signalnum, frame):
        self.ioloop.add_callback_from_signal(self.handle_signal, SIGNAMES[signalnum])

    def handle_signal(self, signame):
        logger.warning("received %s" % signame)
        if signame in ("SIGTERM", "SIGINT", "SIGQUIT"):
            self.quit()
        if signame == "SIGHUP":
            self.reload()
        if signame == "SIGCHLD":
            pass

    def quit(self):
        self.ioloop.add_callback(self._quit)

    @gen.coroutine
    def _quit(self):
        for service in self.services:
            yield service.stop()
        self.ioloop.stop()

    def reload(self):
        raise NotImplementedError

    @classmethod
    def load_from_config(cls, filename, ioloop):
        with open(filename) as fp:
            cfg = config.load(fp)

        services = []
        for name, opts in cfg['service'].items():
            service = Service(name, **opts)
            services.append(service)

        return cls(
            services=services,
            ioloop=ioloop
        )


def main():
    parser = argparse.ArgumentParser(description='Run Bakufu.')
    parser.add_argument('config', help='configuration file', nargs='?')
    parser.add_argument('--version', action='store_true', default=False,
                        help='print Bakufu version.')
    parser.add_argument('--loglevel', dest='loglevel', default="warning",
                        choices=LOG_LEVELS.keys(),
                        help='log level')
    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    if args.config is None:
        parser.print_usage()
        sys.exit(0)

    loglevel = args.loglevel
    logger.setLevel(LOG_LEVELS[loglevel])

    ioloop = IOLoop.current()
    bakufu = Bakufu.load_from_config(args.config, ioloop)
    bakufu.start()


if __name__ == "__main__":
    main()
