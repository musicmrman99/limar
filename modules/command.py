from graphlib import CycleError, TopologicalSorter
from queue import Empty, PriorityQueue
import random
import string
import subprocess

from core.exceptions import LIMARException
from core.modulemanager import ModuleAccessor
from core.modules.phase_utils.phase_system import PhaseSystem
from modules.command_utils.command_transformer import CommandTransformer
from modules.command_utils.cache_utils import CacheUtils

# Types
from argparse import ArgumentParser, Namespace
from typing import Any, Callable, TypedDict

from modules.command_utils.command_types import (
    Command, QueryCommand, ActionCommand,
    LimarSubcommandData, SystemSubcommandData, Subquery,
    Entity
)
from modules.manifest import ItemSet

INFO_LIFECYCLE = PhaseSystem(
    f'{__name__}:lifecycle',
    (
        'INITIALISE',
        'GET',
        'SUBJECT',
        'RUN',
        'TABULATE',
        'RENDER'
    ),
    initial_phase='INITIALISE'
)

class SystemSubcommandResult(TypedDict):
    status: int
    stdout: Any
    stderr: str

class LimarSubcommandResult(TypedDict):
    status: int
    stdout: Any # FIXME: Technically `Any | None`
    stderr: Exception | None

SubcommandResult = SystemSubcommandResult | LimarSubcommandResult

class CommandRunner:
    def __init__(self,
            subject_items: ItemSet,
            command_items: ItemSet,
            command_items_id: str,
            mod: Namespace
    ):
        # Tools
        self._mod = mod
        self._cache_utils = CacheUtils(mod)
        self._command_tr = CommandTransformer()

        # Static
        self._subject_items = subject_items
        self._command_items = command_items

        # Build the partially ordered dep list across the whole command item set
        dependency_graph = self._cache_utils.with_caching(
            self._cache_utils.key(
                "command_runner", f"dependency_graph.{command_items_id}"
            ),
            lambda: {
                ref: item['command']['dependencies']
                for ref, item in command_items.items()
            }
        )

        sorter = TopologicalSorter(dependency_graph)
        try:
            self._command_order = tuple(sorter.static_order())
        except CycleError as e:
            raise LIMARException(
                f"Cannot resolve dependencies while runnign commands due to"
                f" cycle '{e.args[1]}'"
            )

    # Batch Management
    # --------------------------------------------------

    def new_batch(self, subject) -> "CommandBatch":
        return CommandBatch(
            subject,
            self._subject_items,
            self._command_items,
            self._command_order,

            self,
            self._mod,
            self._cache_utils,
            self._command_tr
        )

    # Command Runners
    # --------------------------------------------------

    def run_query(self, ref: str, query: QueryCommand) -> list[Entity]:
        """
        Run the given query whose containing item has the given ref and return
        the output.
        """

        command_outputs = self.run_command(ref, query)

        # Transform the output using the query's parse expression
        self._mod.log.trace('Query parser:', query['parse'])
        query_output: list[Entity] = self._mod.tr.query(
            query['parse'],
            command_outputs,
            lang='jq',
            first=True
        )
        self._mod.log.debug('Query output:', query_output)
        return query_output

    def run_action(self, ref: str, action: ActionCommand) -> list[Entity] | None:
        """
        Run the given query whose containing item has the given ref and return
        the output.
        """

        command_outputs = self.run_command(ref, action)

        # Transform the output using the action's parse expression if it has one
        action_output: list[Entity] | None
        if 'parse' in action:
            self._mod.log.trace('Action parser:', action['parse'])
            action_output = self._mod.tr.query(
                action['parse'],
                command_outputs,
                lang='jq',
                first=True
            )
            self._mod.log.debug('Action output:', action_output)
        else:
            action_output = None
            self._mod.log.debug(
                f"Action '{ref}' has no parse expression, so ignoring its"
                " output"
            )

        return action_output

    def run_command(self, ref: str, command: Command) -> list[Any]:
        """
        Run the given command whose containing item has the given ref and return
        the output.
        """

        # Evaluate parameters to arguments
        command_args: dict[Subquery, str] = {}
        for param in command['parameters']:
            command_args[param] = self._invoke_limar_module(*param)['stdout']
            if not isinstance(command_args[param], str):
                raise LIMARException(
                    f"Evaluation of command parameter {{{{"
                    f" {self._command_tr.format_text_limar_subquery(param)}"
                    " }}}} did not return a string. Cannot interpolate"
                    " non-string values into the requested command."
                )
        self._mod.log.debug('Command arguments:', command_args)

        self._mod.log.info(f"Running {command['type']} command '{ref}'")
        self._mod.log.debug(
            f"  Which is: '{self._command_tr.format_text(command)}'"
        )

        # Run subcommands using corresponding runner
        SUBCOMMAND_RUNNERS = {
            'system': self._run_system_subcommand,
            'limar': self._run_limar_subcommand
        }
        command_outputs: list[dict[str, Any]] = []
        for subcommand in command['subcommands']:
            try:
                command_outputs.append(
                    SUBCOMMAND_RUNNERS[subcommand['type']](
                        subcommand['subcommand'], command_args, subcommand
                    )
                )
                self._mod.log.trace('Command output:', command_outputs[-1])
            except KeyError:
                raise LIMARException(
                    f"Unknown subcommand type '{subcommand['type']}' for"
                    f" subcommand '{subcommand['subcommand']}' in query '{ref}'"
                )
        self._mod.log.trace('Subcommands output:', command_outputs)

        return command_outputs

    # Subcommand and Subquery Runners
    # --------------------------------------------------

    def _run_system_subcommand(self,
        system_subcommand: SystemSubcommandData,
        data: dict[Subquery, str] | None = None,
        options: dict[str, Any] | None = None
    ) -> Any:
        if data is None:
            data = {}

        final_options = {
            'allowedToFail': False
        }
        if options is not None:
            final_options.update(options)

        args = self._command_tr.interpolate_grouped(
            system_subcommand, data
        )
        self._mod.log.trace('Subcommand split:', args)

        exception = None
        try:
            subproc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = subproc.communicate()
            subcommand_status = subproc.returncode

        except subprocess.CalledProcessError as e:
            exception = e
            subcommand_status = exception.returncode

        if subcommand_status != 0 and not final_options['allowedToFail']:
            raise LIMARException(
                f"Process run with arguments {args} failed"
                f" with return code '{subcommand_status}'."
            ) from exception

        return {
            'status': subcommand_status,
            'stdout': stdout.decode().strip(),
            'stderr': stderr.decode().strip()
        }

    def _run_limar_subcommand(self,
            limar_subcommand: LimarSubcommandData,
            data=None,
            options: dict[str, Any] | None = None
    ) -> Any:
        if data is None:
            data = {}

        final_options = {
            'allowedToFail': False
        }
        if options is not None:
            final_options.update(options)

        module, method, args_raw, jqTransform, pqTransform = limar_subcommand
        self._mod.log.debug(
            'Running LIMAR subcommand:',
            self._command_tr.format_text_limar_subcommand(limar_subcommand)
        )

        # Interpolate args
        args = self._command_tr.interpolate_grouped(args_raw, data)
        self._mod.log.debug(
            'Evaluated LIMAR subcommand:',
            # Not technically a subquery, but is kind-of equivalent to one
            self._command_tr.format_text_limar_subquery(
                (module, method, args, jqTransform, pqTransform)
            )
        )

        # LIMAR subcommands are the same process as parameter evaluation, but
        # with support for one level of nesting in the arguments.
        output = self._invoke_limar_module(
            module, method, args, jqTransform, pqTransform
        )

        if output['status'] != 0 and not final_options['allowedToFail']:
            raise LIMARException(
                f"Process run with arguments {args} failed with return code"
                f" '{output['status']}'."
            ) from output['stderr']

        return output

    def _invoke_limar_module(self,
            module: str,
            method: str,
            args: tuple[str, ...],
            jq_transform: str | None,
            pq_transform: str | None
    ) -> LimarSubcommandResult:
        subcommand_output: Any | None = None
        subcommand_error: Exception | None = None

        # Invoke LIMAR service
        # Should only be run if the service method being invoked isn't a
        # query/command, or if it doesn't have caching enabled.
        try:
            limar_service_method = (
                getattr(getattr(self._mod, module), method)
            )
            subcommand_output = limar_service_method(*args)
            subcommand_error = None
            self._mod.log.debug(
                'LIMAR invokation output (pre-transform): ',
                subcommand_output
            )
        except Exception as e:
            subcommand_error = e
            self._mod.log.error(
                'LIMAR invokation error (not transformed): ',
                subcommand_error
            )

        # Process LIMAR invokation output
        if subcommand_error is None:
            if jq_transform is not None:
                subcommand_output = self._mod.tr.query(
                    jq_transform, subcommand_output, lang='jq', first=True
                )
            elif pq_transform is not None:
                subcommand_output = self._mod.tr.query(
                    pq_transform, subcommand_output, lang='yaql'
                )
            self._mod.log.trace(
                'LIMAR invokation output (post-transform): ',
                subcommand_output
            )

        return {
            'status': 0 if subcommand_error is None else 1,
            'stdout': subcommand_output,
            'stderr': subcommand_error
        }

class CommandBatch:
    def __init__(self,
            subject: list[str],
            subject_items: ItemSet,
            command_items: ItemSet,
            command_order: tuple[str, ...],

            _command_runner: CommandRunner,
            _mod: Namespace,
            _cache_utils: CacheUtils,
            _command_tr: CommandTransformer
    ):
        # Tools
        self._command_runner = _command_runner
        self._mod = _mod
        self._cache_utils = _cache_utils
        self._command_tr = _command_tr

        # Static
        self._subject = subject
        self._subject_items = subject_items
        self._command_items = command_items
        self._command_order = command_order

        # State
        self._run_queue = PriorityQueue()
        self._directly_requested = set()
        # NOTE: Assumes that the batch processor caches command output by ref
        #       only. This could cause issues for commands that use dynamic
        #       input.
        self._cacheable: set[str] = set()

    def add(self, *refs):
        """
        Add the commands for all given refs to the batch.

        For any commands (or their transitive dependencies) that are cacheable,
        also add them (without duplicates) to the beginning of the command queue
        in dependency order to ensure caches are invalidated and regenerated
        correctly.

        Must not be called while `process()` is running.
        """

        for ref in refs:
            if ref in self._directly_requested:
                continue
            self._directly_requested.add(ref)

            item = self._command_items[ref]

            # Add directly requested command to the queue (de-dup if cacheable)
            is_cacheable = self._cache_utils.is_enabled(item)
            if not is_cacheable or ref not in self._cacheable:
                self._run_queue.put((
                    self._command_order.index(ref),
                    ref,
                    item
                ))
            if is_cacheable:
                self._cacheable.add(ref)

            # Add cacheable transitive deps to the queue to ensure correct cache
            # invalidation order.
            for dep_ref in item['command']['transitiveDependencies']:
                dep_item = self._command_items[dep_ref]
                if (
                    self._cache_utils.is_enabled(dep_item) and
                    dep_ref not in self._cacheable
                ):
                    self._run_queue.put((
                        self._command_order.index(dep_ref),
                        dep_ref, dep_item
                    ))
                    self._cacheable.add(dep_ref)

    def process(self) -> dict[str | tuple[str, ...], Entity]:
        """
        Process the commands currently on the queue and return the results of
        those directly requested as an indexed list of entities.

        The returned entities are keyed by the ID values of the batch's subject.
        This key is singular (a single string) if the subject contains one item,
        or composite (a tuple of strings) if the subject contains more than one
        item.

        Must be called synchronously, blocking all calls to `add()` and
        `process()` on this or any other batch.
        """

        COMMAND_RUNNERS: dict[str, Callable[..., Any]] = {
            'query': self._command_runner.run_query,
            'action': self._command_runner.run_action
        }

        command_outputs: list[Entity] = []
        refs_with_batch_retention: set[str] = set()
        while True:
            try:
                (
                    _, command_ref, command_item
                ) = self._run_queue.get(block=False)
            except Empty:
                self._directly_requested = set()
                self._cacheable = set()
                self._mod.cache.delete(
                    *map(self._key_for_ref, refs_with_batch_retention)
                )
                break

            command = command_item['command']
            cacheable = self._cache_utils.is_enabled(command_item)
            cache_retention = self._cache_utils.retention_of(command_item)

            # Mark items with batch retention
            if cacheable and cache_retention == 'batch':
                refs_with_batch_retention.add(command_ref)

            # Run command (or fetch from cache)
            runner = COMMAND_RUNNERS[command['type']]
            output: list[Entity]
            if not cacheable:
                output = runner(command_ref, command)
            else:
                # No point in invalidating the caches of dependant commands
                # if this one is not cacheable, as those commands are not
                # cacheable either.
                output = self._cache_utils.with_caching(
                    self._key_for_ref(command_ref),
                    runner, [command_ref, command],
                    invalid_on_run=(
                        map(self._key_for_ref, command['transitiveDependants'])
                    )
                )

            # Collate output
            if command_ref in self._directly_requested and output is not None:
                command_outputs.extend(output)

        self._mod.log.debug('Query outputs:', command_outputs)
        self._mod.log.trace("Merging entities using subject:", self._subject)
        return self._command_tr.merge_entities(
            self._subject_items,
            command_outputs,
            self._subject
        )

    # Utils
    # --------------------------------------------------

    def _key_for_ref(self, command_ref):
        return self._cache_utils.key(
            self._command_items[command_ref]['command']['type'],
            command_ref
        )

class CommandModule:
    """
    MM module for running commands and managing their I/O.
    """

    # Lifecycle
    # --------------------------------------------------

    def __init__(self):
        self._command_tr = CommandTransformer()

    def dependencies(self):
        return ['log', 'cache', 'tr', 'phase', 'manifest', 'command-manifest']

    def aliases(self):
        return ['show', 'run']

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
        parser.add_argument('-c', '--command', metavar='COMMAND_REF',
            action='append', default=[],
            help="""
            Run the given command instead of all commands matched by the given
            subject. This option may be given multiple times to run several
            commands. If this option is given at least once, the subject may be
            omitted, in which case the union of primary subjects (or all
            subjects, where a primary subject is not declared) of all specified
            commands will be used instead.
            """)

        parser.add_argument('subject', metavar='SUBJECT', nargs='*',
            help="""The subject to show information about.""")

        # Output Controls
        mod.phase.configure_phase_control_args(parser)

    def configure(self, *, mod: Namespace, **_):
        mod.phase.register_system(INFO_LIFECYCLE)

    def start(self, *, mod: Namespace, **_):
        self._mod = mod

        subject_items = self._mod.manifest.get_item_set('subject')
        subjects = {
            ref: item
            for ref, item in subject_items.items()
            # Skip anything that wasn't set and didn't fail validation due to
            # double-underscore tags.
            if 'id' in item
        }
        self._subject_mapping = self._command_tr.subject_mapping_from(subjects)

        command_manifest_digest = mod.manifest.get_manifest_digest('command')
        command_items: ItemSet = mod.manifest.get_item_set('command')
        commands = {
            ref: item
            for ref, item in command_items.items()
            # Skip anything that wasn't set and didn't fail validation due to
            # double-underscore tags.
            if 'command' in item
        }

        self._command_runner = CommandRunner(
            subjects,
            commands,
            command_manifest_digest,
            mod
        )

    def __call__(self, *,
            mod: Namespace,
            invoked_as: str,
            args: Namespace,
            forwarded_data: Any,
            output_is_forward: bool,
            **_
    ):
        # Set up phase process and a common transition function
        # WARNING: THIS MUTATES STATE, even though it's used in `if` statements
        transition_to_phase = mod.phase.create_process(INFO_LIFECYCLE, args)

        output: Any = forwarded_data

        if transition_to_phase(INFO_LIFECYCLE.PHASES.GET):
            if len(args.command) > 0:
                command_items = mod.manifest.get_items(args.command)
            else:
                command_items = self.commands_with_subject(args.subject)
            output = command_items

        if transition_to_phase(INFO_LIFECYCLE.PHASES.SUBJECT):
            allowed_types = [
                *(['query'] if invoked_as == 'show' else []),
                *(['action'] if invoked_as == 'run' else [])
            ]
            subject = self.effective_subject_for(command_items, args.subject)
            output = subject

        if transition_to_phase(INFO_LIFECYCLE.PHASES.RUN):
            output = self.run(command_items, subject, allowed_types)

        # Format
        if transition_to_phase(
            INFO_LIFECYCLE.PHASES.TABULATE, not output_is_forward
        ):
            output = mod.tr.tabulate(output.values(), obj_mapping='all')

        if transition_to_phase(
            INFO_LIFECYCLE.PHASES.RENDER, not output_is_forward
        ):
            output = mod.tr.render_table(output, has_headers=True)

        # Forward
        return output

    # Invokation
    # --------------------------------------------------

    @ModuleAccessor.invokable_as_service
    def commands_with_subject(self,
            given_subject: list[str]
    ) -> ItemSet:
        """Return all commands with the given subject."""

        self._mod.log.debug(
            'Resolving subject (keeping unrecognised):',
            given_subject
        )
        partially_resolved_subject = self._command_tr.resolved_subject(
            self._subject_mapping, given_subject,
            keep_unrecognised=True
        )

        self._mod.log.info(
            'Getting commands for resolved subject (with unrecognised kept):',
            partially_resolved_subject
        )
        set_ref = 'command-run-'+''.join(random.choices(string.hexdigits, k=32))
        # FIXME: Yes, I know this is an injection attack waiting to happen, eg.
        #          get(['unlikely] | something_evil | [unlikely'])
        self._mod.manifest.declare_item_set(
            set_ref,
            f"[{' & '.join(partially_resolved_subject)}]"
        )
        return self._mod.manifest.get_item_set(set_ref)

    @ModuleAccessor.invokable_as_service
    def effective_subject_for(self,
            command_items: ItemSet,
            given_subject: list[str] | None = None
    ) -> list[str]:
        """
        Return the effective subject for the given command items.

        Return the given subject filtered for elements declared as a subject of
        at least one of the given commands.

        If the given_subject is None or empty, then return the primary subject
        of the commands instead.
        """

        if given_subject is None or len(given_subject) == 0:
            subject = self._command_tr.primary_subject_of(command_items)
            self._mod.log.debug(
                'Effective subject from primary subject:', subject
            )
        else:
            self._mod.log.debug('Resolving subject:', given_subject)
            resolved_subject = self._command_tr.resolved_subject(
                self._subject_mapping, given_subject,
                keep_unrecognised=False
            )
            self._mod.log.debug('Resolved subject:', resolved_subject)
            subject = self._command_tr.subject_in(
                command_items, resolved_subject
            )
            self._mod.log.debug(
                'Effective subject from given subject:', subject
            )

        return subject

    @ModuleAccessor.invokable_as_service
    def run_refs(self, *command_refs: str):
        """Run the commands with the given refs."""

        command_items = self._mod.manifest.get_items(command_refs)
        subject = self.effective_subject_for(command_items)
        return self.run(command_items, subject)

    @ModuleAccessor.invokable_as_service
    def run(self,
            command_items: ItemSet,
            subject: list[str],
            allowed_types: list[str] | None = None
    ) -> dict[str | tuple[str, ...], Entity]:
        """
        Run the given commands, using the given subject to index the resulting
        indexed list of entities.
        """

        self._mod.log.debug('Running command items:', command_items)

        for command_ref, command_item in command_items.items():
            if not self._command_tr.is_runnable(command_item):
                raise LIMARException(
                    f"Attempt to run unimplemented command '{command_ref}'. Run"
                    " in debug mode (`lm -vvv ...`) to see the full command"
                    " item."
                )

            if allowed_types is not None and len(allowed_types) > 0:
                command_type = self._command_tr.command_type_of(command_item)
                if command_type not in allowed_types:
                    raise LIMARException(
                        f"Attempt to run command '{command_item['ref']}' that"
                        " is not of any type in the list of allowed types for"
                        f" this run (was '{command_type}'; allowed:"
                        f" {allowed_types}). Run in debug mode (`lm -vvv ...`)"
                        " to see the matched item."
                    )

        batch = self._command_runner.new_batch(subject)
        batch.add(*(command_ref for command_ref in command_items.keys()))
        return batch.process()
