import random
import string
import subprocess

from core.modules.phase_utils.phase_system import PhaseSystem

# Types
from argparse import ArgumentParser, Namespace
from typing import Any

INFO_LIFECYCLE = PhaseSystem(
    f'{__name__}:lifecycle',
    (
        'INITIALISE',
        'QUERY',
        'GET',
        'MERGE',
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
        pass

    def dependencies(self):
        return ['log', 'phase', 'manifest', 'command-manifest']

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
        parser.add_argument('entity', metavar='ENTITY',
            help="""
            Show information about the given entity.
            """)

        # Subcommands / Resolve Item Set - Output Controls
        mod.phase.configure_phase_control_args(parser)
        parser.add_argument('---',
            action='store_true', default=False, dest='output_is_forward',
            help="""
            Specifies that the result of this module call should be forwarded to
            another module. This option terminates this module call.
            """)

    def configure(self, *, mod: Namespace, **_):
        mod.phase.register_system(INFO_LIFECYCLE)

    def __call__(self, *,
            mod: Namespace,
            args: Namespace,
            forwarded_data: Any,
            **_
    ):
        # Set up phase process and a common transition function
        # WARNING: THIS MUTATES STATE, even though it's used in `if` statements
        transition_to_phase = mod.phase.create_process(INFO_LIFECYCLE, args)

        output: Any = forwarded_data

        query_command_items = {}
        if transition_to_phase(INFO_LIFECYCLE.PHASES.QUERY):
            ref = 'info-query-'+''.join(random.choices(string.hexdigits, k=32))
            # FIXME: Yes, I know, this is an injection attack waiting to happen.
            mod.manifest.declare_item_set(ref, f'query & [{args.entity}]')
            query_command_items = mod.manifest.get_item_set(ref)
            mod.log.debug(f'Matched manifest items:', query_command_items)

        # Execute each query. Produces a list of entity data (inc. entity ID)
        # for each query executed.
        #   ItemSet -> list[list[dict[str, str]]]
        if transition_to_phase(INFO_LIFECYCLE.PHASES.GET):
            output = []
            for item in query_command_items.values():
                command_query = (
                    item['command']['parse']
                    if 'parse' in item['command']
                    else '.'
                )

                command_outputs: list[dict[str, Any]] = []
                for command in item['command']['commands']:
                    try:
                        subproc = subprocess.Popen(
                            command['command'],
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

                output.append(mod.tr.query(
                    command_query,
                    command_outputs,
                    lang='jq',
                    first=True
                ))

            mod.log.debug(f'Query output:', output)

        # Index and merge entity data by ID
        #   list[list[dict[str, str]]] -> dict[str, dict[str, str]]
        if transition_to_phase(INFO_LIFECYCLE.PHASES.MERGE):
            tmp_output: dict[str, dict[str, str]] = {}
            for entity_list in output:
                for entity_data in entity_list:
                    id = entity_data['id']
                    if id not in tmp_output:
                        tmp_output[id] = {}
                    tmp_output[id].update(entity_data)
            output = tmp_output

        # Format
        if transition_to_phase(
            INFO_LIFECYCLE.PHASES.TABULATE, not args.output_is_forward
        ):
            output = mod.tr.tabulate(output.values(), obj_mapping='all')

        if transition_to_phase(
            INFO_LIFECYCLE.PHASES.RENDER, not args.output_is_forward
        ):
            output = mod.tr.render_table(output, has_headers=True)

        # Forward
        return output
