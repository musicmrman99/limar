import subprocess
import shlex

# Types
from argparse import ArgumentParser, Namespace
from typing import Any

class InfoModule:
    """
    MM module to manage retreiving and displaying information.
    """

    def __init__(self):
        pass

    def dependencies(self):
        return ['log', 'manifest', 'tool-manifest']

    def configure_args(self, *, parser: ArgumentParser, **_):
        parser.add_argument('entity', metavar='ENTITY',
            help="""
            Show information about the given entity.
            """)

        # Subcommands / Resolve Item Set - Output Controls
        parser.add_argument('-L', '--lower-stage', default=None,
            help="""
            Specifies that all stages of processing up to the given stage should
            be performed, even if the result is being forwarded.
            """)
        parser.add_argument('-U', '--upper-stage', default=None,
            help="""
            Specifies that no stages of processing after the given stage should
            be performed, even if the result isn't being forwarded.
            """)
        parser.add_argument('---',
            action='store_true', default=False, dest='output_is_forward',
            help="""
            Specifies that the result of this module call should be forwarded to
            another module. This option terminates this module call.
            """)

    STAGES = [
        'get',
        'merge',
        'tabulate',
        'render'
    ]

    def __call__(self, *, mod: Namespace, args: Namespace, **_):
        query_tools = mod.manifest.get_item_set('queryable')

        # Execute each query. Should produce a list of entity data (inc. ID) for
        # each query executed.
        #   ItemSet -> list[list[dict[str, str]]]
        output: Any = [
            mod.tr.query(
                query['parse'],
                subprocess
                    .check_output(
                        shlex.split(query['command'])
                    )
                    .decode(),
                first=True
            )
            for query_tool in query_tools.values()
            for query in query_tool['commands']['queries']
        ]

        # Index and merge entity data by ID
        #   list[list[dict[str, str]]] -> dict[str, dict[str, str]]
        tmp_output: dict[str, dict[str, str]] = {}
        for entity_list in output:
            for entity_data in entity_list:
                id = entity_data['id']
                if id not in tmp_output:
                    tmp_output[id] = {}
                tmp_output[id].update(entity_data)
        output = tmp_output

        if self._should_run_stage('tabulate',
            args.output_is_forward, args.lower_stage, args.upper_stage
        ):
            output = mod.tr.tabulate(output.values(), obj_mapping='all')

        if self._should_run_stage('render',
            args.output_is_forward, args.lower_stage, args.upper_stage
        ):
            output = mod.tr.render_table(output, has_headers=True)

        return output

    # Stage Management

    def _stage_is_at_or_before(self, target: str, upper: str | None):
        if upper is None:
            return True
        return self.STAGES.index(target) <= self.STAGES.index(upper)

    def _should_run_stage(self,
            stage: str,
            forwarded: bool,
            lower_stage: str | None = None,
            upper_stage: str | None = None
    ):
        include_if_not_reached_lower_stage = (
            lower_stage is not None and
            self._stage_is_at_or_before(stage, lower_stage)
        )
        include_if_not_reached_upper_stage = (
            self._stage_is_at_or_before(stage, upper_stage)
        )

        return (
            (
                not forwarded or
                include_if_not_reached_lower_stage
            ) and
            include_if_not_reached_upper_stage
        )
