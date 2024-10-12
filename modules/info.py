from graphlib import CycleError, TopologicalSorter
import random
import string
import shlex
import subprocess

from core.exceptions import LIMARException
from core.modulemanager import ModuleAccessor
from core.modules.phase_utils.phase_system import PhaseSystem
from modules.command_utils.query import QueryFormatter

# Types
from argparse import ArgumentParser, Namespace
from typing import Any

from modules.command_utils.query import (
    LimarCommand,
    Interpolatable,
    InterpolatableLimarCommand
)
from modules.manifest import Item, ItemSet

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

class InfoModule:
    """
    MM module to manage retreiving and displaying information.
    """

    # Lifecycle
    # --------------------------------------------------

    def __init__(self):
        self._dependency_graph: dict[str, set[str]] | None = None
        self._reverse_dependency_graph: dict[str, set[str]] | None = None

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
        query_items = None
 
        try:
            self._dependency_graph = mod.cache.get(
                f'info.dependency_graph.{command_manifest_digest}.pickle'
            )
        except KeyError:
            if query_items is None:
                query_items = mod.manifest.get_item_set('query')

            self._dependency_graph = {
                ref: {
                    param[2][0] # 1st item of info.get() args
                    for param in item['command']['parameters']
                }
                for ref, item in query_items.items()
            }
            mod.cache.set(
                f'info.dependency_graph.{command_manifest_digest}.pickle',
                self._dependency_graph
            )
        mod.log.debug(
            'dependency graph:',
            self._dependency_graph
        )

        try:
            self._reverse_dependency_graph = mod.cache.get(
                f'info.reverse_dependency_graph.{command_manifest_digest}.pickle'
            )
        except KeyError:
            if query_items is None:
                query_items = mod.manifest.get_item_set('query')

            self._reverse_dependency_graph = {
                ref: {
                    item['ref']
                    for _, item in query_items.items()
                    # TODO: Only supports `info.query(<ref>)` for now
                    if ('info', 'query', (ref,)) in (
                        param[0:3] for param in item['command']['parameters']
                    )
                }
                for ref, _ in query_items.items()
            }
            mod.cache.set(
                f'info.reverse_dependency_graph.{command_manifest_digest}.pickle',
                self._reverse_dependency_graph
            )
        mod.log.debug(
            'reverse dependency graph:',
            self._reverse_dependency_graph
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
    ) -> dict[str | tuple[str, ...], dict[str, str]]:
        """
        Get the list of the queries in the command manifest that match the given
        command_spec, then return the indexed list of objects returned by those
        queries.
        """

        assert self._dependency_graph is not None, f'{self.get.__name__}() called before {self.start.__name__}()'

        self._mod.log.info('Getting info for subject:', subject)

        # Get matching commands to execute
        set_ref = 'info-query-'+''.join(random.choices(string.hexdigits, k=32))
        set_spec = ' & '.join(subject)
        # FIXME: Yes, I know this is an injection attack waiting to happen, eg.
        #          get('unlikely] | something_evil | [unlikely')
        self._mod.manifest.declare_item_set(set_ref, f'query & [{set_spec}]')
        matched_queries: ItemSet = self._mod.manifest.get_item_set(set_ref)
        self._mod.log.debug(f'Matched manifest items:', matched_queries)

        # Sort commands into topological order to avoid issues with dependency
        # cache invalidation.
        # TODO: TopologicalSorter can also be used to run the commands in
        # parallel by following its other usage pattern. See:
        # https://docs.python.org/3/library/graphlib.html
        sorter = TopologicalSorter({
            ref: list(self._dependency_graph[ref])
            for ref in matched_queries.keys()
        })
        try:
            query_sort_order = tuple(sorter.static_order())
        except CycleError as e:
            raise LIMARException(
                f"Cannot resolve dependencies for subject '{subject}' due to"
                f" cycle '{e.args[1]}'"
            )
        self._mod.log.debug(
            f'Query run order (including dependencies):', query_sort_order
        )

        matched_queries_sorted: ItemSet = {}
        for ref in query_sort_order:
            # Don't run dependent queries twice
            # FIXME: ... but won't running dependent queries out of topological
            # order have the same issues as not running matched queries out of
            # topological order? (I think it will)
            # FIXME: ... and therefore won't this need doing for .query() too,
            # including any usages of .query() as part of a LIMAR command in a
            # manifest query?
            # At which point, would it be best to create a dedicated query
            # runner system? (sync for now)
            if ref in matched_queries:
                matched_queries_sorted[ref] = matched_queries[ref]

        # Ensure all matched commands are queries
        for item in matched_queries_sorted.values():
            if item['command']['type'] != 'query':
                raise LIMARException(
                    f"The info subject '{subject}' matched a non-query command"
                    f" '{item['ref']}'. Are you using the correct subject, and"
                    " are the tags correct in the command manifest? Run in"
                    " debug mode (`lm -vvv ...`) to see the full list of"
                    " matched queries."
                )

        # Execute each query. Produces a list of entity data (inc. entity ID)
        # for each query executed.
        #   ItemSet -> list[tuple[ Item, list[dict[str, str]] ]]
        query_outputs =[
            (
                item,
                self._run_query(item['ref'], item['command'])
            )
            for item in matched_queries_sorted.values()
        ]
        self._mod.log.debug('Query outputs:', query_outputs)

        # Index and merge entity data by ID
        return self._merge_entities(query_outputs, subject)

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

        entities = self._run_query(item['ref'], item['command'])
        return self._merge_entities([(item, entities)], subject)

    # Utils - Runners
    # --------------------------------------------------

    def _run_query(self, ref, query) -> list[dict[str, str]]:
        name = ref.replace('/', '.')

        try:
            query_output: list[dict[str, str]] = (
                self._mod.cache.get(f"info.query.{name}.pickle")
            )
        except KeyError:
            query_args: dict[LimarCommand, str] = {}
            for param in query['parameters']:
                query_args[param] = self._run_limar_command(param)['stdout']
                if not isinstance(query_args[param], str):
                    raise LIMARException(
                        f"Evaluation of query parameter {{{{"
                        f" {QueryFormatter().limar_command(param)} }}}} did not"
                        " return a string. Cannot interpolate non-string values"
                        " into the requested query."
                    )
            self._mod.log.debug('Query arguments:', query_args)        

            query_parser = (
                query['parse']
                if 'parse' in query
                else '.'
            )

            COMMAND_RUNNERS = {
                'system': self._run_system_command,
                'limar': self._run_limar_command
            }
            command_outputs: list[dict[str, Any]] = []
            for command in query['commands']:
                try:
                    command_outputs.append(
                        COMMAND_RUNNERS[command['type']](
                            command['command'], query_args, command
                        )
                    )
                    self._mod.log.trace('Command output:', command_outputs[-1])
                except KeyError:
                    raise LIMARException(
                        f"Unknown command type '{command['type']}' for command"
                        f" '{command['command']}' in query '{ref}'"
                    )

            self._mod.log.trace('Query parser input:', command_outputs)
            self._mod.log.trace('Query parser:', query_parser)
            query_output: list[dict[str, str]] = self._mod.tr.query(
                query_parser,
                command_outputs,
                lang='jq',
                first=True
            )
            self._mod.log.debug(
                'Query output (post-transform):',
                command_outputs[-1]
            )
            self._mod.cache.set(f"info.query.{name}.pickle", query_output)

            # Invalidate (delete) the cached output of all commands that depend
            # on the output of this one.
            invalidated = self._invalidate_cache_for_query_dependents(ref)
            self._mod.log.debug(
                f"Invalidated cached output for dependent queries of '{ref}':",
                invalidated
            )

        return query_output

    def _run_limar_command(self,
            limar_command: LimarCommand | InterpolatableLimarCommand,
            data=None,
            options: dict[str, Any] | None = None
    ) -> Any:
        if data is None:
            data = {}

        # Currently unused (don't run unused code), but may be used in future
        # final_options = {}
        # if options is not None:
        #     final_options.update(options)

        module, method, args_raw, jqTransform, pqTransform = limar_command
        self._mod.log.debug(
            'Running LIMAR command:',
            QueryFormatter().limar_command(limar_command)
        )

        # Interpolate args
        args = tuple(
            (
                arg
                if isinstance(arg, str)
                else self._interpolate(arg, data)
            )
            for arg in args_raw
        )
        self._mod.log.debug(
            'Evaluated LIMAR command:',
            QueryFormatter().limar_command(
                (module, method, args, jqTransform, pqTransform)
            )
        )

        # Get LIMAR command output
        cache_hit = False
        if (module, method) == ('info', 'query'):
            try:
                command_output_raw = self._mod.cache.get(
                    f"info.query.{args[0]}.pickle"
                )
                cache_hit = True
            except KeyError:
                pass

        if not cache_hit:
            limar_service_method = getattr(getattr(self._mod, module), method)
            command_output_raw = limar_service_method(*args)

        self._mod.log.debug(
            'LIMAR command output (pre-transform): ',
            command_output_raw
        )

        # Process LIMAR command output
        command_output = command_output_raw
        if jqTransform is not None:
            command_output = self._mod.tr.query(
                jqTransform, command_output_raw, lang='jq', first=True
            )
        elif pqTransform is not None:
            command_output = self._mod.tr.query(
                pqTransform, command_output_raw, lang='yaql'
            )
        self._mod.log.trace(
            'LIMAR command output (post-transform): ',
            command_output
        )

        return {
            'status': 0,
            'stdout': command_output,
            'stderr': None
        }

    def _run_system_command(self,
        system_command: Interpolatable,
        data: dict[LimarCommand, str] | None = None,
        options: dict[str, Any] | None = None
    ) -> Any:
        if data is None:
            data = {}

        final_options = {
            'allowedToFail': False
        }
        if options is not None:
            final_options.update(options)

        command_interpolated = self._interpolate(system_command, data)
        self._mod.log.info('Running command:', command_interpolated)

        command_split_args = shlex.split(command_interpolated)
        self._mod.log.trace('Command split:', command_split_args)

        exception = None
        try:
            subproc = subprocess.Popen(
                command_split_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = subproc.communicate()
            command_status = subproc.returncode

        except subprocess.CalledProcessError as e:
            exception = e
            command_status = exception.returncode

        if command_status != 0 and not final_options['allowedToFail']:
            raise LIMARException(
                f"Process run with arguments {command_split_args} failed"
                f" with return code '{command_status}'."
            ) from exception

        return {
            'status': command_status,
            'stdout': stdout.decode().strip(),
            'stderr': stderr.decode().strip()
        }

    # Utils - Other
    # --------------------------------------------------

    def _interpolate(self,
            interpolatable: Interpolatable,
            data: dict[LimarCommand, str]
    ) -> str:
        return ''.join(
            (
                data[fragment]
                if isinstance(fragment, tuple)
                else fragment
            )
            for fragment in interpolatable
        )

    def _invalidate_cache_for_query_dependents(self,
            query_ref,
            invalidated: set[str] | None = None
    ) -> set[str]:
        assert self._reverse_dependency_graph is not None, f'{self._run_query.__name__}() called before {self.start.__name__}()'

        if invalidated is None:
            invalidated = set()

        for dep_query_ref in self._reverse_dependency_graph[query_ref]:
            if dep_query_ref not in invalidated:
                query_name = dep_query_ref.replace('/', '.')
                self._mod.cache.delete(f'info.query.{query_name}.pickle')

                invalidated.add(dep_query_ref)
                self._invalidate_cache_for_query_dependents(
                    dep_query_ref, invalidated
                )

        return invalidated

    def _merge_entities(self,
            query_outputs: list[tuple[ Item, list[dict[str, str]] ]],
            subject: list[str]
    ) -> dict[str | tuple[str, ...], dict[str, str]]:
        merged_query_output: dict[str | tuple[str, ...], dict[str, str]] = {}
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
