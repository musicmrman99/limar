from rich.console import Console

from core.modulemanager import ModuleAccessor
from core.exceptions import VCSException

# Types
from argparse import ArgumentParser, Namespace

class ConsoleModule:
    # Lifecycle
    # --------------------

    # NOTE: As a core module, this module follows the core module lifecycle,
    #       which 'wraps around' the main module lifecycle.

    def __init__(self):
        self._file_handles = {}
        self._consoles = {}

        self._open_console('out')
        self._open_console('err', stderr=True)

    def configure_root_args(self, *, parser: ArgumentParser, **_):
        parser.add_argument('--out', default=None,
            help="Redirect stdout to the given file")

        parser.add_argument('--err', default=None,
            help="Redirect stderr to the given file")

    def start(self, *, args: Namespace, **_):
        if 'out' in args and args.out is not None:
            self._open_console('out', path=args.out)

        if 'err' in args and args.err is not None:
            self._open_console('err', path=args.err)

    def stop(self, *_, **__):
        for name in tuple(self._consoles):
            self._close_console(name)

    # Configuration
    # --------------------

    @ModuleAccessor.invokable_as_config
    def add_console(self, name, path):
        """
        Allows adding new consoles of specific target files.
        """

        if name in self._consoles:
            raise VCSException(
                f"Attempt to register already-registered console '{name}' for"
                f" output to file '{path}'"
            )

        self._open_console(name, path=path)

    # Invokation
    # --------------------

    @ModuleAccessor.invokable_as_service
    def print(self, *objs):
        self._consoles['out'].print(*objs)

    @ModuleAccessor.invokable_as_service
    def error(self, *objs):
        self._consoles['err'].print(*objs)

    @ModuleAccessor.invokable_as_service
    def get(self, name):
        return self._consoles[name]

    # Utils
    # --------------------

    def _open_console(self, name, *, stderr=False, path=None):
        self._close_console(name)
        if path is not None:
            self._file_handles[name] = open(path, 'wt')
            self._consoles[name] = Console(file=self._file_handles[name])
        else:
            self._consoles[name] = Console(stderr=stderr)

    def _close_console(self, name):
        if name in self._consoles:
            del self._consoles[name]

        if name in self._file_handles:
            self._file_handles[name].close()
            del self._file_handles[name]
