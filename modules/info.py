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
from typing import Any

from modules.command_utils.command_transformer import (
    Subquery,
    SystemSubcommand,
    LimarSubcommand
)
from modules.manifest import Item, ItemSet

Entity = dict[str, str]

INFO_LIFECYCLE = PhaseSystem(
    f'{__name__}:lifecycle',
    (
        'INITIALISE',
        'GET',
        'TABULATE',
        'RENDER'
    ),
    initial_phase='INITIALISE'
)

# TODO/FIXME: This is really a dependency graph of *LIMAR
#   invokations*, as *identified by their arguments*, that are
#   *cacheable* (all three are essential characteristics)
#
#   Also, if:
#   - A and B both depend on C, and therefore run C (forward dep)
#   - Calls to C invalidates the caches for A and B (reverse dep)
#   - Cache invalidation triggers calls to the dependants of C
#     (reactive forward dep)
#   Then you will end up with an infinite cycle: Running A
#   invalidates B, which runs B, which invalidates A, which runs A.
#   More precisely:
#   1.  Start A
#   2.  Start/Run C (because of A)
#   3.  Invalidate A and B (because of C)
#   4.  Run A
#   5.  Check which caches are invalid and need update = B
#   6.  Start B (because it needs update)
#   7.  Start/Run C (because of B)
#   8.  Invalidate A and B (Because of C)
#   9.  Check which caches are invalid and need update = A
#   10. Start A
#      ...
#   This is why proactive running of invalid caches (step 5 + 9) is
#   dangerous and should not be done. You should only invalidate the
#   cache, not cause it to update unless asked to. Also,
#   de-duplication can avoid this trap - run C once for both, and
#   you don't get the cycle.

# ------------------------------------------------------------------------------

# - Sort commands into topological order
# - Insert commands into queue in that order, taking note of which ones were
#   directly requested
#   - Note: Don't need to de-dup here, because queries fetched from cache aren't
#           invalidated.
# - Process each command in the queue (in topological order, per priority),
#   fetching from cache if possible.

class CommandRunner:
    def __init__(self,
            command_items: ItemSet,
            command_items_id: str,
            mod: Namespace
    ):
        # Tools
        self._mod = mod
        self._cache_utils = CacheUtils(mod)
        self._command_tr = CommandTransformer()

        # Static
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
            self._command_items,
            self._command_order,

            self,
            self._mod,
            self._cache_utils
        )

    # Command Runners
    # --------------------------------------------------

    def run_query(self, ref: str, query) -> list[Entity]:
        """
        Run the given query whose containing item has the given ref and return
        the output.
        """

        # Evaluate parameters to arguments
        query_args: dict[Subquery, str] = {}
        for param in query['parameters']:
            query_args[param] = self._invoke_limar_module(*param)['stdout']
            if not isinstance(query_args[param], str):
                raise LIMARException(
                    f"Evaluation of query parameter {{{{"
                    f" {self._command_tr.format_text_limar_subcommand(param)}"
                    " }}}} did not return a string. Cannot interpolate"
                    " non-string values into the requested query."
                )
        self._mod.log.debug('Query arguments:', query_args)

        self._mod.log.info(f"Running query '{ref}'")
        self._mod.log.debug(
            f"  Which is: '{self._command_tr.format_text(query)}'"
        )

        # Run subcommands using corresponding runner
        SUBCOMMAND_RUNNERS = {
            'system': self._run_system_subcommand,
            'limar': self._run_limar_subcommand
        }
        query_outputs: list[dict[str, Any]] = []
        for subcommand in query['subcommands']:
            try:
                query_outputs.append(
                    SUBCOMMAND_RUNNERS[subcommand['type']](
                        subcommand['subcommand'], query_args, subcommand
                    )
                )
                self._mod.log.trace('Command output:', query_outputs[-1])
            except KeyError:
                raise LIMARException(
                    f"Unknown subcommand type '{subcommand['type']}' for"
                    f" subcommand '{subcommand['subcommand']}' in query '{ref}'"
                )
        self._mod.log.trace('Query subcommands output:', query_outputs)

        # Transform the output using the command's parse expression
        self._mod.log.trace('Query parser:', query['parse'])
        query_output: list[Entity] = self._mod.tr.query(
            query['parse'],
            query_outputs,
            lang='jq',
            first=True
        )
        self._mod.log.debug('Query output:', query_output)
        return query_output

    # TODO: Implement this
    def run_action(self, ref, action) -> list[Entity]:
        raise NotImplementedError(
            f"Actions: Attempted to run action '{ref}'"
        )

    # Subcommand and Subquery Runners
    # --------------------------------------------------

    def _run_system_subcommand(self,
        system_subcommand: SystemSubcommand,
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
            limar_subcommand: LimarSubcommand,
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
    ) -> dict[str, Any]:
        subcommand_output: Any = None
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
            command_items: ItemSet,
            command_order: tuple[str, ...],

            _command_runner: CommandRunner,
            _mod: Namespace,
            _cache_utils: CacheUtils
    ):
        # Tools
        self._command_runner = _command_runner
        self._mod = _mod
        self._cache_utils = _cache_utils

        # Static
        self._subject = subject
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

        COMMAND_RUNNERS = {
            'query': self._command_runner.run_query,
            'action': self._command_runner.run_action
        }

        command_outputs: list[tuple[ Item, list[Entity] ]] = []
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
            if command_ref in self._directly_requested:
                command_outputs.append((command_item, output))

        self._mod.log.debug('Query outputs:', command_outputs)
        return self._merge_entities(command_outputs, self._subject)

    # Utils
    # --------------------------------------------------

    def _key_for_ref(self, command_ref):
        return self._cache_utils.key(
            self._command_items[command_ref]['command']['type'],
            command_ref
        )

    def _merge_entities(self,
            query_outputs: list[tuple[ Item, list[Entity] ]],
            subject: list[str]
    ) -> dict[str | tuple[str, ...], Entity]:
        merged_query_output: dict[str | tuple[str, ...], Entity] = {}
        for item, entities in query_outputs:
            self._mod.log.trace(
                f"Subjects for item '{item['ref']}'", item['subjects']
            )
            try:
                id_fields = tuple(item['subjects'][tag] for tag in subject)
            except KeyError as e:
                raise LIMARException(
                    f"Query '{item['ref']}' missing field mapping for subject"
                    f" '{e.args[0]}'."
                    " This is likely to be an issue with the command manifest."
                )
            for entity_data in entities:
                try:
                    id = tuple(entity_data[id_field] for id_field in id_fields)
                except KeyError as e:
                    self._mod.log.error(
                        'Entity that caused the error below:', entity_data
                    )
                    raise LIMARException(
                        f"Above result of query '{item['ref']}' missing"
                        f" identity field '{e.args[0]}' mapped from subject"
                        f" '{subject[id_fields.index(e.args[0])]}'."
                        " This is likely to be an issue with the command"
                        " manifest."
                    )

                # If there is only one item in the composite key, then unwrap
                # it. Neither jq nor yaql support indexing into dictionaries
                # with tuple keys. Unwrapping permits queries (and subqueries)
                # to be indexed into to improve performance when joining data
                # about different subjects.
                if len(id) == 1:
                    id = id[0]

                if id not in merged_query_output:
                    merged_query_output[id] = {}
                merged_query_output[id].update(entity_data)

        return merged_query_output

class InfoModule:
    """
    MM module to manage retreiving and displaying information.
    """

    # Lifecycle
    # --------------------------------------------------

    def dependencies(self):
        return ['log', 'phase', 'manifest', 'command-manifest']

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
        parser.add_argument('-q', '--query',
            action='store_true', default=False,
            help="""Show information about the given subject.""")

        parser.add_argument('subject', metavar='SUBJECT', nargs='+',
            help="""Show information about the given subject.""")

        # Subcommands / Resolve Item Set - Output Controls
        mod.phase.configure_phase_control_args(parser)

    def configure(self, *, mod: Namespace, **_):
        mod.phase.register_system(INFO_LIFECYCLE)

    def start(self, *, mod: Namespace, **_):
        self._mod = mod

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
            commands,
            command_manifest_digest,
            mod
        )

    def __call__(self, *,
            mod: Namespace,
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
            if args.query is True:
                output = self.query(args.subject[0])
            else:
                output = self.get(args.subject)

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
    def get(self,
            subject: list[str]
    ) -> dict[str | tuple[str, ...], Entity]:
        """
        Get the list of the queries in the command manifest that match the given
        command_spec, then return the indexed list of entities returned by those
        queries.
        """

        self._mod.log.info('Getting info for subject:', subject)

        # Get matching commands to execute
        set_ref = 'info-query-'+''.join(random.choices(string.hexdigits, k=32))
        set_spec = ' & '.join(subject)
        # FIXME: Yes, I know this is an injection attack waiting to happen, eg.
        #          get(['unlikely] | something_evil | [unlikely'])
        self._mod.manifest.declare_item_set(set_ref, f'query & [{set_spec}]')
        matched_queries: ItemSet = self._mod.manifest.get_item_set(set_ref)
        self._mod.log.debug(f'Matched manifest items:', matched_queries)

        # Ensure all matched commands are queries
        for item in matched_queries.values():
            if item['command']['type'] != 'query':
                raise LIMARException(
                    f"The info subject '{subject}' matched a non-query command"
                    f" '{item['ref']}'. Are you using the correct subject, and"
                    " are the tags correct in the command manifest? Run in"
                    " debug mode (`lm -vvv ...`) to see the full list of"
                    " matched manifest items."
                )

        # Process the queries
        batch = self._command_runner.new_batch(subject)
        batch.add(*matched_queries.keys())
        return batch.process()

    @ModuleAccessor.invokable_as_service
    def query(self, ref, subject=None):
        item = self._mod.manifest.get_item(ref)

        if subject is None:
            if 'primarySubject' in item:
                subject = [item['primarySubject']]
            else:
                subject = list(item['subjects'].keys())

        if (
            'query' not in item['tags'] or
            'command' not in item or
            'type' not in item['command'] or
            item['command']['type'] != 'query'
        ):
            raise LIMARException(
                f"The query ref '{ref}' matched a non-query command"
                f" '{item['ref']}'. Are you using the correct ref, and are the"
                " tags correct in the command manifest? Run in debug mode"
                " (`lm -vvv ...`) to see the matched item."
            )

        batch = self._command_runner.new_batch(subject)
        batch.add(ref)
        return batch.process()
