import os.path
import sys

# Types
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace

class LogModule:
    LEVELS = [
        'ERROR',
        'WARNING',
        'INFO',
        'DEBUG',
        'TRACE'
    ]

    # Lifecycle
    # --------------------

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('OUTPUT_FILE', default_is_none=True)
        parser.add_variable('ERROR_FILE', default_is_none=True)
        parser.add_variable('VERBOSITY', type=int, default=0)

    def configure_args(self, *,
            parser: ArgumentParser,
            root_parser: ArgumentParser,
            **_
    ):
        # Root
        root_parser.add_argument('--log-output-file', default=None,
            help="Set the file to output log messages to")
        root_parser.add_argument('--log-error-file', default=None,
            help="Set the file to output error messages to")

        root_parser.add_argument('-v', '--log-verbose',
            action='count', default=None,
            help="Can be given up to 4 times to increase the log level")

        # Log - Options
        parser.add_argument('-e', '--error', action='store_true', default=False,
            help='Send the log message to the error log')
        parser.add_argument('-l', '--level', type=int, default=0,
            help="""
            Only output the log message if the current logging level is at
            or above the given level
            """)

        # Log - Arguments
        parser.add_argument('message', help='The message to log')

    def configure(self, *, env: Namespace = None, args: Namespace = None, **_):
        # Verbosity
        self._verbosity = env.VCS_LOG_VERBOSITY
        if 'log_verbose' in args and args.log_verbose is not None:
            self._verbosity = args.log_verbose

        # Output file
        self._output_file_path = env.VCS_LOG_OUTPUT_FILE
        if 'log_output_file' in args and args.log_output_file is not None:
            self._output_file_path = args.log_output_file

        # Error file
        self._error_file_path = env.VCS_LOG_ERROR_FILE
        if 'log_error_file' in args and args.log_error_file is not None:
            self._error_file_path = args.log_error_file

    def start(self, *_, **__):
        # TODO: rotate log + clean up old logs

        self._output_file = sys.stdout
        if self._output_file_path is not None:
            self._output_file = open(self._output_file_path, 'w')

        self._error_file = sys.stderr
        if self._error_file_path is not None:
            self._error_file = open(self._error_file_path, 'w')

        # Say which module instance has been started
        self.debug(f'Started LogModule {self}')

    def __call__(self, *, args: Namespace, **_):
        self.log(args.message, error=args.error, level=args.level)

    def stop(self, *_, **__):
        # Say which module instance has been stopped
        self.debug(f'Stopping LogModule {self}')

        if self._output_file_path is not None:
            self._output_file.close()

        if self._error_file_path is not None:
            self._error_file.close()

    # Invokation
    # --------------------

    def log(self, *objs, error=False, level=0):
        file = self._output_file
        if error:
            file = self._error_file

        if self._verbosity >= level:
            try:
                level_text = LogModule.LEVELS[level]
            except IndexError:
                level_text = LogModule.LEVELS[-1]
            print(level_text+':', *objs, file=file)

    def error(self, *objs):
        self.log(*objs, error=True, level=0)

    def warning(self, *objs):
        self.log(*objs, error=True, level=1)

    def info(self, *objs):
        self.log(*objs, level=2)

    def debug(self, *objs):
        self.log(*objs, level=3)

    def trace(self, *objs):
        self.log(*objs, level=4)
