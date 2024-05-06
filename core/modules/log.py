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

    # NOTE: As a core module, this module's lifecycle is not the normal MM
    #       module lifecycle. It uses the same method names, but its lifecycle
    #       is managed by ModuleManager directly.

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('FILE', default_is_none=True)
        parser.add_variable('VERBOSITY', type=int, default=0)

    def configure_root_args(self, *, parser: ArgumentParser, **_):
        parser.add_argument('--log-file', default=None,
            help="""
            Set the file to output non-error log messages to. Errors always go
            to stderr.
            """)

        parser.add_argument('-v', '--log-verbose',
            action='count', default=None,
            help="Can be given up to 4 times to increase the log level")

    def configure(self, *, env: Namespace, args: Namespace, **_):
        # Output file
        self._output_file_path = env.VCS_LOG_FILE
        if 'log_output_file' in args and args.log_file is not None:
            self._output_file_path = args.log_file

        # Verbosity
        self._verbosity = env.VCS_LOG_VERBOSITY
        if 'log_verbose' in args and args.log_verbose is not None:
            self._verbosity = args.log_verbose

    def start(self, *_, **__):
        # TODO: rotate log + clean up old logs

        self._output_file = sys.stdout
        if self._output_file_path is not None:
            self._output_file = open(self._output_file_path, 'wt')

        # Say which module instance has been started
        self.debug(f'Started LogModule {self}')

    def stop(self, *_, **__):
        # Say which module instance has been stopped
        self.debug(f'Stopping LogModule {self}')

        if self._output_file_path is not None:
            self._output_file.close()

    # Invokation
    # --------------------

    def log(self, *objs, error=False, level=0):
        file = self._output_file if not error else sys.stderr
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
