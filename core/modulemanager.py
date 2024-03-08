from os.path import dirname, basename, isfile, join
import glob
import re
from argparse import ArgumentParser, Namespace
import importlib

from core.environment import Environment
from core.modules.log import Log
from core.exceptions import VCSException

class ModuleManager:
    """
    Manages the lifecycle of a set of modules of some application.

    ## Basic Usage
    
    Create a ModuleManager, register the modules you wish to use using
    `register()` or `register_package()`, then `run()` the manager's lifecycle,
    like so:

    ```py
    from core.environment import Environment
    from core.modulemanager import ModuleManager

    import modules
    from commands import CustomCommand

    env = Environment()
    mod_manager = ModuleManager('my-app', env)
    mod_manager.register_package(modules)
    mod_manager.register(CustomCommand)
    mod_manager.run()
    ```

    And use on the command line like:
    ```sh
    my-app custom-command --an-option optval argument
    ```

    ## Modules and the Module Lifecycle

    A module is a factory function for an object that can be 'invoked'
    (retrieved so that it can be called or used in some other way), either by
    the ModuleManager itself, or by another module.

    The lifecycle of a module consists of the following phases:

    - Registration (no hook):
      Adds the module to the list of modules this ModuleManager knows about.
      Note: Any attempt to register a module after the registration phase will
            raise a VCSException.

    - Initialisation (`__init__()`):
      Uses the module's factory callable (a class or a function) to create the
      module object for that module. Initialisation here should be kept to a
      minimum, with the majority of initialisation done in the Starting phase.

    - Argument Configuration (`configure_args(env, parser, root_parser)`):
      Passes the module a command-line parser just for it, as well as the root
      parser, so that the module can configure the command-line arguments and
      options it takes when called.

    - Configuration (`configure(mod, env, args)`):
      Allows a module to configure itself and any other modules it depends on.

    - Starting (`start(mod, env, args)`):
      Allows a module to fully initialise itself after configuration.

    - Running (`__call__(mod, env, args)`):
      The phase when the module indicated by the command-line, or whoever called
      `ModuleManager.run()` if that is given explicit command-line arguments,
      is run, cascading down to any modules it in turn invokes, until the
      indicated module completes.

    - Stopping (`stop(mod, env, args)`):
      Allows a module to fully tear itself down after running.

    In the above, all arguments are passed as keyword arguments. The following
    values are passed for them:

    - `mod` is a reference to the ModuleManager itself. This can be used to
      invoke and retrieve references to other modules - see below.
    - `env` is an Environment based on the actual environment, or whatever
      Environment is passed to the `run()` method.
    - `args` is an argparse Namespace containing the command-line arguments, or
      whatever arguments were passed to the `run()` method.

    In all lifecycle phases that `mod` is given, a module can invoke another
    module by calling the method on `mod` with the name of the module to be
    invoked. Invoking a module will call that module's special lifecycle method
    `invoke(phase, mod, env, args)` and return a reference to the other module.
    `phase` is the current phase of all modules (of the constants in the
    `ModuleManager.PHASES` Namespace). If the module you want to invoke is named
    the same as one of ModuleManager's own methods (though this should be rare)
    then you can use `mod.invoke_module(name)` instead. Once you have a
    reference to the module instance, you can call the module or run any methods
    that module specifies are supported. ModuleManager does not support calling
    module lifecycle methods via this reference, though they may happen to work
    correctly.

    ## Notes and Tips

    Here are some notes about the system and some tips on module development:
    
    - If you come across an error condition while trying to execute some action,
      always raise a VCSException instead of logging an error and exiting. This
      exception is handled gracefully and any wrapping/contextual actions by
      other modules are undone/finalised.

    - Be careful when developing module classes to avoid infinite recursion when
      modules call each other or each other's methods without a base case.
    """

    PHASES = Namespace(
        REGISTRATION = 'registration',
        INITIALISATION = 'initialisation',
        ARGUMENT_CONFIGURATION = 'argument-configuration',
        CONFIGURATION = 'configuration',
        STARTING = 'starting',
        RUNNING = 'running',
        STOPPING = 'stopping'
    )

    @staticmethod
    def modules_adjacent_to(file):
        """
        Utility for getting a list of all python modules in the same directory
        as the given python file path.

        Can be used make a package support being registered with
        `register_package()` by placing the following in the package's
        `__init__.py`:
        ```
        from core.modulemanager import ModuleManager
        __all__ = ModuleManager.modules_adjacent_to(__file__)
        ```
        """

        # Based on: https://stackoverflow.com/a/1057534/16967315
        modules = glob.glob(join(dirname(file), "*.py"))
        return [
            basename(module)[:-3]
            for module in modules
            if isfile(module) and not basename(module).startswith('__')
        ]

    def __init__(self, app_name, env):
        self._phase = ModuleManager.PHASES.REGISTRATION
        self._env = env
        self._args = None

        self._registered_mods = {}
        self._mods = {}

        self._arg_parser = ArgumentParser(prog=app_name)
        self._arg_subparsers = self._arg_parser.add_subparsers(dest="module")

        # Create a separate logger to avoid infinite recursion.
        # TODO: There may be a way of supporting command-line verbosity
        #       arguments, but getting verbosity from env will do for now.
        self._logger = Log()
        self._logger.configure(
            mod=self,
            env=self._env,
            args=Namespace()
        )

    # Registration
    # --------------------

    def register_package(self, *packages):
        for package in packages:
            self._logger.debug(
                f"Registering all modules in package '{package.__package__}'"
                f" ({package}) with {self}"
            )

            mm_modules = []
            for py_module_name in package.__all__:
                mm_module_name = self._module_to_class(py_module_name)

                try:
                    py_module = importlib.import_module(
                        f'{package.__package__}.{py_module_name}'
                    )
                except ImportError as e:
                    raise VCSException(
                        f"Python module '{py_module_name}' in __all__ not found"
                    ) from e

                try:
                    mm_module = getattr(py_module, mm_module_name)
                except AttributeError as e:
                    raise VCSException(
                        f"Python module '{py_module_name}' in __all__ does not"
                        f" contain a ModuleManager module: '{mm_module_name}'"
                        " not found"
                    ) from e

                mm_modules.append(mm_module)

            self.register(*mm_modules)

    def register(self, *modules):
        for module_factory in modules:
            name = self._camel_to_kebab(module_factory.__name__)
            if self._phase != ModuleManager.PHASES.REGISTRATION:
                raise VCSException(
                    f"Attempt to register module '{name}' after module"
                    " initialisation"
                )

            if self.is_registered(name):
                self._logger.info(
                    f"Skipping registering already-registered module '{name}'"
                )
                continue

            self._logger.debug(
                f"Registering module '{name}' ({module_factory}) with {self}"
            )
            self._registered_mods[name] = module_factory

    # Core Lifecycle
    # --------------------

    def run(self,
            env: Environment = None,
            args: Namespace = None,
            cli_args: 'list[str]' = None
    ):
        """
        Set off the module manager's lifecycle.

        Includes:
        - Initialise all registered modules.
        - Configure supported arguments for all registered modules.
        - Configure all registered modules.
        - Start all registered modules.
        - Invoke and call the module specified in one of the following (the
          first found is used):
          - In args (an argparse Namespace)
          - In cli_args (a list of strings parsed as command line arguments)
          - In the command line arguments (from sys.argv)
        - Stop all registered modules.

        Must be called after all modules have been registered. Attempts to
        register new modules after this is called will raise an exception.
        """

        if env is not None:
            self._env = env

        # Lifecycle: Initialise
        self._phase = ModuleManager.PHASES.INITIALISATION
        for name, module_factory in self._registered_mods.items():
            self._logger.debug(f"Initialising module '{name}'")

            if not callable(module_factory):
                raise VCSException(
                    f"Initialisation failed: '{name}' could not be initialised"
                    " because it is not callable"
                )

            try:
                self._mods[name] = module_factory()
            except RecursionError as e:
                raise VCSException(
                    f"Initialisation failed: '{name}' could not be initialised:"
                    " probable infinite recursion in __init__() of module"
                ) from e

            # For the convenience of other modules, dynamically add a method to
            # this object to invoke the module.
            if name not in self.__dict__:
                self.__dict__[name] = lambda name=name: self.invoke_module(name)

        # Lifecycle: Configure Arguments
        self._phase = ModuleManager.PHASES.ARGUMENT_CONFIGURATION
        for name, module in self._mods.items():
            if hasattr(module, 'configure_args'):
                self._logger.debug(f"Configuring arguments for module '{name}'")
                module_arg_parser = self._arg_subparsers.add_parser(name)
                module.configure_args(
                    env=self._env,
                    parser=module_arg_parser,
                    root_parser=self._arg_parser
                )

        # Parse Arguments
        if args is not None:
            self._logger.debug(f"Setting arguments")
            self._args = args
        elif cli_args is not None and len(cli_args) > 0:
            self._logger.debug(f"Parsing given arguments")
            self._args = self._arg_parser.parse_args(cli_args)
        else:
            self._logger.debug(f"Parsing command-line arguments")
            self._args = self._arg_parser.parse_args()

        # Lifecycle: Configure
        self._phase = ModuleManager.PHASES.CONFIGURATION
        for name, module in self._mods.items():
            if hasattr(module, 'configure'):
                self._logger.debug(f"Configuring module '{name}'")
                module.configure(mod=self, env=self._env, args=self._args)

        # Lifecycle: Start
        self._phase = ModuleManager.PHASES.STARTING
        for name, module in self._mods.items():
            if hasattr(module, 'start'):
                self._logger.debug(f"Starting module '{name}'")
                module.start(mod=self, env=self._env, args=self._args)
 
        # Lifecycle: Invoke and Call (Specified Module)
        self._phase = ModuleManager.PHASES.RUNNING
        self.call_module(self._args.module)

        # Lifecycle: Stop
        self._phase = ModuleManager.PHASES.STOPPING
        for name, module in self._mods.items():
            if hasattr(module, 'stop'):
                self._logger.debug(f"Stopping module '{name}'")
                module.stop(mod=self, env=self._env, args=self._args)

    # Module Utils
    # --------------------

    def is_registered(self, name):
        """
        Return True if a module with the given name has been registered with
        this ModuleManager; otherwise return False.
        """

        return name in self._registered_mods

    def is_initialised(self, name):
        """
        Return True if a registered module with the given name has been
        initialised; otherwise return False.
        """

        return name in self._mods

    def invoke_module(self, name):
        """
        Invoke and return the instance of the module with the given name.

        If no module with the given name has been registered, raise a
        VCSException.
        """

        if not self.is_initialised(name):
            raise VCSException(f"Module not initialised: '{name}'")

        # Lifecycle: Invoke
        if hasattr(self._mods[name], 'invoke'):
            self._mods[name].invoke(
                phase=self._phase,
                mod=self,
                env=self._env,
                args=self._args
            )

        return self._mods[name]

    def call_module(self, name, args=None):
        """
        Run the module with the given name with the given arguments.

        If no module with the given name has been registered, raise a
        VCSException.
        """

        if args is None:
            args = self._args

        module = self.invoke_module(name)
        if callable(module):
            module(phase=self._phase, mod=self, args=args)
        else:
            raise VCSException(f"Module not found: '{name}'")

    # Utils
    # --------------------

    # Derived from: https://stackoverflow.com/a/1176023/16967315
    def _camel_to_kebab(self, name):
        name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', name).lower()

    def _module_to_class(self, name: str):
        return name.title().replace('_', '')
