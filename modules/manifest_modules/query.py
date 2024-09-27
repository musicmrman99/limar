from itertools import chain
from core.exceptions import LIMARException
import re

from core.utils import list_strip

class Query:
    @staticmethod
    def context_type():
        return 'query'

    def __init__(self):
        self._current_query = None

    def on_enter_context(self, context, *_, **__):
        if 'command' not in context['opts']:
            raise LIMARException(
                "@query context must be given a `command` to execute"
            )

        # Query requirements:
        # - read-only (including caching, etc.)
        # - idempotent
        query_parameters = {
            (
                match.groups()[0],
                match.groups()[1],
                tuple(match.groups()[2].split(', ')),
                match.groups()[4],
                match.groups()[5]
            )
            for match in re.finditer(
                '\\{\\{ (?P<module>[a-z0-9-]*)\\.(?P<method>[a-z0-9_]*)\\((?P<args>.*)\\) (: (?P<jqTransform>.*)|:: (?P<pqTransform>.*)) \\}\\}',
                context['opts']['command']
            )
        }

        raw_commands = [
            command.strip()
            for command in re.split(
                '[ \\n]&&[ \\n]',
                context['opts']['command']
            )
        ]
        commands_parsed = [
            {
                'parameters': [
                    (
                        match.groups()[0],
                        match.groups()[1],
                        tuple(match.groups()[2].split(', ')),
                        match.groups()[4],
                        match.groups()[5]
                    )
                    for match in re.finditer(
                        '\\{\\{ (?P<module>[a-z0-9-]*)\\.(?P<method>[a-z0-9_]*)\\((?P<args>.*)\\) (: (?P<jqTransform>.*)|:: (?P<pqTransform>.*)) \\}\\}',
                        raw_command
                    )
                ],
                'fragments': re.split(
                    '\\{\\{ [a-z0-9-]*\\.[a-z0-9_]*\\(.*\\) ::? .* \\}\\}',
                    raw_command
                ),
                'allowedToFail': False
            }
            for raw_command in raw_commands
        ]
        for command_parsed in commands_parsed:
            if command_parsed['fragments'][0][:2] == '!!':
                command_parsed['allowedToFail'] = True
                command_parsed['fragments'][0] = (
                    command_parsed['fragments'][0][2:]
                )

        commands = [
            {
                # Cannot shlex.split() until we know all of the arguments
                'command': list_strip([
                    *chain.from_iterable(
                        zip(command['fragments'], command['parameters'])
                    ),
                    command['fragments'][-1]
                ], ''),
                'allowedToFail': command['allowedToFail']
            }
            for command in commands_parsed
        ]

        if self._current_query is not None:
            fmt_commands = lambda commands: (
                ' && '.join(
                    ' '.join(
                        (
                            '{{'+', '.join(fragment)+'}}'
                            if isinstance(fragment, tuple)
                            else fragment
                        )
                        for fragment in command['command']
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
            'parameters': query_parameters,
            'commands': commands,
            'parse': context['opts']['parse']
        }

    def on_exit_context(self, *_, **__):
        self._current_query = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('query')
        item['command'] = self._current_query
