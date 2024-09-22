from graphlib import CycleError, TopologicalSorter
import random
import string
import shlex
import subprocess

from core.exceptions import LIMARException
from core.modulemanager import ModuleAccessor
from core.modules.phase_utils.phase_system import PhaseSystem

# Types
from argparse import ArgumentParser, Namespace
from typing import Any

from modules.manifest import ItemSet

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

    def __init__(self):
        self._dependency_graph: dict[str, set[str]] | None = None
        self._reverse_dependency_graph: dict[str, set[str]] | None = None

    def dependencies(self):
        return ['log', 'phase', 'manifest', 'command-manifest']

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
        parser.add_argument('entity', metavar='ENTITY',
            help="""
            Show information about the given entity.
            """)

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
                    # TODO: Only supports `info.get(ref...)` for now
                    if ('info', 'get', (ref,)) in (
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
            output = self.get(args.entity)

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

    @ModuleAccessor.invokable_as_service
    def get(self, entity_spec: str) -> dict[str, dict[str, str]]:
        """
        Get the list of the queries in the command manifest that match the given
        command_spec, then return the indexed list of objects returned by those
        queries.
        """

        assert self._dependency_graph is not None, f'{self.get.__name__}() called before {self.start.__name__}()'

        matched_queries_sorted = {}

        # Get matching commands to execute
        set_ref = 'info-query-'+''.join(random.choices(string.hexdigits, k=32))
        # FIXME: Yes, I know this is an injection attack waiting to happen, eg.
        #          get('unlikely] | something_evil | [unlikely')
        self._mod.manifest.declare_item_set(set_ref, f'query & [{entity_spec}]')
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
                f"Cannot resolve dependencies for entity set '{entity_spec}'"
                f" due to cycle '{e.args[1]}'"
            )
        self._mod.log.debug(f'Query run order:', query_sort_order)

        matched_queries_sorted: ItemSet = {
            ref: matched_queries[ref]
            for ref in query_sort_order
        }

        # Ensure all matched commands are queries
        for item in matched_queries_sorted.values():
            if item['command']['type'] != 'query':
                raise LIMARException(
                    f"The info spec '{entity_spec}' matched a non-query command"
                    f" '{item['ref']}'. Are you using the correct tag, and are"
                    " the tags correct in the command manifest? Run in debug"
                    " mode (`lm -vvv ...`) to see the full list of matched"
                    " queries."
                )

        # Execute each query. Produces a list of entity data (inc. entity ID)
        # for each query executed.
        #   ItemSet -> list[list[dict[str, str]]]
        query_outputs = [
            self._run_query(item['ref'], item['command'])
            for item in matched_queries_sorted.values()
        ]
        self._mod.log.debug('Query outputs:', query_outputs)

        # Index and merge entity data by ID
        #   list[list[dict[str, str]]] -> dict[str, dict[str, str]]
        merged_query_output: dict[str, dict[str, str]] = {}
        for entity_list in query_outputs:
            for entity_data in entity_list:
                id = entity_data['id']
                if id not in merged_query_output:
                    merged_query_output[id] = {}
                merged_query_output[id].update(entity_data)

        return merged_query_output

    def _run_query(self, ref, query) -> list[dict[str, str]]:
        name = ref.replace('/', '.')

        try:
            query_output: list[dict[str, str]] = (
                self._mod.cache.get(f"info.query.{name}.pickle")
            )
        except KeyError:
            query_args: dict[tuple[str, ...], str] = {}
            for param in query['parameters']:
                module, method, args, transform = param
                self._mod.log.debug(
                    f"Computing parameter: {module}.{method}(" +
                    ', '.join(f"'{arg}'" for arg in args) +
                    f") : {transform}"
                )

                if module == 'info' and method == 'get':
                    try:
                        query_args[param] = self._mod.cache.get(
                            f"info.query.{args[0]}.pickle"
                        )
                    except KeyError:
                        pass

                query_arg = getattr(getattr(self._mod, module), method)(*args)
                self._mod.log.debug(
                    'Query argument (pre-transform): ',
                    query_arg
                )

                query_args[param] = self._mod.tr.query(
                    transform,
                    query_arg,
                    lang='jq',
                    first=True
                )
                self._mod.log.debug(
                    'Query argument (post-transform): ',
                    query_args[param]
                )

                if not isinstance(query_args[param], str):
                    raise LIMARException(
                        f"Evaluation of query parameter {param} did not return"
                        " a string. Cannot interpolate non-string values into"
                        " the requested query."
                    )

            self._mod.log.debug('Query arguments:', query_args)        

            query_parser = (
                query['parse']
                if 'parse' in query
                else '.'
            )

            command_outputs: list[dict[str, Any]] = []
            for command in query['commands']:
                try:
                    command_interpolated = ''.join(
                        (
                            query_args[fragment]
                            if isinstance(fragment, tuple)
                            else fragment
                        )
                        for fragment in command['command']
                    )
                    self._mod.log.info('Running command:', command_interpolated)

                    command_split_args = shlex.split(command_interpolated)
                    self._mod.log.trace('Command split:', command_split_args)

                    subproc = subprocess.Popen(
                        command_split_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    stdout, stderr = subproc.communicate()
                    command_status = 0

                except subprocess.CalledProcessError as e:
                    if not command['allowedToFail']:
                        raise e
                    command_status = e.returncode

                command_outputs.append({
                    'status': command_status,
                    'stdout': stdout.decode().strip(),
                    'stderr': stderr.decode().strip()
                })
                self._mod.log.trace('Command output:', command_outputs[-1])

            query_output: list[dict[str, str]] = self._mod.tr.query(
                query_parser,
                command_outputs,
                lang='jq',
                first=True
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
