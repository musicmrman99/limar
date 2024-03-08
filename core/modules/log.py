import sys

# Types
from core.environment import Environment
from argparse import ArgumentParser, Namespace

class Log:
    LEVELS = [
        'ERROR',
        'WARNING',
        'INFO',
        'DEBUG',
        'TRACE'
    ]

    # Lifecycle
    # --------------------

    def configure_args(self, *,
            parser: ArgumentParser,
            root_parser: ArgumentParser,
            **_
    ):
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

    def configure(self, *,
            env: Environment = None,
            args: Namespace = None,
            **_
    ):
        self._verbosity = 0
        if env is not None:
            self._verbosity = int(env.get('log.verbosity'))
        if args is not None and 'log_verbose' in args:
            self._verbosity = int(args.log_verbose)

    def __call__(self, args: Namespace):
        self.log(args.message, error=args.error, level=args.level)

    # Actions
    # --------------------

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

    def error(self, *objs):
        self.log(*objs, error=True, level=0)

    def warn(self, *objs):
        self.log(*objs, error=True, level=1)

    def info(self, *objs):
        self.log(*objs, level=2)

    def debug(self, *objs):
        self.log(*objs, level=3)

    def trace(self, *objs):
        self.log(*objs, level=4)
