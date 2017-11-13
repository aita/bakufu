import argparse
import sys

from bakufu import __version__


def main():
    parser = argparse.ArgumentParser(description='Run Bakufu.')
    parser.add_argument('config', help='configuration file', nargs='?')
    parser.add_argument('--version', action='store_true', default=False,
                        help='print Bakufu version.')
    args = parser.parse_args()

    if args.version:
        print(__version__)
        sys.exit(0)

    if args.config is None:
        parser.print_usage()
        sys.exit(0)


if __name__ == "__main__":
    main()
