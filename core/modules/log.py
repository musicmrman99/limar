from core.modulemanager import ModuleAccessor
from core.exceptions import VCSException

# Types
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace

class LogModule:
    LEVELS_ORDERED = [
        'ERROR',
        'WARNING',
        'INFO',
        'DEBUG',
        'TRACE'
    ]
    LEVELS = Namespace(**{name: name for name in LEVELS_ORDERED})

    LOG_CONSOLE = 'log'

    # Lifecycle
    # --------------------

    # NOTE: As a core module, this module follows the core module lifecycle,
    #       which 'wraps around' the main module lifecycle.

    def dependencies(self):
        return ['console']

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

    def configure(self, *,
            mod: Namespace,
            env: Namespace,
            args: Namespace,
            **_
    ):
        # For methods that aren't given it directly
        self._mod = mod

        # Output console
        output_file_path = env.FILE
        if 'log_file' in args and args.log_file is not None:
            output_file_path = args.log_file

        self._out_console_name = 'out'
        if output_file_path is not None:
            mod.console.add_console(self.LOG_CONSOLE, output_file_path)
            self._out_console_name = self.LOG_CONSOLE

        # Verbosity
        self._verbosity = env.VERBOSITY
        if 'log_verbose' in args and args.log_verbose is not None:
            self._verbosity = args.log_verbose

    # TODO: rotate log + clean up old logs

    # Invokation
    # --------------------

    @ModuleAccessor.invokable_as_service
    def log(self, *objs, error=False, level=LEVELS.INFO):
        if level not in self.LEVELS_ORDERED:
            raise VCSException(
                f"Log level '{level}' not recognised. Should be a level from"
                " LogModule.LEVELS"
            )

        if self._verbosity >= self.LEVELS_ORDERED.index(level):
            console_name = self._out_console_name if not error else 'err'
            self._mod.console.get(console_name).print(level+':', *objs)

    @ModuleAccessor.invokable_as_service
    def error(self, *objs):
        self.log(*objs, error=True, level=self.LEVELS.ERROR)

    @ModuleAccessor.invokable_as_service
    def warning(self, *objs):
        self.log(*objs, error=True, level=self.LEVELS.WARNING)

    @ModuleAccessor.invokable_as_service
    def info(self, *objs):
        self.log(*objs, level=self.LEVELS.INFO)

    @ModuleAccessor.invokable_as_service
    def debug(self, *objs):
        self.log(*objs, level=self.LEVELS.DEBUG)

    @ModuleAccessor.invokable_as_service
    def trace(self, *objs):
        self.log(*objs, level=self.LEVELS.TRACE)
