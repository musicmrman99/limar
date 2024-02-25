import re
import argparse

from commands.log import Log

from exceptions import VCSException

class CommandSet:
    """
    Manage argument declaration and parsing, and instantiation of
    command classes.

    Acts like a dynamic collection of command singletons and a command
    line manager.

    Allow registration of command classes. Registration adds them to the
    command pool and also allows those classes to register their argument
    declarations on a passed subparser. The root parser is also passedin
    the keyword argument 'root_parser' so that command classes can register
    global options that affect their behaviour when called indirectly by
    other commands.

    When a command in the pool is requested, if it doesn't yet have an
    instance it is __init__()-ialised, with this command set object and
    the global configuration passed as the first two arguments so that it
    can access any method on any other registered command object. Be
    careful when constructing command classes to avoid infinite recursion
    when calling command methods.

    When a command is called from the CLI (by using run_cmd_line()), then
    it is __call__()-ed with the parsed command line arguments (as an
    argparse Namespace object) given as the first argument.
    """

    def __init__(self, env):
        self._cmds = {}
        self._env = env
        self._args = None
        self._arg_parser = argparse.ArgumentParser()
        self._arg_subparsers = self._arg_parser.add_subparsers(dest="command")

    # Registration
    # --------------------

    def register(self, *commands):
        for command in commands:
            name = self._camel_to_kebab(command.__name__)
            self._log(
                f"Registering command '{name}' ({command}) with {self}",
                level=3
            )

            self._cmds[name] = None
            command_arg_parser = self._arg_subparsers.add_parser(name)
            command.setup_args(command_arg_parser, root_parser=self._arg_parser)

            # Dynamically add a method to this object that can instantiate
            # and retreive the command instance.
            def command_getter(
                    logger=None,

                    # Use kwargs to force it to early-bind
                    name=name, command=command
            ):
                if self._cmds[name] == None:
                    try:
                        self._log(
                            f"Instantiating command '{name}'",
                            level=4
                        )
                        self._cmds[name] = command(self, self._env, self._args)
                    except RecursionError:
                        self._log(
                            f"Recursion error: Probable infinite recursion in command '{name}'",
                            error=True
                        )
                        exit()
                return self._cmds[name]

            self.__dict__[name] = command_getter

    # Post-Registration
    # --------------------

    def is_registered(self, name):
        return name in self._cmds

    def get_command(self, name):
        """Return the instance of the command with the given name."""

        if not self.is_registered(name):
            raise VCSException(f"Sub-command not registered: '{name}'")

        return self.__dict__[name]()

    def run_command(self, name, args):
        """Run the command with the given name with the given arguments."""

        self.get_command(name)(args)

    # Actioning the Command Line
    # --------------------

    def run_cmd_line(self, *args):
        """
        Parse the command line and run the command it specifies.

        If args are given, then run those as a command line instead.
        """

        if len(args) > 0:
            self._args = self._arg_parser.parse_args(args)
        else:
            self._args = self._arg_parser.parse_args()

        self.run_command(self._args.command, self._args)

    # Utils
    # --------------------

    def _log(self, *args, error=False, level=0):
        """
        Use a basic logger to log the given message.

        This is required during the command registration phase, before
        command line arguments are available to the log command so it
        can configure itself.
        """

        if not hasattr(self, '_fallback_log_command'):
            self._fallback_log_command = Log(self, self._env, None)
        self._fallback_log_command.log(*args, error=error, level=level)

    # Derived from: https://stackoverflow.com/a/1176023/16967315
    def _camel_to_kebab(self, name):
        name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', name).lower()
