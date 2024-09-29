from itertools import chain
import re

from core.exceptions import LIMARException
from core.utils import list_strip
from modules.command_utils.query import (
    LimarCommand,
    Interpolatable,
    InterpolatableLimarCommand,
    QueryFormatter
)

class Query:
    @staticmethod
    def context_type():
        return 'query'

    def __init__(self):
        self._current_query = None
        self._fmt = QueryFormatter()

    def on_enter_context(self, context, *_, **__):
        if 'command' not in context['opts']:
            raise LIMARException(
                "@query context must be given a `command` to execute"
            )

        # Query requirements:
        # - read-only (including caching, etc.)
        # - idempotent
        raw_commands = [
            command.strip()
            for command in re.split(
                '[ \\n]&&[ \\n]',
                context['opts']['command']
            )
        ]

        commands = [{} for _ in range(len(raw_commands))]
        for i, raw_command in enumerate(raw_commands):
            command = commands[i]

            command['type'] = 'system'
            command['allowedToFail'] = False
            if raw_command[:2] == '- ':
                command['type'] = 'limar'
                raw_command = raw_command[2:]
            elif raw_command[:2] == '! ':
                command['allowedToFail'] = True
                raw_command = raw_command[2:]

            if command['type'] == 'system':
                # Cannot shlex.split() until we know all of the arguments
                fragments, params = self._split_fragments_params(raw_command)
                system_command: Interpolatable = (
                    self._chain_fragments_params(fragments, params)
                )

                command['parameters'] = set(params)
                command['command'] = system_command

            elif command['type'] == 'limar':
                match = re.match(
                    "^(?P<module>[a-z0-9-]*)\\.(?P<method>[a-z0-9_]*)\\((?P<args>.*)\\) (: (?P<jqTransform>.*)|:: (?P<pqTransform>.*))$",
                    raw_command
                )
                if match is None:
                    raise LIMARException(
                        f"Failed to parse limar command '{raw_command}'"
                    )
                fragments, params = self._split_fragments_params(
                    match.group('args')
                )
                limar_command: InterpolatableLimarCommand = (
                    match.group('module'),
                    match.group('method'),
                    tuple(
                        self._chain_fragments_params(fragments, params)
                        for fragments, params in self._group_fragments_params(
                            fragments, params, ', '
                        )
                    ),
                    match.groups()[4],
                    match.groups()[5]
                )

                command['parameters'] = set(params)
                command['command'] = limar_command

        if self._current_query is not None:
            fmt_commands = lambda commands: (
                ' && '.join(
                    (
                        self._fmt.interpolatable(command['command'])
                        if command['type'] == 'system'
                        else self._fmt.limar_command(command)
                    )
                    for command in commands
                )
            )
            raise LIMARException(
                "Can only have one nested @query context: tried to nest"
                f" '{fmt_commands(commands)}' inside"
                f" '{fmt_commands(self._current_query['commands'])}'"
            )

        self._current_query = {
            'type': 'query',
            'parameters': {
                param
                for command in commands
                for param in command['parameters']
            },
            'commands': commands,
            'parse': context['opts']['parse']
        }

    def on_exit_context(self, *_, **__):
        self._current_query = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('query')
        item['command'] = self._current_query

    def _split_fragments_params(self,
            string: str
    ) -> tuple[list[str], list[LimarCommand]]:
        return (
            re.split(
                '\\{\\{ [a-z0-9-]*\\.[a-z0-9_]*\\(.*\\) ::? .* \\}\\}',
                string
            ),
            [
                (
                    match.group('module'),
                    match.group('method'),
                    tuple(match.group('args').split(', ')),
                    match.groups()[4],
                    match.groups()[5]
                )
                for match in re.finditer(
                    '\\{\\{ (?P<module>[a-z0-9-]*)\\.(?P<method>[a-z0-9_]*)\\((?P<args>.*)\\) (: (?P<jqTransform>.*)|:: (?P<pqTransform>.*)) \\}\\}',
                    string
                )
            ]
        )

    def _group_fragments_params(self,
            fragments: list[str],
            parameters: list[LimarCommand],
            delim: str
    ) -> list[tuple[list[str], list[LimarCommand]]]:
        groups: list[tuple[list[str], list[LimarCommand]]] = [
            ([], [])
        ]

        for fragment, parameter in zip(fragments[:-1], parameters):
            split_fragment = fragment.split(delim)
            groups[-1][0].append(split_fragment[0])
            groups.extend(
                ([initial_fragment], [])
                for initial_fragment in split_fragment[1:]
            )
            groups[-1][1].append(parameter)

        split_fragment = fragments[-1].split(delim)
        groups[-1][0].append(split_fragment[0])
        groups.extend(
            ([initial_fragment], [])
            for initial_fragment in split_fragment[1:]
        )

        return groups

    def _chain_fragments_params(self,
            fragments: list[str],
            parameters: list[LimarCommand]
    ) -> Interpolatable:
        return list_strip([
            *chain.from_iterable(
                zip(fragments, parameters)
            ),
            fragments[-1]
        ], '')
