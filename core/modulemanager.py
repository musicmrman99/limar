from os.path import dirname, basename, isfile, join
import glob
import re
import importlib
from contextlib import contextmanager
from argparse import ArgumentParser, Namespace

from core.envparse import EnvironmentParser
from core.shellscript import ShellScript
from core.modules.log import Log
from core.exceptions import VCSException

class ModuleManager:
    """
    Manages the lifecycle of a set of modules of some application.

    ## Basic Usage
    
    Create a ModuleManager, register the modules you wish to use by using
    `register()` or `register_package()`, then `run()` the manager's lifecycle,
    like so:

    ```py
    from core.modulemanager import ModuleManager

    import modules
    from commands import CustomCommand

    mod_manager = ModuleManager('my-app')
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
    the ModuleManager itself (for the module given on the command line), or by
    another module.

    The module lifecycle consists of the following phases:

    - Registration (no hook):
      Adds each module to the list of modules this ModuleManager knows about.
      Note: Any attempt to register a module after the registration phase will
            raise a VCSException.

    - Initialisation (`__init__()`):
      Uses each module's factory callable (a class or a function) to create the
      module object for that module. Module initialisation during this phase
      should be kept to a minimum, with the majority of initialisation done in
      the Starting phase.

    - Environment Configuration (`configure_env(parser, root_parser)`):
      Passes each module an EnvironmentParser just for it, as well as the root
      EnvironmentParser, so that the module can configure the environment
      variables it supports when invoked.

    - Argument Configuration (`configure_args(env, parser, root_parser)`):
      Passes each module an ArgumentParser just for it, as well as the root
      ArgumentParser, so that the module can configure the command-line
      arguments and options it takes when invoked.

    - Configuration (`configure(mod, env, args)`):
      Allows each module to configure itself and any other modules it depends
      on. This phase is usually used to configure other modules.

    - Starting (`start(mod, env, args)`):
      Allows each module to fully initialise itself after environment/argument
      parsing and module configuration. This phase is usually used for setting
      env/args-dependent attributes, acquiring resources, etc.

    - Running (`__call__(mod, env, args)`):
      Runs the directly-called module. The module being 'directly called' is
      determined by the first argument (see below for where arguments can come
      from). The called module may call other modules and/or supported methods
      of other modules, recursively, within this phase.

    - Stopping (`stop(mod, env, args)`):
      Allows each module to fully tear itself down after running. This lifecycle
      method is guaranteed to run for all modules that started without error
      (including if they have no `start()` lifecycle method), in reverse order
      of starting. This phase is usually used for releasing resources.

    In the above, all arguments are passed as keyword arguments. The following
    values are passed for them:

    - `mod` is a reference to the ModuleManager itself. This can be used to
      invoke and retrieve references to other modules - see below.

    - `env` is an argparse Namespace based on the command-line environment and
      any configured default values. The environment can come from one of the
      following sources (the first one found is used):
      - The post-parse env given to `run()`
      - The pre-parse cli_env given to `run()`
      - The post-parse env given to `ModuleManager.__init__()`
      - The pre-parse arguments from the command line (ie. from sys.argv)

    - `args` is an argparse Namespace containing all command-line arguments and
      any configured default values. Arguments can come from one of the
      following sources (the first one found is used):
      - The post-parse args given to `run()`
      - The pre-parse cli_args given to `run()`
      - The post-parse args given to `ModuleManager.__init__()`
      - The pre-parse environment from the command line (ie. from os.environ)

    In all lifecycle phases that have `mod` passed to them, a module can invoke
    another module by calling the method on `mod` with the same name as the
    module to be invoked. Invoking a module will call that module's special
    lifecycle method `invoke(phase, mod, env, args)` if it exists, then return
    that module's module object back to the invoking module. In the `invoke()`
    call, `mod`, `env`, and `args` are as they are defined above. `phase` is one
    of the constants in the `ModuleManager.PHASES` argparse Namespace that
    represents the current lifecycle phase. `phase` allows the invoked module
    to change its behaviour depending on which phase it is being invoked in.

    Once you have a reference to the module instance, you can call the module or
    run any methods that module specifies are supported to be run in that phase.
    ModuleManager does not support calling module lifecycle methods via this
    reference, though they may happen to work correctly.

    ## Utility Methods

    ModuleManager provides some utility methods that can be used by modules:

    - You can determine if a particular module has been loaded by using
      `mod.is_registered('module_name')`.

    - If the module you want to invoke is named the same as one of
      ModuleManager's own methods (though this should be rare) then you can
      directly invoke a named module by using
      `mod.invoke_module('module_name')`.

    - If you need to call a module using a different environment or arguments
      than those your module was called with, then you can use:
      ```
      mod.call_module(
        'module_name',
        argparse.Namespace(APPNAME_MODULENAME_SOME_ENV_VAR='value'),
        argparse.Namespace(arg='another-value')
      )
      ```

    - If you need to make modifications to the _outer_ shell proces, such as
      setting environment variables or changing the current directory, then you
      can add commands to be run after this script by using
      `mod.add_command('command')`. Note that module authors are responsible for
      word splitting, escaping, etc.

    ## Notes and Tips

    Here are some notes about the system and some tips on module development:

    - If your module is designed to provide some temporary change to the shell
      environment, repository, or anything else for the duration of the command
      being run, then make sure to revert those changes in the `stop()`
      lifecycle method, conditionally if needed (eg. if you only make the change
      when certain arguments are passed).

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

    def __init__(self,
            app_name: str,
            env: Namespace = None,
            args: Namespace = None
    ):
        self._phase = ModuleManager.PHASES.REGISTRATION
        self._env = [env] if env is not None else []
        self._args = [args] if args is not None else []

        self._registered_mods = {}
        self._mods = {}

        self._env_parser = EnvironmentParser(app_name)
        self._arg_parser = ArgumentParser(prog=app_name)
        self._arg_subparsers = self._arg_parser.add_subparsers(dest="module")

    def __enter__(self):
        # Create a separate logger to avoid infinite recursion.
        # TODO: There may be a way of supporting environment variables or
        #       command-line arguments for verbosity and output destination, but
        #       hard-coding these will be fine for now.
        self._logger = Log()
        self._logger.configure(
            mod=self,
            env=self._env[-1] if len(self._env) > 0 else Namespace(
                VCS_LOG_OUTPUT_FILE=join(dirname(__file__), 'modulemanager.log'),
                VCS_LOG_ERROR_FILE=None,
                VCS_LOG_VERBOSITY=4
            ),
            args=self._args[-1] if len(self._args) > 0 else Namespace()
        )
        self._logger.start()

        return self

    def __exit__(self, type, value, traceback):
        self._logger.stop()

    # Registration
    # --------------------

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
            env: Namespace = None,
            args: Namespace = None,
            cli_env: 'dict[str, str]' = None,
            cli_args: 'list[str]' = None
    ):
        """
        Set off the module manager's lifecycle (see class docstring for
        details of the lifecycle).

        Must be called after all modules have been registered. Attempts to
        register new modules after this is called will raise an exception.
        """

        with self._env_args_of(env, args):
            self._run(cli_env, cli_args)

    def _run(self,
            cli_env: 'dict[str, str]' = None,
            cli_args: 'list[str]' = None
    ):
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
                self._logger.debug(
                    f"Initialised module '{name}' as {self._mods[name]}"
                )
            except RecursionError as e:
                raise VCSException(
                    f"Initialisation failed: '{name}' could not be initialised:"
                    " probable infinite recursion in __init__() of module"
                ) from e

            # For the convenience of other modules, dynamically add a method to
            # this object to invoke the module.
            if name not in self.__dict__:
                self.__dict__[name] = lambda name=name: self.invoke_module(name)

        # Lifecycle: Configure Environment
        # Note: Configuring environment before args means that configuring args
        #       can depend on the environment, which allows for things like
        #       environment-based feature toggles.

        for name, module in self._mods.items():
            if hasattr(module, 'configure_env'):
                self._logger.debug(
                    f"Configuring environment for module '{name}'"
                )
                module_env_parser = self._env_parser.add_parser(name)
                module.configure_env(
                    parser=module_env_parser,
                    root_parser=self._env_parser
                )

        # Finalise Environment (at the run level)
        if len(self._env) == 0:
            if cli_env is not None:
                self._logger.debug(f"Parsing given environment")
                self._env.append(self._env_parser.parse_env(cli_env))
            else:
                self._logger.debug(f"Parsing environment")
                self._env.append(self._env_parser.parse_env())

        env, args = self._env_args()

        # Configure ModuleManager Arguments
        self._arg_parser.add_argument('--mm-source-file',
            default='/tmp/vcs-source',
            help="""
            The path to a temporary file that will be sourced in the parent
            shell (outside of this python app). Your ModuleManager-based app
            should use a shell wrapper (such as a bash function) that generates
            the value for this option, passes it to the python app, then sources
            the file it refers to.

            This option allows modules managed by ModuleManager to add commands
            to execute in the context of the calling shell process, such as
            changing directory or setting environment variables.
            """)

        # Lifecycle: Configure Arguments
        self._phase = ModuleManager.PHASES.ARGUMENT_CONFIGURATION
        for name, module in self._mods.items():
            if hasattr(module, 'configure_args'):
                self._logger.debug(f"Configuring arguments for module '{name}'")
                module_arg_parser = self._arg_subparsers.add_parser(name)
                module.configure_args(
                    env=env,
                    parser=module_arg_parser,
                    root_parser=self._arg_parser
                )

        # Finalise Arguments, parsing if needed (at the run level)
        if len(self._args) == 0:
            if cli_args is not None:
                self._logger.debug(f"Parsing given command-line arguments")
                self._args.append(self._arg_parser.parse_args(cli_args))
            else:
                self._logger.debug(f"Parsing command-line arguments")
                self._args.append(self._arg_parser.parse_args())

        env, args = self._env_args()

        # Initialise Source File Manager
        self._source_file = ShellScript(args.mm_source_file)

        # Lifecycle: Configure
        self._phase = ModuleManager.PHASES.CONFIGURATION
        for name, module in self._mods.items():
            if hasattr(module, 'configure'):
                self._logger.debug(f"Configuring module '{name}'")
                module.configure(mod=self, env=env, args=args)

        # Initialise Error Management
        modules_started = []
        exceptions = []

        # TODO: Log exception tracebacks as well as capturing exception objects

        # Lifecycle: Start
        self._phase = ModuleManager.PHASES.STARTING
        for name, module in self._mods.items():
            if hasattr(module, 'start'):
                self._logger.debug(f"Starting module '{name}'")
                try:
                    module.start(mod=self, env=env, args=args)
                    modules_started.append(module)
                except (Exception, KeyboardInterrupt) as e:
                    self._logger.error(
                        f"Starting module '{name}' failed, attempting to stop"
                        " all successfully started modules ..."
                    )
                    exceptions.append(e)

                    # Don't try to start any more modules if we've already got
                    # an error.
                    break

        # Lifecycle: Invoke and Call (Specified Module)
        if len(exceptions) == 0:
            self._phase = ModuleManager.PHASES.RUNNING
            self._logger.debug(f"Running module '{args.module}'")
            try:
                self.call_module(args.module)
            except (Exception, KeyboardInterrupt) as e:
                self._logger.error(f"Run of module '{args.module}' failed")
                exceptions.append(e)

        # Lifecycle: Stop
        self._phase = ModuleManager.PHASES.STOPPING
        for name, module in reversed(modules_started):
            if hasattr(module, 'stop'):
                self._logger.debug(f"Stopping module '{name}'")
                try:
                    module.stop(mod=self, env=env, args=args)
                except (Exception, KeyboardInterrupt) as e:
                    self._logger.error(
                        f"Stopping module '{name}' failed, SKIPPING."
                    )
                    self._logger.warning(
                        "THIS MAY HAVE LEFT YOUR SHELL, PROJECT, OR ANYTHING"
                        " ELSE UNDER ModuleManager's MANAGEMENT IN AN UNCLEAN"
                        " STATE! If you know what the above module does, then"
                        " you may be able to clean up manually."
                    )

        # Write Source File
        if len(exceptions) == 0:
            self._logger.debug("Writing added commands to source file")
            self._source_file.write()
        else:
            self._logger.warning(
                "Skipping writing commands to the source file to avoid causing"
                " any more changes than necessary after the above error(s)."
            )
            raise exceptions[0]

    # ModuleManager Utils
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
        env, args = self._env_args()
        if hasattr(self._mods[name], 'invoke'):
            self._mods[name].invoke(
                phase=self._phase,
                mod=self,
                env=env,
                args=args
            )

        return self._mods[name]

    def call_module(self, name, env=None, args=None):
        """
        Run the module with the given name with the given arguments.

        If no module with the given name has been registered, raise a
        VCSException.
        """

        if self._phase != ModuleManager.PHASES.RUNNING:
            raise VCSException(
                f"Attempt to call module '{name}' outside of RUNNING phase"
            )

        with self._env_args_of(env, args) as (env, args):
            module = self.invoke_module(name)
            if callable(module):
                module(mod=self, env=env, args=args)
            else:
                raise VCSException(f"Module not callable: '{name}'")

    def add_shell_command(self, command):
        self._source_file.add_command(command)

    # Utils
    # --------------------

    def _env_args(self):
        return (
            self._env[-1] if len(self._env) > 0 else None,
            self._args[-1] if len(self._args) > 0 else None
        )

    @contextmanager
    def _env_args_of(self,
            env: Namespace = None,
            args: Namespace = None
    ):
        if env is not None:
            self._env.append(env)
        try:
            if args is not None:
                self._args.append(args)
            try:
                yield self._env_args()
            finally:
                if args is not None:
                    self._args.pop()
        finally:
            if env is not None:
                self._env.pop()

    # Derived from: https://stackoverflow.com/a/1176023/16967315
    def _camel_to_kebab(self, name):
        name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1-\2', name).lower()

    def _module_to_class(self, name: str):
        return name.title().replace('_', '')
