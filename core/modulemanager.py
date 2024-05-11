# Types
from __future__ import annotations
from typing import Any, Callable

# Everything else
import sys
from os.path import dirname, join
import re
import importlib
from graphlib import CycleError, TopologicalSorter
from argparse import ArgumentParser, Namespace

from core.envparse import EnvironmentParser
from core.exceptions import VCSException
import core.modules as core_module_package

class ModuleManagerRun:
    Phase = str
    PHASES_ORDERED: list[Phase] = [
        'CREATED',
        'INITIALISATION',
        'RESOLVE_DEPENDENCIES',
        'CREATE_MODULE_ACCESSORS',

        'ENVIRONMENT_CONFIGURATION',
        'ENVIRONMENT_PARSING',

        'ROOT_ARGUMENT_CONFIGURATION',
        'ROOT_ARGUMENT_PARSING',
        'CONFIGURATION',
        'STARTING',
        'STARTED',

        'ARGUMENT_CONFIGURATION',
        'ARGUMENT_PARSING',
        'RUNNING',

        'STOPPING',
        'STOPPED'
    ]
    PHASES = Namespace(**{name: name for name in PHASES_ORDERED})

    # Moving from one phase to the next is allowed by default, plus these:
    ALLOWED_PHASE_JUMPS: dict[Phase, list[Phase]] = {
        'STARTED': ['STOPPING']
    }

    # Constructors
    # --------------------

    def __init__(self,
            app_name: str,
            mod_factories: dict[str, Callable],
            cli_env: dict[str, str] | None = None,
            cli_args: list[str] | None = None,
            parent_run: ModuleManagerRun | None = None
    ):
        self._app_name = app_name
        self._mod_factories = mod_factories
        self._cli_env = cli_env
        self._cli_args = cli_args
        self._parent_run = parent_run

        self._phase = self.PHASES.CREATED
        self._mods = {}
        self._all_mods = {}

        self._start_exceptions = []
        self._run_exception = None

    def create_subrun(self,
            app_name: str,
            mod_factories: dict[str, Callable],
            cli_env: dict[str, str] | None = None,
            cli_args: list[str] | None = None
    ) -> ModuleManagerRun:
        return ModuleManagerRun(
            app_name=app_name,
            mod_factories=mod_factories,
            cli_env=cli_env,
            cli_args=cli_args,
            parent_run=self
        )

    # High-Level Lifecycle
    # --------------------

    def __enter__(self):
        env_parser = EnvironmentParser(self._app_name)
        self._arg_parser = ArgumentParser(prog=self._app_name)

        inherited_mods: dict[str, Any] = (
            self._parent_run._mods
            if self._parent_run is not None
            else {}
        )

        self._mods, self._all_mods = (
            self.initialise(self._mod_factories, inherited_mods)
        )
        self._mods = self.resolve_dependencies(self._mods, self._all_mods)
        self._accessor_object = (
            self.create_module_accessor_object(self._all_mods)
        )

        self.configure_environment(self._all_mods, env_parser)
        self._env = self.parse_environment(env_parser, self._cli_env)

        self.configure_root_arguments(
            self._all_mods,
            self._env,
            self._arg_parser
        )
        self._root_args, self._module_full_cli_args_set = (
            self.parse_root_arguments(self._arg_parser, self._cli_args)
        )

        # Can mutate module state
        self.configure(
            self._mods,
            self._env,
            self._root_args,
            self._accessor_object
        )
        self._started_modules, self._start_exceptions = self.start(
            self._mods,
            self._env,
            self._root_args,
            self._accessor_object
        )

        return self

    def run(self):
        self.configure_arguments(self._all_mods, self._env, self._arg_parser)
        self._module_args_set = self.parse_arguments(
            self._arg_parser,
            self._module_full_cli_args_set
        )

        # Can mutate module state
        self._run_exception = self.invoke_and_call(
            self._module_args_set,
            self._env,
            self._start_exceptions,
            self._accessor_object
        )

    def __exit__(self, type, value, traceback):
        # Can mutate module state
        stop_exceptions = self.stop(
            self._started_modules,
            # Update other indexes
            self._all_mods,
            self._mods,

            self._env,
            self._root_args,
            self._start_exceptions,
            self._run_exception,
            self._accessor_object
        )

        exceptions = [
            *self._start_exceptions,
            *([self._run_exception] if self._run_exception is not None else []),
            *stop_exceptions
        ]
        if len(exceptions) > 0:
            raise exceptions[0]

    # Low-Level Lifecycle
    # --------------------

    def initialise(self,
            mod_factories: dict[str, Callable],
            inherited_mods: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self._proceed_to_phase('INITIALISATION')

        mods: dict[str, Any] = {}
        all_mods: dict[str, Any] = dict(inherited_mods)
        for name, factory in mod_factories.items():
            if name in mods or name in inherited_mods:
                self._debug(
                    f"Module '{name}' already initialised, skipping",
                    mods=mods,
                    all_mods=all_mods
                )
                continue
            else:
                self._debug(
                    f"Initialising module '{name}'",
                    mods=mods,
                    all_mods=all_mods
                )

            if not callable(factory):
                raise VCSException(
                    f"Initialisation failed: '{name}' could not be initialised"
                    " because it is not callable"
                )

            try:
                all_mods[name] = mods[name] = factory()
                self._debug(
                    f"Initialised module '{name}' as {mods[name]}",
                    mods=mods,
                    all_mods=all_mods
                )
            except RecursionError as e:
                raise VCSException(
                    f"Initialisation failed: '{name}' could not be initialised:"
                    " probable infinite recursion in __init__() of module"
                ) from e

        return mods, all_mods

    def resolve_dependencies(self,
            mods: dict[str, Any],
            all_mods: dict[str, Any]
    ) -> dict[str, Any]:
        self._proceed_to_phase('RESOLVE_DEPENDENCIES')

        # This function assumes that any parent Run has or will have its
        # `resolve_dependencies()` function called to ensure that all mods that
        # it manages are present in its dependency tree, but we can't assume
        # that it was run before this Run's `resolve_dependencies()`, so we have
        # to re-gather deps and re-sort all mods.
        #
        # If we could assume that, then we could assume that the parent Run's
        # _mods are in order. As they necessarily don't depend on any additional
        # mods this Run manages (or the parent Run's `resolve_dependencies()`
        # would have failed), we could sort only this Run's mods and their deps,
        # add that onto the parent Run's mods in-order, then verify all required
        # mods have been initialised.
        #
        # This would likely give a small performance boost, but probably not
        # much.

        module_deps = {
            name: (
                mods[name].dependencies()
                if hasattr(mods[name], 'dependencies')
                else []
            )
            for name in mods.keys()
        }

        self._debug(
            'Modules (dependency graph):', module_deps,
            mods=mods,
            all_mods=all_mods
        )
        sorter = TopologicalSorter(module_deps)
        try:
            sorted_mod_names = tuple(sorter.static_order())
        except CycleError:
            raise VCSException(
                f"Resolve Dependencies failed: Modules have circular"
                " dependencies"
            )

        sorted_mods = {}
        for name in sorted_mod_names:
            try:
                # Check that all of this Run's mods and their deps are
                # initialised, but only add a mod to sorted mods if it's managed
                # by this Run, as sorted_mods should contain the same modules as
                # mods.
                mod = all_mods[name]
                if name in mods:
                    sorted_mods[name] = mod
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

        self._debug(
            'Modules (dependencies resolved):', module_deps,
            mods=mods,
            all_mods=all_mods
        )

        return sorted_mods

    def create_module_accessor_object(self,
            all_mods: dict[str, Any]
    ) -> Namespace:
        """
        For the convenience of modules, dynamically add methods to this Run to
        invoke each module.
        """

        self._proceed_to_phase('CREATE_MODULE_ACCESSORS')

        accessors = {
            name: lambda name=name: self.invoke_module(name)
            for name in all_mods
        }
        return Namespace(**accessors)

    def configure_environment(self,
            all_mods: dict[str, Any],
            env_parser: EnvironmentParser
    ) -> None:
        self._proceed_to_phase('ENVIRONMENT_CONFIGURATION')

        for name, module in all_mods.items():
            if hasattr(module, 'configure_env'):
                self._debug(f"Configuring environment for module '{name}'")
                module_env_parser = env_parser.add_parser(name)
                module.configure_env(
                    parser=module_env_parser,
                    root_parser=env_parser
                )

    def parse_environment(self,
            env_parser: EnvironmentParser,
            cli_env: dict[str, str] | None = None
    ) -> Namespace:
        self._proceed_to_phase('ENVIRONMENT_PARSING')

        if cli_env is not None:
            env = env_parser.parse_env(cli_env)
        else:
            env = env_parser.parse_env()

        return env

    # NOTE: Grammar for the command line is:
    #         app_name global_opt*
    #         module_name module_opt* module_arg*
    #         ('---' module_name module_opt* module_arg*)*

    def configure_root_arguments(self,
            all_mods: dict[str, Any],
            env: Namespace,
            arg_parser: ArgumentParser
    ) -> None:
        self._proceed_to_phase('ROOT_ARGUMENT_CONFIGURATION')

        for name, module in all_mods.items():
            if hasattr(module, 'configure_root_args'):
                self._debug(f"Configuring root arguments for module '{name}'")
                module.configure_root_args(env=env, parser=arg_parser)

    def parse_root_arguments(self,
            arg_parser: ArgumentParser,
            cli_args: list[str] | None = None
    ) -> tuple[Namespace, dict[str, list[str]]]:
        self._proceed_to_phase('ROOT_ARGUMENT_PARSING')

        if cli_args is None:
            cli_args = sys.argv[1:]

        root_args, remaining_args = arg_parser.parse_known_args(cli_args)
        self._trace('Result:', root_args)

        # Manually parse remaining args into a set of module arguments, split
        # on '---' and prefixed with the root arguments so that every module
        # invokation will also have all global args available to it.
        root_cli_args = cli_args[:-len(remaining_args)]
        module_cli_args_set = self._list_split(remaining_args, '---')

        module_full_cli_args_set = {
            module_cli_args[0]: [ # The module name
                *root_cli_args,
                module_cli_args[0],
                *(['---'] if i+1 < len(module_cli_args_set) else []),
                *module_cli_args[1:]
            ]
            for i, module_cli_args in enumerate(module_cli_args_set)
        }

        return root_args, module_full_cli_args_set

    def configure(self,
            mods: dict[str, Any],
            env: Namespace,
            root_args: Namespace,
            accessor_object: Any
    ) -> None:
        self._proceed_to_phase('CONFIGURATION')

        for name, module in mods.items():
            if hasattr(module, 'configure'):
                self._debug(f"Configuring module '{name}'")
                module.configure(mod=accessor_object, env=env, args=root_args)

    def start(self,
            mods: dict[str, Any],
            env: Namespace,
            root_args: Namespace,
            accessor_object: Any
    ) -> tuple[dict[str, Any], list[Exception | KeyboardInterrupt]]:
        self._proceed_to_phase('STARTING')

        # TODO: Log exception tracebacks as well as capturing exception objects

        # Lifecycle: Start
        started_modules: dict[str, Any] = {}
        exceptions: list[Exception | KeyboardInterrupt] = []
        for name, module in mods.items():
            if hasattr(module, 'start'):
                self._debug(f"Starting module '{name}'")
                try:
                    module.start(mod=accessor_object, env=env, args=root_args)
                    started_modules[name] = module
                except (Exception, KeyboardInterrupt) as e:
                    self._error(f"Starting module '{name}' failed")
                    self._error('Stopping all successfully started modules ...')
                    exceptions.append(e)

                    # Don't try to start any more modules if we've already got
                    # an error.
                    break

        self._proceed_to_phase('STARTED')
        return started_modules, exceptions

    def configure_arguments(self,
            all_mods: dict[str, Any],
            env: Namespace,
            arg_parser: ArgumentParser
    ) -> None:
        self._proceed_to_phase('ARGUMENT_CONFIGURATION')

        arg_subparsers = None
        for name, module in all_mods.items():
            if hasattr(module, 'configure_args'):
                if arg_subparsers is None:
                    arg_subparsers = arg_parser.add_subparsers(dest="module")

                self._debug(f"Configuring arguments for module '{name}'")
                module_arg_parser = arg_subparsers.add_parser(name)
                module.configure_args(env=env, parser=module_arg_parser)

    def parse_arguments(self,
            arg_parser: ArgumentParser,
            module_full_cli_args_set: dict[str, list[str]]
    ) -> dict[str, Namespace]:
        self._proceed_to_phase('ARGUMENT_PARSING')

        module_args_set = {}
        for name, module_cli_args in module_full_cli_args_set.items():
            self._debug(
                f"Parsing arguments for module '{name}':"
                f" {' '.join(module_cli_args)}"
            )
            module_args_set[name] = arg_parser.parse_args(module_cli_args)
            self._trace('Result:', module_args_set[name])

        return module_args_set

    def invoke_and_call(self,
            module_args_set: dict[str, Namespace],
            env: Namespace,
            start_exceptions: list[Exception | KeyboardInterrupt],
            accessor_object: Any
    ) -> Exception | KeyboardInterrupt | None:
        self._proceed_to_phase('RUNNING')

        if len(start_exceptions) > 0:
            self._warning(
                'Skipped running because exception(s) were raised during start'
            )
            return

        forwarded_data = None
        for name, module_args in module_args_set.items():
            self._debug(f"Running module '{name}'")
            try:
                # Eww, using object state instead of args ... yes, but modules
                # have to be able to do this anyway (probably by proxy via the
                # accessors), so it's a precondition of this function that the
                # state needed for `invoke_module()` is set. This asserts that
                # precondition to be true.
                module = self.invoke_module(name)
                if not callable(module):
                    raise VCSException(f"Module not callable: '{name}'")

                forwarded_data = module(
                    mod=accessor_object,
                    env=env,
                    args=module_args,
                    forwarded_data=forwarded_data
                )
            except (Exception, KeyboardInterrupt) as e:
                self._error(
                    f"Run of module '{name}' failed, aborting further calls"
                )
                return e

        if forwarded_data != None:
            print(forwarded_data)

    def stop(self,
            started_modules: dict[str, Any],
            all_mods: dict[str, Any],
            mods: dict[str, Any],

            env: Namespace,
            root_args: Namespace,
            start_exceptions: list[Exception | KeyboardInterrupt],
            run_exception: Exception | KeyboardInterrupt | None,
            accessor_object: Any
    ):
        self._proceed_to_phase('STOPPING')

        stop_exceptions: list[Exception | KeyboardInterrupt] = []
        for name, module in reversed(started_modules.items()):
            if hasattr(module, 'stop'):
                self._debug(f"Stopping module '{name}'")
                try:
                    module.stop(
                        mod=accessor_object,
                        env=env,
                        args=root_args,
                        start_exceptions=start_exceptions,
                        run_exception=run_exception,
                        stop_exceptions=stop_exceptions
                    )
                except (Exception, KeyboardInterrupt) as e:
                    self._error(
                        f"Stopping module '{name}' failed, SKIPPING."
                    )
                    self._warning(
                        "THIS MAY HAVE LEFT YOUR SHELL, PROJECT, OR ANYTHING"
                        " ELSE UNDER ModuleManager's MANAGEMENT IN AN UNCLEAN"
                        " STATE! If you know what the above module does, then"
                        " you may be able to clean up manually."
                    )
                    stop_exceptions.append(e)

                    # Try to stop all modules, even if we've got an error.

                finally:
                    # Remove the module from the known modules set.
                    del mods[name]
                    del all_mods[name]

        self._proceed_to_phase('STOPPED')
        return stop_exceptions

    # Module-Accessible Utils
    # --------------------

    def is_initialised(self, name: str) -> bool:
        """
        Return True if a module with the given name has been initialised,
        otherwise return False.
        """

        return name in self._all_mods

    def invoke_module(self, name: str) -> Any:
        """
        Invoke and return the instance of the module with the given name.

        If the named module has not been initialised, raise a VCSException.
        """

        if not self.is_initialised(name):
            raise VCSException(
                f"Attempt to invoke uninitialised module '{name}'"
            )

        # Lifecycle: Invoke
        if hasattr(self._all_mods[name], 'invoke'):
            self._debug(f"Invoking module: {name}")
            self._all_mods[name].invoke(
                phase=self._phase,
                mod=self._accessor_object
            )

        return self._all_mods[name]

    # 'Friends' (ala C++) of ModuleManager
    # --------------------

    def _error(self,
            *objs,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        if all_mods is None:
            all_mods = self._all_mods
        if (
            'log' in all_mods and
            self._mod_has_started_phase('log', 'STARTED', mods=mods) and
            not self._mod_has_started_phase('log', 'STOPPING', mods=mods)
        ):
            all_mods['log'].error(*objs)

    def _warning(self,
            *objs,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        if all_mods is None:
            all_mods = self._all_mods
        if (
            'log' in all_mods and
            self._mod_has_started_phase('log', 'STARTED', mods=mods) and
            not self._mod_has_started_phase('log', 'STOPPING', mods=mods)
        ):
            all_mods['log'].warning(*objs)

    def _info(self,
            *objs,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        if all_mods is None:
            all_mods = self._all_mods
        if (
            'log' in all_mods and
            self._mod_has_started_phase('log', 'STARTED', mods=mods) and
            not self._mod_has_started_phase('log', 'STOPPING', mods=mods)
        ):
            all_mods['log'].info(*objs)

    def _debug(self,
            *objs,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        if all_mods is None:
            all_mods = self._all_mods
        if (
            'log' in all_mods and
            self._mod_has_started_phase('log', 'STARTED', mods=mods) and
            not self._mod_has_started_phase('log', 'STOPPING', mods=mods)
        ):
            all_mods['log'].debug(*objs)

    def _trace(self,
            *objs,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        if all_mods is None:
            all_mods = self._all_mods
        if (
            'log' in all_mods and
            self._mod_has_started_phase('log', 'STARTED', mods=mods) and
            not self._mod_has_started_phase('log', 'STOPPING', mods=mods)
        ):
            all_mods['log'].trace(*objs)

    # Utils
    # --------------------

    def _phase_of(self,
            mod_name: str,
            mods: dict[str, Any] | None = None
    ) -> Phase:
        if mods is None:
            mods = self._mods

        if mod_name in mods:
            return self._phase
        elif self._parent_run is not None:
            return self._parent_run._phase_of(mod_name)
        else:
            raise VCSException(
                f"Requested the phase of unregistered module '{mod_name}'"
            )

    def _mod_has_started_phase(self,
            mod_name: str,
            required_phase: Phase,
            mods: dict[str, Any] | None = None
    ) -> bool:
        cur_index = self.PHASES_ORDERED.index(
            self._phase_of(mod_name, mods=mods)
        )
        required_index = self.PHASES_ORDERED.index(required_phase)
        return cur_index >= required_index # Close enough

    def _proceed_to_phase(self,
            phase: Phase,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ) -> None:
        cur_index = self.PHASES_ORDERED.index(self._phase)
        requested_index = self.PHASES_ORDERED.index(phase)
        required_cur_index = requested_index - 1

        if (
            required_cur_index == cur_index or (
                self._phase in self.ALLOWED_PHASE_JUMPS and
                phase in self.ALLOWED_PHASE_JUMPS[self._phase]
            )
        ):
            self._phase = self.PHASES_ORDERED[requested_index]
            if self._phase is not self.PHASES.CREATED:
                self._info(
                    f"{'-'*5} {self._phase} {'-'*(43-len(self._phase))}",
                    mods=mods,
                    all_mods=all_mods
                )
        else:
            raise VCSException(
                f"Attempt to proceed to {phase} ModuleManager run phase"
                f" {'before' if cur_index < required_cur_index else 'after'}"
                f" the {self.PHASES_ORDERED[required_cur_index]} phase"
            )

    def _list_split(self, list_, sep):
        lists = [[]]
        for item in list_:
            if item == sep:
                lists.append([])
            else:
                lists[-1].append(item)
        return lists

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
    `ModuleManagerRun.PHASES` argparse Namespace that represents the current
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

    # Initialisation
    # --------------------

    def __init__(self, app_name: str, mm_cli_args: list[str] | None = None):
        self._app_name = app_name
        self._mm_cli_args = mm_cli_args

        self._registered_mods = {}
        self._core_run = None
        self._main_run = None

    # Core Lifecycle
    # --------------------

    def __enter__(self):
        """
        Initialise Module Manager and MM's core modules for one or more runs.
        """

        self.register_package(core_module_package)

        # Not a full run - only exists to delegate initialised core mods to the
        # main run and clean them up after the main run.
        self._core_run = ModuleManagerRun(
            self._app_name,
            self._registered_mods,
            cli_env={
                'VCS_LOG_FILE': join(dirname(__file__), 'modulemanager.log'),
                'VCS_LOG_VERBOSITY': '4'
            },
            cli_args=self._mm_cli_args
        )
        self._core_run.__enter__()

        return self

    def run(self,
            cli_env: dict[str, str] | None = None,
            cli_args: list[str] | None = None
    ):
        """
        Set off the module manager's lifecycle (see class docstring for
        details of the lifecycle).

        Must be called after all modules have been registered. Attempts to
        register new modules after this is called will raise an exception.

        ModuleManager does not support nesting runs on the same instance, so
        modules should never call this method.
        """

        assert self._core_run is not None, 'run() run before __enter__()'
        self._main_run = self._core_run.create_subrun(
            app_name=self._app_name,
            mod_factories=self._registered_mods,
            cli_env=cli_env,
            cli_args=cli_args
        )
        with self._main_run as mm_run:
            mm_run.run()
        self._main_run = None

    def __exit__(self, type, value, traceback):
        """
        Clean up Module Manager after one or more runs.
        """

        assert self._core_run is not None, '__exit__() run before __enter__()'
        self._core_run.__exit__(type, value, traceback)
        self._core_run = None

    # Registration
    # --------------------

    def register_package(self, *packages):
        for package in packages:
            if self._core_run is not None:
                self._core_run._debug(
                    f"Registering all modules in package"
                    f" '{package.__package__}' ({package}) with {self}"
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
            if mm_mod_name in self._registered_mods:
                if self._core_run is not None:
                    self._core_run._info(
                        "Skipping registering already-registered module"
                        f" '{mm_mod_name}'"
                    )
                continue

            if self._core_run is not None:
                self._core_run._debug(
                    f"Registering module '{mm_mod_name}' ({module_factory})"
                    f" with {self}"
                )
            self._registered_mods[mm_mod_name] = module_factory

    # Utils
    # --------------------

    # Derived from: https://stackoverflow.com/a/1176023/16967315
    def _class_to_mm_module(self, name):
        name = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
        name = re.sub('([a-z0-9])([A-Z])', r'\1-\2', name)
        return name.lower().removesuffix('-module')

    def _py_module_to_class(self, name: str):
        return name.title().replace('_', '') + 'Module'
