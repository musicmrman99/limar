# Types
from __future__ import annotations
from typing import (
    Any,
    Callable,
    Concatenate,
    Literal,
    Mapping,
    MutableMapping,
    MutableSequence,
    ParamSpec,
    Sequence,
    TypeVar
)

# Everything else
import sys
import os
import re
import importlib
from copy import copy
from graphlib import CycleError, TopologicalSorter
from argparse import ArgumentParser, Namespace

from core.envparse import EnvironmentParser
from core.utils import list_split_match
from core.exceptions import LIMARException
import core.modules as core_module_package

from core.modules.docs_utils.docs_arg import docs_for, add_docs_arg

from core.modules.phase_utils.phase import Phase
from core.modules.phase_utils.phase_system import PhaseSystem
from core.modules.phase_utils.phased_process import PhasedProcess

# LIFECYCLE_PHASE_SYSTEM, but with a shorter name because it's used so often
LIFECYCLE = PhaseSystem(
    f'{__name__}:lifecycle',
    (
        'CREATED',
        'GET_MANAGED_MODULES',
        'GET_ALL_MODULES',
        'INITIALISATION',
        'RESOLVE_DEPENDENCIES',
        'CREATE_MODULE_ACCESSORS',

        'ENVIRONMENT_CONFIGURATION',
        'ENVIRONMENT_PARSING',

        'ROOT_ARGUMENT_CONFIGURATION',
        'ROOT_ARGUMENT_PARSING',
        'CONFIGURATION',
        'STARTING',

        'ARGUMENT_CONFIGURATION',
        'ARGUMENT_PARSING',
        'RUNNING',

        'STOPPING',
        'STOPPED',
    ),
    {
        'STARTING': ('STOPPING',),
        'ARGUMENT_PARSING': ('STOPPING',),
    },
    initial_phase='CREATED',
    completed_phase='STOPPED'
)

Params = ParamSpec("Params")
RetType = TypeVar("RetType")

class ModuleAccessor:
    ACCESS_TYPES = Namespace(
        FUNCTION='FUNCTION',
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
            raise LIMARException(
                f"Attempt to retreive inaccessible method '{name}' from module"
                f" '{self._module_name}'"
            )

        def _invoker(*args, **kwargs):
            can_access_module_as = {
                # Functions (whether pure or impure) can be accessed in any
                # phase, but they MUST NOT depend on the current phase or any
                # state that is dependent on it. This is difficult to verify, so
                # for now there are no checks performed for this access type.
                self.ACCESS_TYPES.FUNCTION: lambda: True,

                self.ACCESS_TYPES.CONFIG: lambda: (
                    # If the target module has completed configuration
                    self._lifecycle._has_mod(
                        self._module_name,
                        'completed',
                        LIFECYCLE.PHASES.CONFIGURATION
                    ) and
                    # If ANY module hasn't completed configuration
                    not self._lifecycle._has_mod(
                        self._module_name,
                        'started',
                        LIFECYCLE.PHASES.STARTING
                    )
                ),

                self.ACCESS_TYPES.SERVICE: lambda: (
                    self._lifecycle._has_mod(
                        self._module_name,
                        'completed',
                        LIFECYCLE.PHASES.STARTING
                    ) and
                    not self._lifecycle._has_mod(
                        self._module_name,
                        'started',
                        LIFECYCLE.PHASES.STOPPING
                    )
                )
            }

            if (not can_access_module_as[invokation_target._access_type]()):
                raise LIMARException(
                    "A module attempted to invoke"
                    f" {invokation_target._access_type} method '{name}' of"
                    f" module '{self._module_name}' outside of valid invokation"
                    f" target phase range."
                    " This is an issue with the implementation of one of your"
                    " installed modules, not your command or configuration."
                )

            return invokation_target(*args, **kwargs)

        return _invoker

    # Utils
    # --------------------

    @staticmethod
    def invokable_as_function(
            func: Callable[Concatenate[Any, Params], RetType]
    ) -> Callable[Concatenate[Any, Params], RetType]:
        func._access_type = ModuleAccessor.ACCESS_TYPES.FUNCTION # type: ignore
        return func # type: ignore

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
            app: Callable,
            app_name: str,
            mod_factories: dict[str, Callable],
            cli_env: dict[str, str] | None = None,
            cli_args: list[str] | None = None,
            parent_lifecycle: ModuleLifecycle | None = None
    ):
        self._app = app
        self._app_name = app_name
        self._mod_factories = mod_factories
        self._cli_env = cli_env
        self._cli_args = cli_args
        self._parent_lifecycle = parent_lifecycle

        self._controller = PhasedProcess(LIFECYCLE, id_length=0)
        self._managed_mod_names = None
        self._all_mod_names = None
        self._mods = {}
        self._all_mods = {}

        self._MODULE_PHASE_SYSTEM = None
        self._ALL_MODULE_PHASE_SYSTEM = None

        self._start_exceptions = []
        self._run_exception = None

    def create_sublifecycle(self,
            app: Callable,
            app_name: str,
            mod_factories: dict[str, Callable],
            cli_env: dict[str, str] | None = None,
            cli_args: list[str] | None = None
    ) -> ModuleLifecycle:
        return ModuleLifecycle(
            app=app,
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
        self._arg_parser = ArgumentParser(
            prog=self._app_name,
            epilog=docs_for(self._app),
            add_help=False
        )

        inherited_mods: dict[str, Any] = (
            self._parent_lifecycle._mods
            if self._parent_lifecycle is not None
            else {}
        )

        # Categorise, initialise, sort, and setup access to modules
        # Note: The phase systems are accessed from self from here on
        self._managed_mod_names, self._MODULE_PHASE_SYSTEM = (
            self.get_managed_modules(self._mod_factories, inherited_mods)
        )
        self._all_mod_names, self._ALL_MODULE_PHASE_SYSTEM = (
            self.get_all_modules(self._managed_mod_names, inherited_mods)
        )
        self._mods, self._all_mods = self.initialise(
            self._managed_mod_names,
            self._mod_factories,
            inherited_mods
        )

        self._mods, self._MODULE_PHASE_SYSTEM = (
            self.resolve_dependencies(self._mods, self._all_mods)
        )
        self._accessor_object = (
            self.create_module_accessor_object(self._all_mods)
        )

        # Configure environment and global/root arguments
        self.configure_environment(
            self._all_mods,
            env_parser,
            self._accessor_object
        )
        self._env = self.parse_environment(
            env_parser,
            self._all_mod_names,
            self._cli_env
        )

        self.configure_root_arguments(
            self._all_mods,
            self._env,
            self._arg_parser,
            self._accessor_object
        )
        self._root_args, self._module_full_cli_args_set = (
            self.parse_root_arguments(self._arg_parser, self._cli_args)
        )

        # Configure and start modules (WARNING: can mutate module state)
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
        # Configure call-specific arguments
        self.configure_arguments(
            self._all_mods,
            self._env,
            self._arg_parser,
            self._accessor_object
        )
        self._module_args_set = self.parse_arguments(
            self._arg_parser,
            self._module_full_cli_args_set
        )

        # Invoke modules (WARNING: can mutate module state)
        self._run_exception = self.invoke_and_call(
            self._module_args_set,
            self._env,
            self._start_exceptions,
            self._accessor_object
        )

    def __exit__(self, type, value, traceback):
        # Stop modules in reverse order of starting them. Also reverse the
        # mods state to reverse the order they are considered to have 'started'
        # the 'STOPPING' phase. Don't need to do this to all_mods because
        # all_mods is only used for lookup.
        mods_to_stop = tuple(reversed(self._started_mods.keys()))
        self._mods = {
            name: module
            for name, module in reversed(self._mods.items())
        }
        self._MODULE_PHASE_SYSTEM = self._create_subsystem(
            f'{__name__}:reversed_sorted_modules',
            tuple(self._mods.keys())
        )

        # Stop modules (WARNING: can mutate module state)
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

        # Handle errors
        exceptions = [
            *self._start_exceptions,
            *([self._run_exception] if self._run_exception is not None else []),
            *stop_exceptions
        ]
        if len(exceptions) > 0:
            raise exceptions[0]

    # Low-Level Lifecycle
    # --------------------

    def get_managed_modules(self,
            mod_factories: dict[str, Callable],
            inherited_mods: dict[str, Any]
    ) -> tuple[tuple[str, ...], PhaseSystem]:
        self._proceed_to_phase(LIFECYCLE.PHASES.GET_MANAGED_MODULES)

        managed_mods: list[str] = []
        for name in mod_factories.keys():
            if name in managed_mods or name in inherited_mods:
                self._debug(f"Module '{name}' already initialised, skipping")
            else:
                managed_mods.append(name)

        module_lifecycle = self._create_subsystem(
            f'{__name__}:unsorted_modules',
            tuple(managed_mods)
        )

        return tuple(managed_mods), module_lifecycle

    def get_all_modules(self,
            mod_names: tuple[str, ...],
            inherited_mods: dict[str, Any]
    ) -> tuple[tuple[str, ...], PhaseSystem]:
        self._proceed_to_phase(LIFECYCLE.PHASES.GET_ALL_MODULES)

        all_module_lifecycle = self._create_subsystem(
            f'{__name__}:unsorted_all_modules',
            (*inherited_mods.keys(), *mod_names)
        )

        return (*inherited_mods.keys(), *mod_names), all_module_lifecycle

    def initialise(self,
            managed_mod_names: tuple[str, ...],
            mod_factories: dict[str, Callable],
            inherited_mods: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        mod_subproc = self._start_module_subprocess_for(
            LIFECYCLE.PHASES.INITIALISATION
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.INITIALISATION)

        mods: dict[str, Any] = {}
        for name in managed_mod_names:
            mod_subproc.transition_to(name)
            self._debug(f"Initialising module '{name}'")

            factory = mod_factories[name]

            if not callable(factory):
                raise LIMARException(
                    f"Initialisation failed: module '{name}' could not be"
                    " initialised because it is not callable"
                )

            try:
                mods[name] = factory()
                self._debug(f"Initialised module '{name}' as {mods[name]}")
            except RecursionError as e:
                raise LIMARException(
                    f"Initialisation failed: '{name}' could not be initialised:"
                    " probable infinite recursion in __init__() of module"
                ) from e

        mod_subproc.transition_to_complete()
        return mods, inherited_mods | mods

    def resolve_dependencies(self,
            mods: dict[str, Any],
            all_mods: dict[str, Any]
    ) -> tuple[dict[str, Any], PhaseSystem]:
        self._proceed_to_phase(LIFECYCLE.PHASES.RESOLVE_DEPENDENCIES)

        # This function assumes that any parent Lifecycle has or will have its
        # `resolve_dependencies()` function called to ensure that all mods that
        # it manages are present in its dependency graph. However, we can't
        # assume it was called before this Lifecycle's `resolve_dependencies()`,
        # so we have to re-gather deps and re-sort all mods.
        #
        # If we could assume that, then we could also assume that the parent
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

        self._debug('Modules (dependency graph):', module_deps)
        sorter = TopologicalSorter(module_deps)
        try:
            sorted_mod_names = tuple(sorter.static_order())
        except CycleError:
            raise LIMARException(
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
                raise LIMARException(
                    f"Resolve Dependencies failed: Module '{name}' depended on"
                    f" by modules {missing_module_rev_deps} not registered"
                )

        own_sorted_mod_names = list(sorted_mods.keys())
        sorted_module_lifecycle = self._create_subsystem(
            f'{__name__}:sorted_modules',
            tuple(own_sorted_mod_names)
        )

        self._debug('Modules (dependencies resolved):', sorted_mod_names)
        self._debug(
            'Own Modules (dependencies resolved):',
            own_sorted_mod_names
        )
        return sorted_mods, sorted_module_lifecycle

    def create_module_accessor_object(self,
            all_mods: dict[str, Any]
    ) -> Namespace:
        """
        For the convenience of modules, dynamically add methods to this
        Lifecycle to invoke each module.
        """

        self._proceed_to_phase(LIFECYCLE.PHASES.CREATE_MODULE_ACCESSORS)

        return Namespace(**{
            name: ModuleAccessor(self, name)
            for name in all_mods
        })

    def configure_environment(self,
            all_mods: dict[str, Any],
            env_parser: EnvironmentParser,
            accessor_object: Any
    ) -> None:
        all_mod_subproc = self._start_all_module_subprocess_for(
            LIFECYCLE.PHASES.ENVIRONMENT_CONFIGURATION
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.ENVIRONMENT_CONFIGURATION)

        for name, module in all_mods.items():
            all_mod_subproc.transition_to(name)

            if hasattr(module, 'configure_env'):
                self._debug(f"Configuring environment for module '{name}'")
                module_env_parser = env_parser.add_parser(name)
                module.configure_env(
                    parser=module_env_parser,
                    root_parser=env_parser,
                    mod=accessor_object
                )

        all_mod_subproc.transition_to_complete()

    def parse_environment(self,
            env_parser: EnvironmentParser,
            all_mod_names: tuple[str, ...],
            cli_env: dict[str, str] | None = None
    ) -> dict[str, Namespace]:
        all_mod_subproc = self._start_all_module_subprocess_for(
            LIFECYCLE.PHASES.ENVIRONMENT_PARSING
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.ENVIRONMENT_PARSING)

        if cli_env is None:
            cli_env = {
                name: value
                for name, value in os.environ.items()
                if name.startswith(self._app_name.upper())
            }

        self._debug(f"Parsing environment:", cli_env)

        envs = {}
        for name in all_mod_names:
            all_mod_subproc.transition_to(name)

            envs[name] = env_parser.parse_env(
                cli_env,
                subparsers_to_use=[name],
                collapse_prefixes=True
            )

        all_mod_subproc.transition_to_complete()
        self._trace(f"Result:", envs)
        return envs

    # NOTE: Grammar for the command line is:
    #         app_name global_opt*
    #         module_name module_opt* module_arg*
    #         (
    #           (('-' | ']') '-' ('-' | '['))
    #           module_name module_opt* module_arg*
    #         )*

    def configure_root_arguments(self,
            all_mods: dict[str, Any],
            envs: dict[str, Namespace],
            arg_parser: ArgumentParser,
            accessor_object: Any
    ) -> None:
        all_mod_subproc = self._start_all_module_subprocess_for(
            LIFECYCLE.PHASES.ROOT_ARGUMENT_CONFIGURATION
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.ROOT_ARGUMENT_CONFIGURATION)

        for name, module in all_mods.items():
            all_mod_subproc.transition_to(name)

            if hasattr(module, 'configure_root_args'):
                self._debug(f"Configuring root arguments for module '{name}'")
                module.configure_root_args(
                    env=envs[name],
                    parser=arg_parser,
                    mod=accessor_object
                )

        all_mod_subproc.transition_to_complete()

    def parse_root_arguments(self,
            arg_parser: ArgumentParser,
            cli_args: list[str] | None = None
    ) -> tuple[Namespace, list[tuple[str, list[str], str | None, str | None]]]:
        self._proceed_to_phase(LIFECYCLE.PHASES.ROOT_ARGUMENT_PARSING)

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
        add_docs_arg(arg_parser)

        # Manually parse remaining args into a set of module arguments, split
        # on any forwarding operator, and prefix with the root arguments so that
        # every module invokation will also have all global args available.
        root_cli_args = cli_args[:-len(remaining_args)]
        module_cli_args_set, forward_types = (
            list_split_match(remaining_args, '[-\\]][-][-\\[]')
        )

        module_full_cli_args_set = [
            (
                module_cli_args[0], # The module name
                [*root_cli_args, *module_cli_args],
                forward_types[i-1] if i > 0 else None,
                forward_types[i] if i < len(module_cli_args_set) - 1 else None
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
        mod_subproc = self._start_module_subprocess_for(
            LIFECYCLE.PHASES.CONFIGURATION
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.CONFIGURATION)

        for name, module in mods.items():
            mod_subproc.transition_to(name)

            if hasattr(module, 'configure'):
                self._debug(f"Configuring module '{name}'")
                module.configure(
                    mod=accessor_object,
                    env=envs[name],
                    args=root_args
                )

        mod_subproc.transition_to_complete()

    def start(self,
            mods: dict[str, Any],
            envs: dict[str, Namespace],
            root_args: Namespace,
            accessor_object: Any
    ) -> tuple[dict[str, Any], list[Exception | KeyboardInterrupt]]:
        mod_subproc = self._start_module_subprocess_for(
            LIFECYCLE.PHASES.STARTING
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.STARTING)

        # TODO: Log exception tracebacks as well as capturing exception objects

        # Lifecycle: Start
        started_modules: dict[str, Any] = {}
        exceptions: list[Exception | KeyboardInterrupt] = []
        for name, module in mods.items():
            mod_subproc.transition_to(name)

            if hasattr(module, 'start'):
                self._debug(f"Starting module '{name}'")
                try:
                    module.start(
                        mod=accessor_object,
                        env=envs[name],
                        args=root_args
                    )
                    started_modules[name] = module
                except (Exception, KeyboardInterrupt) as e:
                    self._error(f"Starting module '{name}' failed")
                    self._error('Stopping all successfully started modules ...')
                    exceptions.append(e)

                    # Don't try to start any more modules if we've already got
                    # an error.
                    break

        if len(exceptions) == 0:
            mod_subproc.transition_to_complete()
        else:
            self._stop_subprocess(LIFECYCLE.PHASES.STARTING)

        return started_modules, exceptions

    def configure_arguments(self,
            all_mods: dict[str, Any],
            envs: dict[str, Namespace],
            arg_parser: ArgumentParser,
            accessor_object: Any
    ) -> None:
        all_mod_subproc = self._start_all_module_subprocess_for(
            LIFECYCLE.PHASES.ARGUMENT_CONFIGURATION
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.ARGUMENT_CONFIGURATION)

        arg_subparsers = None
        for name, module in all_mods.items():
            all_mod_subproc.transition_to(name)

            if hasattr(module, 'configure_args'):
                if arg_subparsers is None:
                    arg_subparsers = arg_parser.add_subparsers(dest="module")

                self._debug(f"Configuring arguments for module '{name}'")
                module_arg_parser = arg_subparsers.add_parser(
                    name,
                    epilog=docs_for(module)
                )
                add_docs_arg(module_arg_parser)
                module.configure_args(
                    env=envs[name],
                    parser=module_arg_parser,
                    mod=accessor_object
                )

        all_mod_subproc.transition_to_complete()

    def parse_arguments(self,
            arg_parser: ArgumentParser,
            module_full_cli_args_set: list[
                tuple[str, list[str], str | None, str | None]
            ]
    ) -> list[tuple[str, Namespace, str | None, str | None]]:
        raw_invokations_sys = self._create_subsystem(
            f'{__name__}:raw_invokations',
            tuple(
                f'{invokation_index}-{name}'
                for invokation_index, (name, _args, _pe_f, _po_f) in
                    enumerate(module_full_cli_args_set)
            )
        )
        raw_invokations_process = self._create_subprocess(raw_invokations_sys)
        self._start_subprocess(
            LIFECYCLE.PHASES.ARGUMENT_PARSING,
            raw_invokations_process
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.ARGUMENT_PARSING)

        module_args_set: list[
            tuple[str, Namespace, str | None, str | None]
        ] = []
        for raw_invokation_index, raw_invokation in enumerate(
                module_full_cli_args_set
        ):
            (
                name,
                module_cli_args,
                pre_forward_type,
                post_forward_type
            ) = raw_invokation

            raw_invokations_process.transition_to(
                f'{raw_invokation_index}-{name}'
            )

            self._debug(
                f"Parsing arguments for module '{name}':",
                module_cli_args
            )
            try:
                module_args = arg_parser.parse_args(module_cli_args)
            except SystemExit as e:
                self._stop_subprocess(LIFECYCLE.PHASES.ARGUMENT_PARSING)
                raise e

            module_args_set.append((
                name,
                module_args,
                pre_forward_type,
                post_forward_type
            ))
            self._trace('Result:', module_args_set[-1])

        raw_invokations_process.transition_to_complete()
        return module_args_set

    def invoke_and_call(self,
            module_args_set: list[
                tuple[str, Namespace, str | None, str | None]
            ],
            envs: dict[str, Namespace],
            start_exceptions: list[Exception | KeyboardInterrupt],
            accessor_object: Any
    ) -> Exception | KeyboardInterrupt | None:
        if len(start_exceptions) > 0:
            self._warning(
                'Skipped running because exception(s) were raised during start'
            )
            return

        invokations_subsystem = self._create_subsystem(
            f'{__name__}:invokations',
            tuple(
                f'{invokation_index}-{name}'
                for invokation_index, (name, _args, _pe_f, _po_f) in enumerate(
                    module_args_set
                )
            )
        )
        invokations_process = self._create_subprocess(invokations_subsystem)
        self._start_subprocess(LIFECYCLE.PHASES.RUNNING, invokations_process)
        self._proceed_to_phase(LIFECYCLE.PHASES.RUNNING)

        leaf_level: int = 1
        forward_carry: list[Any] = [None]
        if not sys.stdin.isatty():
            forward_carry[0] = sys.stdin.read()
            if len(module_args_set) > 0:
                module_args_set[0] = (
                    *module_args_set[0][:2],
                    '---',
                    *module_args_set[0][3:]
                )

        for invokation_index, raw_module_args in enumerate(module_args_set):
            (
                name,
                module_args,
                pre_forward_type,
                post_forward_type
            ) = raw_module_args

            invokations_process.transition_to(f'{invokation_index}-{name}')

            self._info(f"--- Running Module '{name}' ----------")
            try:
                # Eww, using object state instead of args ... yes, but modules
                # have to be able to do this anyway (via the accessors), so it's
                # a precondition of this function that the state needed for
                # `invoke_module()` is set. This asserts that precondition to be
                # true.
                module = self._invoke_module(name)
                if not callable(module):
                    raise LIMARException(f"Module not callable: '{name}'")

                # Call module and collect output(s)
                if pre_forward_type is None or pre_forward_type[2] == '-':
                    pass
                elif pre_forward_type[2] == '[':
                    leaf_level += 1

                self._debug(
                    'All forwarded data'
                    f' (calls are {leaf_level} [white]level(s) deep):',
                    forward_carry
                )

                def call_module(forward_input: Any) -> Any:
                    self._debug('Forwarded input:', forward_input)
                    return module(
                        mod=accessor_object,
                        env=envs[name],
                        args=module_args,
                        forwarded_data=forward_input,
                        output_is_forward=(post_forward_type is not None)
                    )
                forward_carry = self._map_tree_leaves(
                    call_module,
                    forward_carry,
                    leaf_level
                )

                if post_forward_type is None or post_forward_type[0] == '-':
                    pass
                elif post_forward_type[0] == ']':
                    leaf_level -= 1
                    if leaf_level < 1:
                        self._debug(
                            "Requested forwarding contraction without a"
                            " forwarding expansion: wrapping forwarded data in"
                            " a list instead."
                        )
                        leaf_level += 1
                        forward_carry = [forward_carry]

            except (Exception, KeyboardInterrupt) as e:
                self._error(
                    f"Run of module '{name}' failed, aborting further calls"
                )
                self._stop_subprocess(LIFECYCLE.PHASES.RUNNING)
                return e

        invokations_process.transition_to_complete()

        for output in forward_carry:
            if output != None:
                self._print(output)

    def stop(self,
            mods_to_stop: tuple[str, ...],
            mods: dict[str, Any],
            all_mods: dict[str, Any],

            envs: dict[str, Namespace],
            root_args: Namespace,
            start_exceptions: list[Exception | KeyboardInterrupt],
            run_exception: Exception | KeyboardInterrupt | None,
            accessor_object: Any
    ):
        stopping_process = self._start_module_subprocess_for(
            LIFECYCLE.PHASES.STOPPING
        )
        self._proceed_to_phase(LIFECYCLE.PHASES.STOPPING)

        stop_exceptions: list[Exception | KeyboardInterrupt] = []
        for name, module in tuple(mods.items()):
            # Transition to stopping every module to ensure that the phasing
            # system knows when a module would have been stopped, even if no
            # action needs to be taken for some modules, to enable using that
            # module's service methods up until the point that it would have
            # been stopped.
            stopping_process.transition_to(name)
            if name not in mods_to_stop:
                continue

            if hasattr(module, 'stop'):
                self._debug(f"Stopping module '{name}'")
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
                    self._error(f"Stopping module '{name}' failed, SKIPPING.")
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

        stopping_process.transition_to_complete()
        self._proceed_to_phase(LIFECYCLE.PHASES.STOPPED)
        return stop_exceptions

    # 'Friends' (ala C++) of other MM classes
    # --------------------

    def _print(self, *objs):
        if (
            'console' in self._all_mods and
            self._has_mod('console', 'completed', LIFECYCLE.PHASES.STARTING) and
            not self._has_mod('console', 'started', LIFECYCLE.PHASES.STOPPING)
        ):
            self._all_mods['console'].print(*objs)

    def _log(self, *objs,  log_type: str):
        if (
            'log' in self._all_mods and
            self._has_mod('log', 'completed', LIFECYCLE.PHASES.STARTING) and
            not self._has_mod('log', 'started', LIFECYCLE.PHASES.STOPPING)
        ):
            getattr(self._all_mods['log'], log_type)(*objs)

    def _error(self, *objs):
        self._log(*objs, log_type='error')

    def _warning(self, *objs):
        self._log(*objs, log_type='warning')

    def _info(self, *objs):
        self._log(*objs, log_type='info')

    def _debug(self, *objs):
        self._log(*objs, log_type='debug')

    def _trace(self, *objs):
        self._log(*objs, log_type='trace')

    def _invoke_module(self, name: str) -> Any:
        """
        Invoke and return the instance of the module with the given name.

        If the named module has not been initialised, raise a LIMARException.
        """

        if not name in self._all_mods:
            raise LIMARException(
                f"Attempt to invoke uninitialised module '{name}'"
            )

        # Lifecycle: Invoke
        if hasattr(self._all_mods[name], 'invoke'):
            self._debug(f"Invoking module: {name}")
            self._all_mods[name].invoke(
                phase=self._controller.phase(),
                mod=self._accessor_object
            )

        return self._all_mods[name]

    # Phasing
    # --------------------

    # Queries

    # Also a 'friend' of other MM classes
    def _has_mod(self,
            mod_name: str,
            relation: Literal['started', 'completed'],
            phase: Phase
    ):
        assert self._managed_mod_names is not None, '_mod_has_started() run before get_managed_modules()'

        if mod_name in self._managed_mod_names:
            if self._controller.is_after(phase):
                return True
            elif self._controller.is_before(phase):
                return False

            try:
                subproc = self._controller.get_subprocess_for(phase)
            except KeyError:
                # If there is no subprocess, then fall back to the granularity
                # of the primary LIFECYCLE phase.
                return relation == 'started'

            # Some phases use subprocess phase names that aren't module names,
            # in which case this will be False.
            if subproc.phase_system().has_phase(mod_name):
                is_relation_satisfied_for = {
                    'started': subproc.is_at_or_after,
                    'completed': subproc.is_after
                }[relation]
            else:
                # By the rule "a conditional with a false anticedent is true"
                # Less formally, if the module is not processed in this phase:
                # - For the purpose of "Can I now do something with it?", it
                #   hasn't got anything left to do for this phase, so it can
                #   be considered completed.
                # - For the purpose of "Can I now *not* do anything further with
                #   it?", the phase as a whole may have modified global state
                #   that causes it to become unusable, or other dependent
                #   modules may have started this phase causing it to become
                #   possibly-unusable, so it should be considered 'started'
                #   regardless.
                # - Also, considering the module to have completed this phase
                #   but not started it would have been counterintuitive.
                is_relation_satisfied_for = lambda _: True

            return is_relation_satisfied_for(mod_name)

        elif self._parent_lifecycle is not None:
            return (
                self._parent_lifecycle._has_mod(mod_name, relation, phase)
            )

        else:
            raise LIMARException(
                f"Requested the phase of unregistered module '{mod_name}'"
            )

    # Commands - Low-Level Interfaces

    def _create_subsystem(self, name: str, items: tuple[str, ...]):
        return PhaseSystem(
            name,
            ('STARTED', *items, 'COMPLETED'),
            initial_phase='STARTED',
            completed_phase='COMPLETED'
        )

    def _create_subprocess(self, subsystem: PhaseSystem, singular=True):
        return PhasedProcess(subsystem, id_length=(0 if singular else None))

    def _start_subprocess(self, phase: Phase, process: PhasedProcess):
        self._controller.start_subprocess(phase, process)

    def _stop_subprocess(self, phase: Phase):
        self._controller.stop_subprocess(phase, force=True)

    # Commands - High-Level Interfaces

    def _start_module_subprocess_for(self, phase: Phase) -> PhasedProcess:
        """
        Create a new phased process using the `MODULE_PHASE_SYSTEM` and start it
        as a subprocess of the given phase.
        """

        assert self._MODULE_PHASE_SYSTEM is not None, '_start_module_subprocess_for() called before get_managed_modules()'
        module_subprocess = self._create_subprocess(
            self._MODULE_PHASE_SYSTEM, singular=False
        )
        self._start_subprocess(phase, module_subprocess)
        return module_subprocess

    def _start_all_module_subprocess_for(self, phase: Phase) -> PhasedProcess:
        """
        Create a new phased process using the `ALL_MODULE_PHASE_SYSTEM` and
        start it as a subprocess for the given phase.
        """

        assert self._ALL_MODULE_PHASE_SYSTEM is not None, '_start_all_module_subprocess_for() called before get_managed_modules()'
        all_module_subprocess = self._create_subprocess(
            self._ALL_MODULE_PHASE_SYSTEM, singular=False
        )
        self._start_subprocess(phase, all_module_subprocess)
        return all_module_subprocess

    def _proceed_to_phase(self, phase: Phase):
        self._controller.transition_to(phase)
        self._info(f"{'-'*5} {phase} {'-'*(43-len(phase))}")

    # Utils
    # --------------------

    def _map_tree_leaves(self,
            fn: Callable[[Any], Any],
            data: Any,
            levels: int
    ) -> Any:
        """
        Clone the structure of data to one less than the given number of
        levels deep, then apply fn to each item at levels deep. If levels is 1,
        then this is equivalent to `map(fn, data)`. If levels is 0, then this is
        equivalent to `fn(data)`.
        """

        # A negative number of levels are considered to mean "the level to map
        # at was reached before this function was called", so do nothing.
        if levels < 0:
            output = data
        elif levels == 0:
            output = fn(data)
        else:
            if isinstance(data, MutableMapping):
                output = copy(data)
                for key, value in output.items():
                    output[key] = self._map_tree_leaves(fn, value, levels-1)
            elif isinstance(data, Mapping):
                # TODO: Is there a way of making a new instance of the same type?
                output = {
                    key: self._map_tree_leaves(fn, value, levels-1)
                    for key, value in data.items()
                }
            elif isinstance(data, MutableSequence):
                output = copy(data)
                for i, item in enumerate(output):
                    output[i] = self._map_tree_leaves(fn, item, levels-1)
            elif isinstance(data, Sequence):
                # TODO: Is there a way of making a new instance of the same type?
                output = tuple(
                    self._map_tree_leaves(fn, item, levels-1)
                    for item in data
                )
            else:
                raise LIMARException(
                    f"Cannot map non-sequence '{data}' at level '{levels}'"
                    " using function '{fn.__name__}'"
                )
        return output

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
    register a module after the registration phase will raise a LIMARException.

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

    Note: Circular or unregistered dependencies will raise a LIMARException.

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

    def __init__(self, app: Callable, app_name: str, mm_cli_args: list[str] | None = None):
        self._app = app
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
            self._app,
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
            app=self._app,
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
                    raise LIMARException(
                        f"Python module '{py_module_name}' in __all__ failed to"
                        " load"
                    ) from e

                try:
                    mm_module = getattr(py_module, mm_class_name)
                except AttributeError as e:
                    raise LIMARException(
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
