import sys
import re
import argparse

from commands.log import Log

from exceptions import VCSException

class CommandSet:
    """
    Manage argument declaration and parsing, and instantiation of
    command classes.

    Acts like a dynamic collection of command singletons and CLI manager.

    Allow all command classes to register their argument declarations,
    but only create instances of command classes at the point they
    are requested and cache those instances once created. When
    registering a command, pass the instance of this class doing the
    registering to the command, so it can use other commands without
    importing them.
    """

    def __init__(self, config):
        self._cmds = {}
        self._config = config
        self._arg_parser = argparse.ArgumentParser()
        self._arg_subparsers = self._arg_parser.add_subparsers(dest="command")

    def register(self, *commands):
        for command in commands:
            name = self._camel_to_kebab(command.__name__)
            self._log(
                f"Registering command '{name}' ({command}) with {self}",
                level=3
            )

            self._cmds[name] = None
            command_arg_parser = self._arg_subparsers.add_parser(name)
            command.setup_args(command_arg_parser)

            # Dynamically add a method to this object that can instantiate
            # and retreive the command instance.
            # Set kwargs to force it to early-bind those values
            def command_getter(name=name, command=command, logger=None):
                if self._cmds[name] == None:
                    log_fn = self._log if logger is None else logger.log

                    try:
                        log_fn(
                            f"Instantiating command '{name}'",
                            level=4
                        )
                        self._cmds[name] = command(self, self._config)
                    except RecursionError:
                        log_fn(
                            f"Recursion error: Probable infinite recursion in command '{name}'",
                            error=True
                        )
                        exit()
                return self._cmds[name]

            self.__dict__[name] = command_getter

    def is_registered(self, name):
        return name in self._cmds

    def get_command(self, name):
        """Return the instance of the command with the given name."""

        try:
            return self.__dict__[name]()
        except TypeError as e: # NoneType object is not callable
            raise VCSException(f"Sub-command not registered: '{name}'") from e

    def run_command(self, name, args):
        """Run the command with the given name with the given arguments."""

        self.get_command(name)(args)

    def run_cli(self):
        """Parse CLI arguments and run the command they specify."""

        args = self._arg_parser.parse_args()
        self.run_command(args.command, args)

    def _log(self, *args, error=False, level=0):
        """
        Try logging the given message using the registered logger command.

        If no logger command has been registered yet, then use a basic logger.
        """

        if not hasattr(self, '_fallback_log_command'):
            self._fallback_log_command = Log(self, self._config)

        # Avoid infinite recursion
        if self.is_registered('log'):
            logger = self.log(logger=self._fallback_log_command)
        else:
            logger = self._fallback_log_command

        logger.log(*args, error=error, level=level)

    # Derived from: https://stackoverflow.com/a/1176023/16967315
    def _camel_to_kebab(self, name):
        name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', name).lower()
