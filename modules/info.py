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
        try:
            self._reverse_dependency_graph = mod.cache.get(
                f'info.dependency_graph.{command_manifest_digest}.pickle'
            )
        except KeyError:
            query_items = mod.manifest.get_item_set('query')
            self._reverse_dependency_graph = {
                ref: {
                    item['ref']
                    for _, item in query_items.items()
                    # TODO: Only supports `info.get(ref...)` for now
                    if ('info', 'get', ref) in (
                        param[0:3] for param in item['command']['parameters']
                    )
                }
                for ref, _ in query_items.items()
            }
            mod.cache.set(
                f'info.dependency_graph.{command_manifest_digest}.pickle',
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

        matched_queries = {}

        # Get matching commands to execute
        ref = 'info-query-'+''.join(random.choices(string.hexdigits, k=32))
        # FIXME: Yes, I know this is an injection attack waiting to happen, eg.
        #          get('unlikely] | something_evil | [unlikely')
        self._mod.manifest.declare_item_set(ref, f'query & [{entity_spec}]')
        matched_queries = self._mod.manifest.get_item_set(ref)
        self._mod.log.debug(f'Matched manifest items:', matched_queries)

        # Ensure all matched commands are queries
        for item in matched_queries.values():
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
            self._run_query(item['ref'].replace('/', '_'), item['command'])
            for item in matched_queries.values()
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

    def _run_query(self, name, query) -> list[dict[str, str]]:
        use_cache = False
        try:
            cached_output: dict[str, Any] = (
                self._mod.cache.get(f"info.query.{name}.pickle")
            )
            is_valid: bool = cached_output['is_valid']
            query_output: list[dict[str, str]] = cached_output['query_output']
            if is_valid:
                use_cache = True
        except KeyError:
            pass

        if not use_cache:
            query_parser = (
                query['parse']
                if 'parse' in query
                else '.'
            )

            command_outputs: list[dict[str, Any]] = []
            for command in query['commands']:
                try:
                    command_interpolated = ''.join(
                        fragment
                        for fragment in command['command']
                        if isinstance(fragment, str)
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
            self._mod.cache.set(
                f"info.query.{name}.pickle",
                {
                    'is_valid': True,
                    'query_output': query_output
                }
            )

        return query_output
