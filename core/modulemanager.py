import re
import argparse

from core.modules.log import Log

from core.exceptions import VCSException

class ModuleManager:
    """
    Manage the module lifecycle, including argument declaration and parsing.

    Acts like a dynamic collection of module singletons and a command
    line manager.

    Allow registration of module classes. Registration adds them to the
    module pool and also allows those classes to register their argument
    declarations on a passed subparser. The root parser is also passed in
    the keyword argument 'root_parser' so that module classes can register
    global options that affect their behaviour when called indirectly by
    other modules.

    When a module in the pool is requested, if it doesn't yet have an
    instance it is __init__()-ialised, with this module set object and
    the global configuration passed as the first two arguments so that it
    can access any method on any other registered module object. Be
    careful when developing module classes to avoid infinite recursion
    when calling module methods.

    When a module is called from the CLI (by using run_command_line()), then
    it is __call__()-ed with the parsed command line arguments (as an
    argparse Namespace object) given as the first argument.
    """

    def __init__(self, env):
        self._mods = {}
        self._env = env
        self._args = None
        self._arg_parser = argparse.ArgumentParser(prog='vcs')
        self._arg_subparsers = self._arg_parser.add_subparsers(dest="module")

    # Registration
    # --------------------

    def register(self, *modules):
        for module in modules:
            name = self._camel_to_kebab(module.__name__)
            self._log(
                f"Registering module '{name}' ({module}) with {self}",
                level=3
            )

            self._mods[name] = None
            module_arg_parser = self._arg_subparsers.add_parser(name)
            module.setup_args(module_arg_parser, root_parser=self._arg_parser)

            # Dynamically add a method to this object that can instantiate
            # and retreive the module instance.
            def module_getter(
                    logger=None,

                    # Use kwargs to force it to early-bind
                    name=name, module=module
            ):
                if self._mods[name] == None:
                    try:
                        self._log(
                            f"Instantiating module '{name}'",
                            level=4
                        )
                        self._mods[name] = module(
                            mod=self,
                            env=self._env,
                            args=self._args
                        )
                    except RecursionError:
                        self._log(
                            f"Recursion error: Probable infinite recursion in module '{name}'",
                            error=True
                        )
                        exit()
                return self._mods[name]

            self.__dict__[name] = module_getter

    # Post-Registration
    # --------------------

    def is_registered(self, name):
        return name in self._mods

    def get_module(self, name):
        """Return the instance of the module with the given name."""

        if not self.is_registered(name):
            raise VCSException(f"Module not registered: '{name}'")

        return self.__dict__[name]()

    def run_module(self, name, args):
        """Run the module with the given name with the given arguments."""

        self.get_module(name)(args)

    # Actioning the Command Line
    # --------------------

    def run_command_line(self, *args):
        """
        Parse the command line and run the module it specifies.

        If args are given, then run those as a command line instead.
        """

        if len(args) > 0:
            self._args = self._arg_parser.parse_args(args)
        else:
            self._args = self._arg_parser.parse_args()

        self.run_module(self._args.module, self._args)

    # Utils
    # --------------------

    def _log(self, *args, error=False, level=0):
        """
        Use a basic logger to log the given message.

        This is required during the module registration phase, before
        command line arguments are available to the log module so it
        can configure itself.
        """

        if not hasattr(self, '_fallback_log_module'):
            self._fallback_log_module = Log(mod=self, env=self._env)
        self._fallback_log_module.log(*args, error=error, level=level)

    # Derived from: https://stackoverflow.com/a/1176023/16967315
    def _camel_to_kebab(self, name):
        name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', name).lower()
