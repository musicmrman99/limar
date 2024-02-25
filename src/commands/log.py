import sys
from argparse import ArgumentParser, Namespace

from environment import Environment

class Log:
    LEVELS = [
        'ERROR',
        'WARNING',
        'INFO',
        'DEBUG',
        'TRACE'
    ]

    @staticmethod
    def setup_args(parser: ArgumentParser, root_parser: ArgumentParser = None):
        # Root parser
        root_parser.add_argument('-v', '--log-verbose',
            action='count', default=0,
            help="Can be given up to 4 times to increase the log level")

        # Arguments
        parser.add_argument('message', help='The message to log')

        # Options
        parser.add_argument('-e', '--error', action='store_true', default=False,
            help='Send the log message to the error log')
        parser.add_argument('-l', '--level', type=int, default=0,
            help="""
            Only output the log message if the current logging level is at
            or above the given level
            """)

    def __init__(self,
            cmd = None, # CommandSet, but not given to avoid circular import
            env: Environment = None,
            args: Namespace = None
    ):
        self._verbosity = 0
        if env is not None:
            self._verbosity = int(env.get('log.verbosity'))
        if args is not None and 'log_verbose' in args:
            self._verbosity = args.log_verbose

    def __call__(self, args):
        self.log(args.message, error=args.error, level=args.level)

    def log(self, *objs, error=False, level=0):
        file = sys.stdout
        if error:
            file = sys.stderr

        if self._verbosity >= level:
            try:
                level_text = Log.LEVELS[level]
            except IndexError:
                level_text = Log.LEVELS[-1]
            print(level_text+':', *objs, file=file)
