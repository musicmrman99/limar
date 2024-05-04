import sys
from os.path import dirname, basename, isfile, join
import glob
import re
import importlib
from contextlib import contextmanager
from graphlib import CycleError, TopologicalSorter
from argparse import ArgumentParser, Namespace

from core.envparse import EnvironmentParser
from core.shellscript import ShellScript
from core.modules.log import LogModule
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

    - Dependency Resolution (`dependencies()`):
      Retrieves the dependencies (an iterable of module names) of each module
      and sorts the main list of modules into order. All subsequent lifecycle
      phases are run against each module in this order.
      Note: The presence of circular or unregistered dependencies will raise a
            VCSException.

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
    lifecycle method `invoke(phase, mod)` if it exists, then return that
    module's module object back to the invoking module. In the `invoke()` call,
    `mod` is as it is defined above. `phase` is one of the constants in the
    `ModuleManager.PHASES` argparse Namespace that represents the current
    lifecycle phase. `phase` allows the invoked module to change its behaviour
    depending on which phase it is being invoked in.

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

    - If you need to make modifications to the _outer_ shell process, such as
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
        ENVIRONMENT_CONFIGURATION = 'environment-configuration',
        ARGUMENT_CONFIGURATION = 'argument-configuration',
        CONFIGURATION = 'configuration',
        STARTING = 'starting',
        RUNNING = 'running',
        STOPPING = 'stopping'
    )

    def __init__(self, app_name: str):
        self._app_name = app_name

        self._phase = ModuleManager.PHASES.REGISTRATION
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
        self._logger = LogModule()
        self._logger.configure(
            mod=self,
            env=Namespace(
                VCS_LOG_OUTPUT_FILE=join(dirname(__file__), 'modulemanager.log'),
                VCS_LOG_ERROR_FILE=None,
                VCS_LOG_VERBOSITY=4
            ),
            args=Namespace()
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
                mm_class_name = self._py_module_to_class(py_module_name)

                try:
                    py_module = importlib.import_module(
                        f'{package.__package__}.{py_module_name}'
                    )
                except ImportError as e:
                    raise VCSException(
                        f"Python module '{py_module_name}' in __all__ not found"
                    ) from e

                try:
                    mm_module = getattr(py_module, mm_class_name)
                except AttributeError as e:
                    raise VCSException(
                        f"Python module '{py_module_name}' in __all__ does not"
                        f" contain a ModuleManager module: '{mm_class_name}'"
                        " not found"
                    ) from e

                mm_modules.append(mm_module)

            self.register(*mm_modules)

    def register(self, *modules):
        for module_factory in modules:
            mm_mod_name = self._class_to_mm_module(module_factory.__name__)
            if self._phase != ModuleManager.PHASES.REGISTRATION:
                raise VCSException(
                    f"Attempt to register module '{mm_mod_name}' after module"
                    " initialisation"
                )

            if self.is_registered(mm_mod_name):
                self._logger.info(
                    "Skipping registering already-registered module"
                    f" '{mm_mod_name}'"
                )
                continue

            self._logger.debug(
                f"Registering module '{mm_mod_name}' ({module_factory}) with"
                f" {self}"
            )
            self._registered_mods[mm_mod_name] = module_factory

    # Core Lifecycle
    # --------------------

    def run(self,
            cli_env: 'dict[str, str]' = None,
            cli_args: 'list[str]' = None
    ):
        """
        Set off the module manager's lifecycle (see class docstring for
        details of the lifecycle).

        Must be called after all modules have been registered. Attempts to
        register new modules after this is called will raise an exception.

        ModuleManager does not support nesting runs on the same instance, so
        modules should never call this method.
        """

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

        # Lifecycle: Resolve Dependencies
        module_deps = {
            name: (
                self._mods[name].dependencies()
                if hasattr(self._mods[name], 'dependencies')
                else []
            )
            for name in self._mods.keys()
        }

        self._logger.debug('Modules (dependency graph):', module_deps)
        module_sorter = TopologicalSorter(module_deps)
        try:
            modules_sorted = tuple(module_sorter.static_order())
        except CycleError:
            raise VCSException(
                f"Resolve Dependencies failed: Modules have circular"
                " dependencies"
            )

        _mods = {}
        for name in modules_sorted:
            try:
                _mods[name] = self._mods[name]
            except KeyError:
                # Only need single-level resolution - the user should be able
                # to figure out the problem from there.
                missing_module_rev_deps = [
                    check_name
                    for check_name, check_deps in module_deps.items()
                    if name in check_deps
                ]
                raise VCSException(
                    f"Resolve Dependencies failed: Module '{name}' depended on"
                    f" by modules {missing_module_rev_deps} not registered"
                )
        self._logger.debug('Modules (dependencies resolved):', module_deps)

        # Lifecycle: Configure Environment
        self._phase = ModuleManager.PHASES.ENVIRONMENT_CONFIGURATION
        for name, module in _mods.items():
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
        self._logger.debug(f"Parsing environment")
        if cli_env is not None:
            env = self._env_parser.parse_env(cli_env)
        else:
            env = self._env_parser.parse_env()

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
        for name, module in _mods.items():
            if hasattr(module, 'configure_args'):
                self._logger.debug(f"Configuring arguments for module '{name}'")
                module_arg_parser = self._arg_subparsers.add_parser(name)
                module.configure_args(
                    env=env,
                    parser=module_arg_parser,
                    root_parser=self._arg_parser
                )

        # Finalise Arguments
        if cli_args is not None:
            cli_args = [self._app_name, *cli_args]
        else:
            cli_args = list(sys.argv)
            cli_args[0] = self._app_name

        # Split Arguments into Module Invokations
        # Grammar for the command line is:
        #   app_name global_opt*
        #   module_name module_opt* module_arg*
        #   ('->' module_name module_opt* module_arg*)*

        app_name = cli_args[0]
        cli_args = cli_args[1:]

        global_opts = []
        for cli_arg in cli_args:
            if (not cli_arg.startswith('-')):
                break
            global_opts.append(cli_arg)
        cli_args = cli_args[len(global_opts):]

        global_invokation_args = [app_name, *global_opts]
        module_invokation_args_set = self._list_split(cli_args, '->')

        # Parse Global Arguments
        if cli_args is not None:
            global_args = self._arg_parser.parse_args(global_invokation_args)
        else:
            global_args = self._arg_parser.parse_args(global_invokation_args)

        # Initialise Source File Manager
        self._source_file = ShellScript(global_args.mm_source_file)

        # Lifecycle: Configure
        self._phase = ModuleManager.PHASES.CONFIGURATION
        for name, module in _mods.items():
            if hasattr(module, 'configure'):
                self._logger.debug(f"Configuring module '{name}'")
                module.configure(mod=self, env=env, args=global_args)

        # Initialise Error Management
        modules_started = {}
        exceptions = []

        # TODO: Log exception tracebacks as well as capturing exception objects

        # Lifecycle: Start
        self._phase = ModuleManager.PHASES.STARTING
        for name, module in _mods.items():
            if hasattr(module, 'start'):
                self._logger.debug(f"Starting module '{name}'")
                try:
                    module.start(mod=self, env=env, args=global_args)
                    modules_started[name] = module
                except (Exception, KeyboardInterrupt) as e:
                    self._logger.error(
                        f"Starting module '{name}' failed, attempting to stop"
                        " all successfully started modules ..."
                    )
                    exceptions.append(e)

                    # Don't try to start any more modules if we've already got
                    # an error.
                    break

        # Lifecycle: Invoke and Call (Specified Modules)
        if len(exceptions) == 0:
            self._phase = ModuleManager.PHASES.RUNNING

            forward_data = None
            for module_invokation_args in module_invokation_args_set:
                # Parse Module Arguments
                module_name = module_invokation_args[0]
                full_mod_invk_args = [
                    *global_invokation_args, *module_invokation_args
                ]
                module_args = self._arg_parser.parse_args(full_mod_invk_args)

                # Invoke and Call Module
                self._logger.debug(f"Running module '{module_name}'")
                try:
                    module = self.invoke_module(module_name)
                    if not callable(module):
                        raise VCSException(
                            f"Module not callable: '{module_name}'"
                        )

                    forward_data = module(
                        mod=self,
                        env=env,
                        args=module_args,
                        forward_data=forward_data
                    )
                except (Exception, KeyboardInterrupt) as e:
                    self._logger.error(f"Run of module '{module_name}' failed")
                    exceptions.append(e)

        # Lifecycle: Stop
        self._phase = ModuleManager.PHASES.STOPPING
        for name, module in reversed(modules_started.items()):
            if hasattr(module, 'stop'):
                self._logger.debug(f"Stopping module '{name}'")
                try:
                    module.stop(mod=self, env=env, args=global_args)
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
        if hasattr(self._mods[name], 'invoke'):
            self._mods[name].invoke(phase=self._phase, mod=self)

        return self._mods[name]

    def add_shell_command(self, command):
        self._source_file.add_command(command)

    # Utils
    # --------------------

    # Derived from: https://stackoverflow.com/a/1176023/16967315
    def _class_to_mm_module(self, name):
        name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        name = re.sub('([a-z0-9])([A-Z])', r'\1-\2', name)
        return name.lower().removesuffix('-module')

    def _py_module_to_class(self, name: str):
        return name.title().replace('_', '') + 'Module'

    def _list_split(self, list_, sep):
        lists = [[]]
        for item in list_:
            if item == sep:
                lists.append([])
            else:
                lists[-1].append(item)
        return lists
