# Types
from __future__ import annotations
from typing import (
    Any,
    Callable,
    Concatenate,
    ParamSpec,
    TypeVar
)

# Everything else
import sys
import os
import re
import importlib
from graphlib import CycleError, TopologicalSorter
from argparse import ArgumentParser, Namespace

from core.envparse import EnvironmentParser
from core.exceptions import VCSException
import core.modules as core_module_package

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
    'CONFIGURED',
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
    PHASES.ARGUMENT_PARSING: [PHASES.STOPPING],
    PHASES.STARTED: [PHASES.STOPPING]
}

Params = ParamSpec("Params")
RetType = TypeVar("RetType")

class ModuleAccessor:
    ACCESS_TYPES = Namespace(
        CONFIG='CONFIG',
        SERVICE='SERVICE'
    )

    def __init__(self,
            lifecycle: ModuleLifecycle,
            module_name: str
    ):
        self._lifecycle = lifecycle
        self._module_name = module_name

    def __getattr__(self, name):
        return self._get_invoker(name)

    def __getitem__(self, name):
        return self._get_invoker(name)

    def _get_invoker(self, name):
        module = self._lifecycle._invoke_module(self._module_name)
        invokation_target: Callable = getattr(module, name)

        # You MUST decorate all invokable methods with one of the accessor
        # static methods below that adds the needed metadata. Any methods that
        # aren't decorated aren't invokable.
        if not hasattr(invokation_target, '_access_type'):
            raise VCSException(
                f"Attempt to retreive inaccessible method '{name}' from module"
                f" '{self._module_name}'"
            )

        def _invoker(*args, **kwargs):
            cur_phase = self._lifecycle._phase_of(self._module_name)

            valid_phases_for = {
                self.ACCESS_TYPES.CONFIG: (
                    PHASES.CONFIGURED
                ),
                self.ACCESS_TYPES.SERVICE: (
                    PHASES.STARTED,
                    PHASES.RUNNING,
                    PHASES.STOPPING
                )
            }

            valid_phases = valid_phases_for[invokation_target._access_type]
            if (cur_phase not in valid_phases):
                raise VCSException(
                    "A module attempted to invoke"
                    f" {invokation_target._access_type} method '{name}' of"
                    f" module '{self._module_name}' outside of valid invokation"
                    f" target phase (one of {valid_phases}; was in {cur_phase}"
                    " phase)."
                    " Ignoring invokation."
                    " This is an issue with the implementation of one of your"
                    " installed modules, not your command or configuration."
                )

            return invokation_target(*args, **kwargs)

        return _invoker

    # Utils
    # --------------------

    @staticmethod
    def invokable_as_config(
            func: Callable[Concatenate[Any, Params], RetType]
    ) -> Callable[Concatenate[Any, Params], RetType]:
        func._access_type = ModuleAccessor.ACCESS_TYPES.CONFIG # type: ignore
        return func # type: ignore

    @staticmethod
    def invokable_as_service(
            func: Callable[Concatenate[Any, Params], RetType]
    ) -> Callable[Concatenate[Any, Params], RetType]:
        func._access_type = ModuleAccessor.ACCESS_TYPES.SERVICE # type: ignore
        return func # type: ignore

class ModuleLifecycle:
    # Constructors
    # --------------------

    def __init__(self,
            app_name: str,
            mod_factories: dict[str, Callable],
            cli_env: dict[str, str] | None = None,
            cli_args: list[str] | None = None,
            parent_lifecycle: ModuleLifecycle | None = None
    ):
        self._app_name = app_name
        self._mod_factories = mod_factories
        self._cli_env = cli_env
        self._cli_args = cli_args
        self._parent_lifecycle = parent_lifecycle

        self._phase = PHASES.CREATED
        self._cur_mod_name = None
        self._mods = {}
        self._all_mods = {}

        self._start_exceptions = []
        self._run_exception = None

    def create_sublifecycle(self,
            app_name: str,
            mod_factories: dict[str, Callable],
            cli_env: dict[str, str] | None = None,
            cli_args: list[str] | None = None
    ) -> ModuleLifecycle:
        return ModuleLifecycle(
            app_name=app_name,
            mod_factories=mod_factories,
            cli_env=cli_env,
            cli_args=cli_args,
            parent_lifecycle=self
        )

    # High-Level Lifecycle
    # --------------------

    def __enter__(self):
        env_parser = EnvironmentParser(self._app_name)
        self._arg_parser = ArgumentParser(prog=self._app_name, add_help=False)

        inherited_mods: dict[str, Any] = (
            self._parent_lifecycle._mods
            if self._parent_lifecycle is not None
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
        self._env = (
            self.parse_environment(env_parser, self._all_mods, self._cli_env)
        )

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
        self._started_mods, self._start_exceptions = self.start(
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
        # Stop modules in reverse order of starting them. Also reverse the
        # mods state to reverse the order they are considered to have reached
        # the 'STOPPED' phase. See _phase_of(). Don't need to do this to
        # all_mods because all_mods is only used for lookup.
        mods_to_stop = {
            name: module
            for name, module in reversed(self._started_mods.items())
        }
        self._mods = {
            name: module
            for name, module in reversed(self._mods.items())
        }

        # Can mutate module state
        stop_exceptions = self.stop(
            mods_to_stop,

            # Update other indexes
            self._mods,
            self._all_mods,

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
        self._proceed_to_phase(PHASES.INITIALISATION)

        mods: dict[str, Any] = {}
        all_mods: dict[str, Any] = dict(inherited_mods)
        for name, factory in mod_factories.items():
            self._proceed_to_module(name)

            if name in mods or name in inherited_mods:
                self._debug(
                    f"Module '{name}' already initialised, skipping",
                    cur_mod_name=name,
                    mods=mods,
                    all_mods=all_mods
                )
                continue
            else:
                self._debug(
                    f"Initialising module '{name}'",
                    cur_mod_name=name,
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
                    cur_mod_name=name,
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
        self._proceed_to_phase(PHASES.RESOLVE_DEPENDENCIES)

        # This function assumes that any parent Lifecycle has or will have its
        # `resolve_dependencies()` function called to ensure that all mods that
        # it manages are present in its dependency graph. However, we can't
        # assume it was called before this Lifecycle's `resolve_dependencies()`,
        # so we have to re-gather deps and re-sort all mods.
        #
        # If we could assume that, then we could assume that the parent
        # Lifecycle's _mods are in order. As they necessarily don't depend on
        # any additional mods that this Lifecycle manages (or otherwise the
        # parent Lifecycle's `resolve_dependencies()` would have failed), we
        # could sort only this Lifecycle's mods and their deps, add that onto
        # the parent Lifecycle's mods in-order, then verify all required mods
        # have been initialised.
        #
        # This would likely give a small performance boost, but probably less
        # valuable than the time it took to write and maintain this comment.

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
            mods=mods, all_mods=all_mods
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
                # Check that all of this Lifecycle's mods and their deps are
                # initialised, but only add a mod to sorted mods if it's managed
                # by this Lifecycle, as sorted_mods should contain the same
                # modules as mods.
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
            'Modules (dependencies resolved):', sorted_mod_names,
            mods=mods, all_mods=all_mods
        )

        return sorted_mods

    def create_module_accessor_object(self,
            all_mods: dict[str, Any]
    ) -> Namespace:
        """
        For the convenience of modules, dynamically add methods to this
        Lifecycle to invoke each module.
        """

        self._proceed_to_phase(PHASES.CREATE_MODULE_ACCESSORS)

        return Namespace(**{
            name: ModuleAccessor(self, name)
            for name in all_mods
        })

    def configure_environment(self,
            all_mods: dict[str, Any],
            env_parser: EnvironmentParser
    ) -> None:
        self._proceed_to_phase(PHASES.ENVIRONMENT_CONFIGURATION)

        for name, module in all_mods.items():
            self._proceed_to_module(name)

            if hasattr(module, 'configure_env'):
                self._debug(
                    f"Configuring environment for module '{name}'",
                    cur_mod_name=name
                )
                module_env_parser = env_parser.add_parser(name)
                module.configure_env(
                    parser=module_env_parser,
                    root_parser=env_parser
                )

    def parse_environment(self,
            env_parser: EnvironmentParser,
            all_mods: dict[str, Any],
            cli_env: dict[str, str] | None = None
    ) -> dict[str, Namespace]:
        self._proceed_to_phase(PHASES.ENVIRONMENT_PARSING)

        if cli_env is None:
            cli_env = {
                name: value
                for name, value in os.environ.items()
                if name.startswith(self._app_name.upper())
            }

        self._debug(f"Parsing environment:", cli_env)

        envs = {}
        for name in all_mods:
            self._proceed_to_module(name)
            envs[name] = env_parser.parse_env(
                cli_env,
                subparsers_to_use=[name],
                collapse_prefixes=True
            )

        self._trace(f"Result:", envs, cur_mod_name=name)

        return envs

    # NOTE: Grammar for the command line is:
    #         app_name global_opt*
    #         module_name module_opt* module_arg*
    #         ('---' module_name module_opt* module_arg*)*

    def configure_root_arguments(self,
            all_mods: dict[str, Any],
            envs: dict[str, Namespace],
            arg_parser: ArgumentParser
    ) -> None:
        self._proceed_to_phase(PHASES.ROOT_ARGUMENT_CONFIGURATION)

        for name, module in all_mods.items():
            self._proceed_to_module(name)

            if hasattr(module, 'configure_root_args'):
                self._debug(
                    f"Configuring root arguments for module '{name}'",
                    cur_mod_name=name
                )
                module.configure_root_args(env=envs[name], parser=arg_parser)

    def parse_root_arguments(self,
            arg_parser: ArgumentParser,
            cli_args: list[str] | None = None
    ) -> tuple[Namespace, list[tuple[str, list[str]]]]:
        self._proceed_to_phase(PHASES.ROOT_ARGUMENT_PARSING)

        if cli_args is None:
            cli_args = sys.argv[1:]

        self._debug(f"Parsing root arguments:", cli_args)
        root_args, remaining_args = arg_parser.parse_known_args(cli_args)
        self._trace('Result:', root_args)

        # Only add the help options to the root parser *after* we've parsed the
        # root arguments. For some reason, `parse_known_arguments()` will
        # interpret and action the help options even if they're after an
        # unknown argument.
        arg_parser.add_argument('-h', '--help', action='help',
            help='Show this help message and exit')

        # Manually parse remaining args into a set of module arguments, split
        # on '---' and prefixed with the root arguments so that every module
        # invokation will also have all global args available to it.
        root_cli_args = cli_args[:-len(remaining_args)]
        module_cli_args_set = self._list_split(remaining_args, '---')

        module_full_cli_args_set = [
            (
                module_cli_args[0], # The module name
                [
                    *root_cli_args,
                    *module_cli_args,
                    *(['---'] if i+1 < len(module_cli_args_set) else [])
                ]
            )
            for i, module_cli_args in enumerate(module_cli_args_set)
        ]
        self._trace('Module CLI args set:', module_full_cli_args_set)

        return root_args, module_full_cli_args_set

    def configure(self,
            mods: dict[str, Any],
            envs: dict[str, Namespace],
            root_args: Namespace,
            accessor_object: Any
    ) -> None:
        self._proceed_to_phase(PHASES.CONFIGURATION)

        for name, module in mods.items():
            self._proceed_to_module(name)

            if hasattr(module, 'configure'):
                self._debug(f"Configuring module '{name}'", cur_mod_name=name)
                module.configure(
                    mod=accessor_object,
                    env=envs[name],
                    args=root_args
                )

        self._proceed_to_phase(PHASES.CONFIGURED)

    def start(self,
            mods: dict[str, Any],
            envs: dict[str, Namespace],
            root_args: Namespace,
            accessor_object: Any
    ) -> tuple[dict[str, Any], list[Exception | KeyboardInterrupt]]:
        self._proceed_to_phase(PHASES.STARTING)

        # TODO: Log exception tracebacks as well as capturing exception objects

        # Lifecycle: Start
        started_modules: dict[str, Any] = {}
        exceptions: list[Exception | KeyboardInterrupt] = []
        for name, module in mods.items():
            self._proceed_to_module(name)

            if hasattr(module, 'start'):
                self._debug(f"Starting module '{name}'", cur_mod_name=name)
                try:
                    module.start(
                        mod=accessor_object,
                        env=envs[name],
                        args=root_args
                    )
                    started_modules[name] = module
                except (Exception, KeyboardInterrupt) as e:
                    self._error(
                        f"Starting module '{name}' failed",
                        cur_mod_name=name
                    )
                    self._error(
                        'Stopping all successfully started modules ...',
                        cur_mod_name=name
                    )
                    exceptions.append(e)

                    # Don't try to start any more modules if we've already got
                    # an error.
                    break

        self._proceed_to_phase(PHASES.STARTED)
        return started_modules, exceptions

    def configure_arguments(self,
            all_mods: dict[str, Any],
            envs: dict[str, Namespace],
            arg_parser: ArgumentParser
    ) -> None:
        self._proceed_to_phase(PHASES.ARGUMENT_CONFIGURATION)

        arg_subparsers = None
        for name, module in all_mods.items():
            self._proceed_to_module(name)

            if hasattr(module, 'configure_args'):
                if arg_subparsers is None:
                    arg_subparsers = arg_parser.add_subparsers(dest="module")

                self._debug(
                    f"Configuring arguments for module '{name}'",
                    cur_mod_name=name
                )
                module_arg_parser = arg_subparsers.add_parser(name)
                module.configure_args(env=envs[name], parser=module_arg_parser)

    def parse_arguments(self,
            arg_parser: ArgumentParser,
            module_full_cli_args_set: list[tuple[str, list[str]]]
    ) -> list[tuple[str, Namespace]]:
        self._proceed_to_phase(PHASES.ARGUMENT_PARSING)

        module_args_set = []
        for name, module_cli_args in module_full_cli_args_set:
            # Don't _set_cur_module here, as module_full_cli_args_set may be in
            # any order and may have duplicates, which breaks the purpose of
            # that method. See _phase_of().

            self._debug(
                f"Parsing arguments for module '{name}':", module_cli_args,
                cur_mod_name=name
            )
            module_args_set.append(
                (name, arg_parser.parse_args(module_cli_args))
            )
            self._trace('Result:', module_args_set[-1], cur_mod_name=name)

        return module_args_set

    def invoke_and_call(self,
            module_args_set: list[tuple[str, Namespace]],
            envs: dict[str, Namespace],
            start_exceptions: list[Exception | KeyboardInterrupt],
            accessor_object: Any
    ) -> Exception | KeyboardInterrupt | None:
        self._proceed_to_phase(PHASES.RUNNING)

        if len(start_exceptions) > 0:
            self._warning(
                'Skipped running because exception(s) were raised during start'
            )
            return

        forwarded_data: Any = None
        if not sys.stdin.isatty():
            forwarded_data = sys.stdin.read()

        for name, module_args in module_args_set:
            # Don't _set_cur_module here, as module_args_set may be in any order
            # and may have duplicates, which breaks the purpose of that method.
            # See _phase_of().

            self._debug(f"Running module '{name}'", cur_mod_name=name)
            try:
                # Eww, using object state instead of args ... yes, but modules
                # have to be able to do this anyway (via the accessors), so it's
                # a precondition of this function that the state needed for
                # `invoke_module()` is set. This asserts that precondition to be
                # true.
                module = self._invoke_module(name)
                if not callable(module):
                    raise VCSException(f"Module not callable: '{name}'")

                self._debug(
                    f"Forwarded data:", forwarded_data,
                    cur_mod_name=name
                )
                forwarded_data: Any = module(
                    mod=accessor_object,
                    env=envs[name],
                    args=module_args,
                    forwarded_data=forwarded_data
                )
            except (Exception, KeyboardInterrupt) as e:
                self._error(
                    f"Run of module '{name}' failed, aborting further calls",
                    cur_mod_name=name
                )
                return e

        if forwarded_data != None:
            self._print(forwarded_data)

    def stop(self,
            mods_to_stop: dict[str, Any],
            mods: dict[str, Any],
            all_mods: dict[str, Any],

            envs: dict[str, Namespace],
            root_args: Namespace,
            start_exceptions: list[Exception | KeyboardInterrupt],
            run_exception: Exception | KeyboardInterrupt | None,
            accessor_object: Any
    ):
        self._proceed_to_phase(PHASES.STOPPING)

        stop_exceptions: list[Exception | KeyboardInterrupt] = []
        for name, module in mods_to_stop.items():
            self._proceed_to_module(name)

            if hasattr(module, 'stop'):
                self._debug(f"Stopping module '{name}'", cur_mod_name=name)
                try:
                    module.stop(
                        mod=accessor_object,
                        env=envs[name],
                        args=root_args,
                        start_exceptions=start_exceptions,
                        run_exception=run_exception,
                        stop_exceptions=stop_exceptions
                    )
                except (Exception, KeyboardInterrupt) as e:
                    self._error(
                        f"Stopping module '{name}' failed, SKIPPING.",
                        cur_mod_name=name
                    )
                    self._warning(
                        "THIS MAY HAVE LEFT YOUR SHELL, PROJECT, OR ANYTHING"
                        " ELSE UNDER ModuleManager's MANAGEMENT IN AN UNCLEAN"
                        " STATE! If you know what the above module does, then"
                        " you may be able to clean up manually.",
                        cur_mod_name=name
                    )
                    stop_exceptions.append(e)

                    # Try to stop all modules, even if we've got an error.

                finally:
                    # Remove the module from the known modules set.
                    del mods[name]
                    del all_mods[name]

        self._proceed_to_phase(PHASES.STOPPED)
        return stop_exceptions

    # 'Friends' (ala C++) of other MM classes
    # --------------------

    def _print(self,
            *objs,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        if all_mods is None:
            all_mods = self._all_mods
        if (
            'console' in all_mods and
            self._mod_has_started_phase(
                'console', PHASES.STARTED,
                cur_mod_name=cur_mod_name, mods=mods
            ) and
            not self._mod_has_started_phase(
                'console', PHASES.STOPPED,
                cur_mod_name=cur_mod_name, mods=mods
            )
        ):
            all_mods['console'].print(*objs)

    def _log(self,
            *objs,
            log_type: str,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        if all_mods is None:
            all_mods = self._all_mods
        if (
            'log' in all_mods and
            self._mod_has_started_phase(
                'log', PHASES.STARTED,
                cur_mod_name=cur_mod_name, mods=mods
            ) and
            not self._mod_has_started_phase(
                'log', PHASES.STOPPED,
                cur_mod_name=cur_mod_name, mods=mods
            )
        ):
            getattr(all_mods['log'], log_type)(*objs)

    def _error(self,
            *objs,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        self._log(
            *objs,
            log_type='error',
            cur_mod_name=cur_mod_name,
            mods=mods,
            all_mods=all_mods
        )

    def _warning(self,
            *objs,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        self._log(
            *objs,
            log_type='warning',
            cur_mod_name=cur_mod_name,
            mods=mods,
            all_mods=all_mods
        )

    def _info(self,
            *objs,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        self._log(
            *objs,
            log_type='info',
            cur_mod_name=cur_mod_name,
            mods=mods,
            all_mods=all_mods
        )

    def _debug(self,
            *objs,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        self._log(
            *objs,
            log_type='debug',
            cur_mod_name=cur_mod_name,
            mods=mods,
            all_mods=all_mods
        )

    def _trace(self,
            *objs,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ):
        self._log(
            *objs,
            log_type='trace',
            cur_mod_name=cur_mod_name,
            mods=mods,
            all_mods=all_mods
        )

    def _phase_of(self,
            mod_name: str,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None
    ) -> Phase:
        if mods is None:
            mods = self._mods
        if cur_mod_name is None:
            cur_mod_name = self._cur_mod_name

        if mod_name in mods:
            mod_list = list(mods.keys())
            if (
                cur_mod_name is not None and
                mod_name in mod_list and cur_mod_name in mod_list and
                mod_list.index(mod_name) < mod_list.index(cur_mod_name)
            ):
                return self._phase_after(self._phase)
            else:
                return self._phase
        elif self._parent_lifecycle is not None:
            return self._parent_lifecycle._phase_of(
                mod_name,
                cur_mod_name=cur_mod_name
            )
        else:
            raise VCSException(
                f"Requested the phase of unregistered module '{mod_name}'"
            )

    def _mod_has_started_phase(self,
            mod_name: str,
            required_phase: Phase,
            cur_mod_name: str | None = None,
            mods: dict[str, Any] | None = None
    ) -> bool:
        cur_index = PHASES_ORDERED.index(
            self._phase_of(mod_name, cur_mod_name=cur_mod_name, mods=mods)
        )
        required_index = PHASES_ORDERED.index(required_phase)
        return cur_index >= required_index # Close enough

    def _invoke_module(self, name: str) -> Any:
        """
        Invoke and return the instance of the module with the given name.

        If the named module has not been initialised, raise a VCSException.
        """

        if not self._is_initialised(name):
            raise VCSException(
                f"Attempt to invoke uninitialised module '{name}'"
            )

        # Lifecycle: Invoke
        if hasattr(self._all_mods[name], 'invoke'):
            self._debug(f"Invoking module: {name}", cur_mod_name=name)
            self._all_mods[name].invoke(
                phase=self._phase,
                mod=self._accessor_object
            )

        return self._all_mods[name]

    # Utils
    # --------------------

    def _proceed_to_phase(self,
            phase: Phase,
            mods: dict[str, Any] | None = None,
            all_mods: dict[str, Any] | None = None
    ) -> None:
        cur_index = PHASES_ORDERED.index(self._phase)
        requested_index = PHASES_ORDERED.index(phase)
        required_cur_index = requested_index - 1

        if (
            required_cur_index == cur_index or (
                self._phase in ALLOWED_PHASE_JUMPS and
                phase in ALLOWED_PHASE_JUMPS[self._phase]
            )
        ):
            self._phase = PHASES_ORDERED[requested_index]
            self._proceed_to_module(None)
            if self._phase is not PHASES.CREATED:
                self._info(
                    f"{'-'*5} {self._phase} {'-'*(43-len(self._phase))}",
                    mods=mods,
                    all_mods=all_mods
                )
        else:
            raise VCSException(
                f"Attempt to proceed to {phase} ModuleLifecycle phase"
                f" {'before' if cur_index < required_cur_index else 'after'}"
                f" the {PHASES_ORDERED[required_cur_index]} phase"
            )

    def _proceed_to_module(self, module_name: str | None):
        self._cur_mod_name = module_name

    def _phase_after(self, phase: Phase):
        return PHASES_ORDERED[PHASES_ORDERED.index(phase) + 1]

    def _is_initialised(self, name: str) -> bool:
        """
        Return True if a module with the given name has been initialised,
        otherwise return False.
        """

        return name in self._all_mods

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

    ModuleManager (MM) is intended to be used as a context manager. Create a
    ModuleManager, register the modules you wish to use by using
    `register()` or `register_package()`, then `run()` the manager's lifecycle,
    like so:

    ```py
    from core.modulemanager import ModuleManager

    import modules
    from commands import CustomCommand

    with ModuleManager('my-app') as module_manager:
        module_manager.register_package(modules)
        mod_manager.register(CustomCommand)
        module_manager.run()
    ```

    Set up an alias, function, or script called `my-app` that calls your
    MM-based Python app, then and run your app on the command line like:

    ```sh
    my-app custom-command --an-option optval argument
    ```

    ## Modules

    A module is a factory function (or something else callable, like a class
    constructor) for a single module instance. These module instances go through
    a defined lifecycle. Some phases in the lifecycle call a specific method on
    all registered modules that define that method.

    Modules may be 'invoked' on the command line by using their module name,
    followed by any options and arguments they require. Modules can also be
    invoked programmatically by other modules by using the `mod` namespace given
    in relevant MM lifecycle calls to call methods that are decorated with one
    of the access declarations defined in the ModuleAccessor class.

    Some core modules are always loaded by default, including the `console`,
    `log`, and `shell` modules. These allow basic I/O and interacting with the
    calling shell from MM modules. See their documentation for details.

    ## The Module Lifecycle

    The module lifecycle consists of an ordered series of phases, with some
    phase jumps allowed for error conditions. Some phases allow customisation
    by modules, including:

    ### Registration
    Called on the ModuleManager instance within its context.

    Allows the app to add modules to ModuleManager's store using the
    `register_module()` and `register_package()` methods. Any attempt to
    register a module after the registration phase will raise a VCSException.

    ### Initialisation
    `__init__()`

    Uses each module's factory callable (a class or a function) to create its
    instance. Module initialisation during this phase should be kept to a
    minimum (it can often be omitted entirely), with the majority of
    initialisation done in the Starting phase.

    ### Dependency Resolution
    `dependencies() -> list[str]`

    Retrieves the dependencies (a list of module names) of each module and sorts
    the main list of modules into a run order. All subsequent lifecycle phases
    run against each module in this order.

    Note: Circular or unregistered dependencies will raise a VCSException.

    ### Environment Configuration
    `configure_env(parser: EnvironmentParser, root_parser: EnvironmentParser) -> None`

    Passes each module an EnvironmentParser just for it, as well as the root
    EnvironmentParser, so that the module can configure the environment
    variables it requires or supports when invoked.

    Root environment variables may be use by multiple modules, and are prefixed
    with the application name. Module environment variables should only be used
    by the module that defines them, and are prefixed by the application name
    and the module name. All environment variable declarations are converted to
    ALL_CAPS naming style before parsing the environment.

    For example, a module environment variable declared as `some-var` by a
    module called `my-module` (ie. from a class named `MyModuleModule`) for an
    app called `my-app` would be named `MY_APP_MY_MODULE_SOME_VAR`.

    ### Root Argument Configuration
    `configure_root_args(env: Namespace, parser: ArgumentParser) -> None`

    Passes each module its parsed environment and an ArgumentParser just for it,
    so that the module can configure the application command-line arguments and
    options it supports when invoked. Root-level arguments can affect the
    module's behaviour when it's invoked on the command-line, or by another
    module.

    While MM permits root-level arguments to be required by a module, this is
    not recommended. If a module requires root-level arguments, then apps that
    use that module will always require those arguments when run, even if the
    module is never invoked. As such, mandatory root-level arguments should only
    be used if the argument cannot have a default value, and the module requires
    it during the configuration, starting, and/or stopping phases.

    ### Configuration
    `configure(mod: Namespace, env: Namespace, args: Namespace) -> None`

    Allows each module to configure itself and any other modules it depends
    on. This phase is usually used to configure other modules.

    Only module methods decorated with `ModuleAccessor.invokable_as_config` can
    be invoked by other modules during this phase (see below for how). Also, the
    module being invoked must have already been configured as part of this
    phase, though this won't be an issue if the module has declared all of its
    dependencies.

    ### Starting
    `start(mod: Namespace, env: Namespace, args: Namespace) -> None`

    Allows each module to fully initialise itself after environment/argument
    parsing and module configuration. This phase is usually used for setting
    attributes, acquiring resources, etc. that are dependent on environment
    variables, arguments, known-final configuration, etc.

    Only module methods decorated with `ModuleAccessor.invokable_as_service` can
    be invoked by the called modules during this phase (see below for how).

    ### Argument Configuration
    `configure_args(env: Namespace, parser: ArgumentParser) -> None`

    Passes each module an ArgumentParser just for it, so that the module can
    configure the command-line arguments and options it takes when invoked on
    the command line. This method will be called to parse the arguments of each
    separate invokation of the module on the command line, so may be called
    multiple times if the full app command uses
    [data forwarding](#data-forwarding).

    For a module to support [forwarding its result data](#data-forwarding) to
    another module, this method must declare an argument called `---` with
    `action='store_true'`, `default=False`, and some value for `dest`. The
    `help` message may explain if this module performs any special processing if
    its result data is being forwarded to another module.

    ### Running
    `__call__(mod: Namespace, env: Namespace, args: Namespace)`

    Runs the directly-called module(s). The modules being 'directly called' are
    determined by the first argument after the global options, plus the first
    argument after each instance of `---` (see
    [data forwarding](#data-forwarding)).

    Only module methods decorated with `ModuleAccessor.invokable_as_service` can
    be invoked by the called modules during this phase (see below for how).

    ### Stopping
    `stop(mod: Namespace, env: Namespace, args: Namespace) -> None`

    Allows each module to clean up after running. This lifecycle method is
    guaranteed to run for all modules that started without error
    (including if they have no `start()` lifecycle method), in reverse order
    of starting. This phase is usually used for releasing resources.

    Only module methods decorated with `ModuleAccessor.invokable_as_service` can
    be invoked by the called modules during this phase (see below for how).

    ### Notes

    All arguments to lifecycle methods are passed as keyword arguments. This is
    so that modules can accept the arguments they need and discard the rest.
    A common pattern for lifecycle methods is to slurp all arguments and keyword
    arguments, extracting only the arguments you need, eg:

    ```
    def lifecycle_method_name(self, *, mod: Namespace, **_):
        ...
    ```

    The following parameters are common to multiple lifecycle methods:

    - `mod` is a Namespace of ModuleAccessor objects. This can be used to invoke
      other modules by calling `mod.module_name.method_name()`, eg.
      `mod.log.info('Some info')`. See below for details.

    - `env` is an argparse Namespace containing an entry for each environment
      variable that the called module declared to require or support during
      environment configuration (without prefixes). The environment can come
      from either:
      - The cli_env given to `run()`, if given
      - Otherwise, the environment from the parent process, usually a shell

    - `args` is an argparse Namespace containing an entry for each argument that
      the called module declared to require or support during argument
      configuration. Any argument that wasn't passed on the command line
      contains its default value instead. Arguments can come from either:
      - The cli_args given to `run()`, if given
      - Otherwise, the arguments from the command line

    Invoking a module will call that module's special lifecycle method
    `invoke(phase: str, mod: namespace)` if it exists, then invoke the
    requested method. The `mod` parameter of `invoke()` is the same as defined
    above. `phase` is one of the constants in the `ModuleLifecycle.PHASES`
    Namespace that represents the current lifecycle phase. Modules may use
    `phase` to alter the behaviour of invokation.

    Modules that provide services should keep a reference to the accessor object
    they are given (which is usually done in `start()`) if those services need
    to invoke other modules.

    Modules should take care to avoid infinite recursion when invoking other
    modules that in turn invoke your module.
    """

    # Initialisation
    # --------------------

    def __init__(self, app_name: str, mm_cli_args: list[str] | None = None):
        self._app_name = app_name
        self._mm_cli_args = mm_cli_args

        self._registered_mods = {}
        self._core_lifecycle = None
        self._main_lifecycle = None

    # Core and Main Lifecycles
    # --------------------

    def __enter__(self):
        """
        Initialise Module Manager and MM's core modules for one or more nested
        lifecycles.
        """

        self.register_package(core_module_package)

        # Not a full lifecycle - only exists to delegate initialised core mods
        # to the main lifecycle and clean them up after the main lifecycle.
        self._core_lifecycle = ModuleLifecycle(
            self._app_name,
            self._registered_mods,
            cli_args=self._mm_cli_args
        )
        self._core_lifecycle.__enter__()

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

        ModuleManager does not support nesting runs of the same instance, so
        modules should never call this method.
        """

        assert self._core_lifecycle is not None, 'run() run before __enter__()'
        self._main_lifecycle = self._core_lifecycle.create_sublifecycle(
            app_name=self._app_name,
            mod_factories=self._registered_mods,
            cli_env=cli_env,
            cli_args=cli_args
        )
        with self._main_lifecycle as mm_lifecycle:
            mm_lifecycle.run()
        self._main_lifecycle = None

    def __exit__(self, type, value, traceback):
        """
        Clean up Module Manager after running.
        """

        assert self._core_lifecycle is not None, '__exit__() run before __enter__()'
        self._core_lifecycle.__exit__(type, value, traceback)
        self._core_lifecycle = None

    # Registration
    # --------------------

    def register_package(self, *packages):
        for package in packages:
            if self._core_lifecycle is not None:
                self._core_lifecycle._debug(
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
                if self._core_lifecycle is not None:
                    self._core_lifecycle._info(
                        "Skipping registering already-registered module"
                        f" '{mm_mod_name}'"
                    )
                continue

            if self._core_lifecycle is not None:
                self._core_lifecycle._debug(
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
