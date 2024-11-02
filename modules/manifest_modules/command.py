from itertools import chain
import re

from core.exceptions import LIMARException
from core.utils import list_strip
from modules.command_utils.formatter import (
    LimarSubcommand,
    InterpolatableSubcommand,
    InterpolatableLimarSubcommand,
    SubcommandFormatter
)

class Command:
    def __init__(self):
        self._current_command = None
        self._fmt = SubcommandFormatter()

    @staticmethod
    def context_type():
        return 'command'

    @staticmethod
    def can_be_root():
        return True

    def on_enter_context(self, context, *_, **__):
        # Ignore 'requirement' contexts
        if len(context['opts']) == 0:
            return

        # Require command in 'declaration' contexts
        if 'command' not in context['opts']:
            raise LIMARException(
                "A declaration @command context must be given a `command` to"
                " execute"
            )

        raw_subcommands = [
            subcommand.strip()
            for subcommand in re.split(
                '[ \\n]&&[ \\n]',
                context['opts']['command']
            )
        ]

        subcommands = [{} for _ in range(len(raw_subcommands))]
        for subcommand, raw_subcommand in zip(subcommands, raw_subcommands):
            subcommand['type'] = 'system'
            subcommand['allowedToFail'] = False
            if raw_subcommand[:2] == '- ':
                subcommand['type'] = 'limar'
                raw_subcommand = raw_subcommand[2:]
            elif raw_subcommand[:2] == '! ':
                subcommand['allowedToFail'] = True
                raw_subcommand = raw_subcommand[2:]

            if subcommand['type'] == 'system':
                # Cannot shlex.split() until we know all of the arguments
                fragments, params = self._split_fragments_params(raw_subcommand)
                system_subcommand: InterpolatableSubcommand = (
                    self._chain_fragments_params(fragments, params)
                )

                subcommand['parameters'] = set(params)
                subcommand['subcommand'] = system_subcommand

            elif subcommand['type'] == 'limar':
                match = re.match(
                    "^(?P<module>[a-z0-9-]*)\\.(?P<method>[a-z0-9_]*)\\((?P<args>.*)\\) (: (?P<jqTransform>.*)|:: (?P<pqTransform>.*))$",
                    raw_subcommand
                )
                if match is None:
                    raise LIMARException(
                        f"Failed to parse limar subcommand '{raw_subcommand}'"
                    )
                fragments, params = self._split_fragments_params(
                    match.group('args')
                )
                limar_subcommand: InterpolatableLimarSubcommand = (
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

                subcommand['parameters'] = set(params)
                subcommand['subcommand'] = limar_subcommand

        if self._current_command is not None:
            fmt_subcommands = lambda subcommands: (
                ' && '.join(
                    (
                        self._fmt.interpolatable_subcommand(
                            subcommand['subcommand']
                        )
                        if subcommand['type'] == 'system'
                        else self._fmt.limar_subcommand(subcommand)
                    )
                    for subcommand in subcommands
                )
            )
            raise LIMARException(
                "Can only have one nested @query context: tried to nest"
                f" '{fmt_subcommands(subcommands)}' inside"
                f" '{fmt_subcommands(self._current_command['subcommands'])}'"
            )

        self._current_command = {
            'parameters': {
                param
                for subcommand in subcommands
                for param in subcommand['parameters']
            },
            'subcommands': subcommands
        }

    def on_exit_context(self, *_, **__):
        self._current_command = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('command')
        item['command'] = self._current_command

    def on_exit_manifest(self, items, item_sets, *_, **__):
        # Verify that required contexts were declared for all commands
        for item in items.values():
            if (
                'command' in item['tags'] and
                'command' not in item and

                # Ignore any items with a tag that starts with `__`
                all(
                    not name.startswith('__')
                    for name in item['tags'].raw().keys()
                )
            ):
                raise LIMARException(
                    "@command context requires a command to be declared for"
                    f" item '{item['ref']}'"
                )

    def _split_fragments_params(self,
            string: str
    ) -> tuple[list[str], list[LimarSubcommand]]:
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
            parameters: list[LimarSubcommand],
            delim: str
    ) -> list[tuple[list[str], list[LimarSubcommand]]]:
        groups: list[tuple[list[str], list[LimarSubcommand]]] = [
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
            parameters: list[LimarSubcommand]
    ) -> InterpolatableSubcommand:
        return list_strip([
            *chain.from_iterable(
                zip(fragments, parameters)
            ),
            fragments[-1]
        ], '')
