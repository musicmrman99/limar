import sys
import argparse

class Log:
    LEVELS = [
        'ERROR',
        'WARNING',
        'INFO',
        'TRACE',
        'DEBUG'
    ]

    @staticmethod
    def setup_args(parser: argparse.ArgumentParser):
        parser.add_argument('message', help='The message to log')

        parser.add_argument('-e', '--error', action='store_true', default=False,
            help='Send the log message to the error log')
        parser.add_argument('-l', '--level', type=int, default=0,
            help='Only output the log message if the current logging level is at or above the given level')

    def __init__(self, _=None, config=None) -> None:
        self.verbosity = 0
        if config is not None:
            self.verbosity = int(config.log_verbosity)

    def __call__(self, args):
        self.log(args.message, error=args.error, level=args.level)

    def log(self, *objs, error=False, level=0):
        file = sys.stdout
        if error:
            file = sys.stderr

        if self.verbosity >= level:
            try:
                level_text = Log.LEVELS[level]
            except IndexError:
                level_text = Log.LEVELS[-1]
            print(level_text+':', *objs, file=file)
