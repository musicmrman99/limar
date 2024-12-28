from itertools import chain, zip_longest
import re

from core.exceptions import LIMARException
from core.utils import list_strip

from typing import Any, Literal, TypedDict, cast

Subquery = tuple[str, str, tuple[str, ...], str | None, str | None]
Interpolatable = list[str | Subquery]
GroupedInterpolatable = tuple[Interpolatable, ...]

SystemSubcommandData = GroupedInterpolatable
LimarSubcommandData = tuple[
    str,
    str,
    GroupedInterpolatable,
    str | None,
    str | None
]

class SystemSubcommand(TypedDict):
    type: Literal['system']
    allowedToFail: bool
    parameters: set[Subquery]
    subcommand: SystemSubcommandData

class LimarSubcommand(TypedDict):
    type: Literal['limar']
    allowedToFail: bool
    parameters: set[Subquery]
    subcommand: LimarSubcommandData

Subcommand = SystemSubcommand | LimarSubcommand

class CommandParseOnly(TypedDict):
    parameters: set[Subquery]
    subcommands: list[Subcommand]

class CommandOnly(CommandParseOnly):
    dependencies: tuple[str, ...]
    dependants: tuple[str, ...]
    transitiveDependencies: tuple[str, ...]
    transitiveDependants: tuple[str, ...]

class QueryCommand(CommandOnly):
    type: Literal['query']
    parse: str

class ActionCommand(CommandOnly):
    type: Literal['action']

Command = QueryCommand | ActionCommand

class CommandTransformer:
    # Interface
    # --------------------------------------------------

    # Parsing
    # --------------------

    def parse(self, raw_command: str) -> CommandParseOnly:
        # Split into subcommands
        raw_subcommands = [
            subcommand.strip()
            for subcommand in re.split(
                '[ \\n]&&[ \\n]',
                raw_command
            )
        ]

        # Parse each subcommand
        subcommands: list[Subcommand] = [
            {
                'type': 'system',
                'allowedToFail': False,
                'parameters': set(),
                'subcommand': tuple()
            }
            for _ in range(len(raw_subcommands))
        ]
        for subcommand, raw_subcommand in zip(subcommands, raw_subcommands):
            # Parse markers
            if raw_subcommand[:1] == '!':
                subcommand['allowedToFail'] = True
                raw_subcommand = raw_subcommand[1:]

            if raw_subcommand[:1] == '-':
                cast(LimarSubcommand, subcommand)['type'] = 'limar'
                raw_subcommand = raw_subcommand[1:]

            if raw_subcommand[:1] == ' ':
                raw_subcommand = raw_subcommand[1:]

            # Parse system subcommand
            if subcommand['type'] == 'system':
                fragments, params = self._split_fragments_params(raw_subcommand)
                system_subcommand: SystemSubcommandData = tuple(
                    self._chain_fragments_params(fragments, params)
                    for fragments, params in self._group_fragments_params(
                        fragments, params, delim='[ \t\n]+', quote="[\"']"
                    )
                )

                subcommand['parameters'] = set(params)
                subcommand['subcommand'] = system_subcommand

            # Parse LIMAR subcommand
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
                limar_subcommand: LimarSubcommandData = (
                    match.group('module'),
                    match.group('method'),
                    tuple(
                        self._chain_fragments_params(fragments, params)
                        for fragments, params in self._group_fragments_params(
                            fragments, params, delim=', '
                        )
                    ),
                    match.groups()[4],
                    match.groups()[5]
                )

                subcommand['parameters'] = set(params)
                subcommand['subcommand'] = limar_subcommand

        return {
            'parameters': {
                param
                for subcommand in subcommands
                for param in subcommand['parameters']
            },
            'subcommands': subcommands
        }

    # Checks
    # --------------------

    def is_runnable(self, item):
        return (
            'command' in item and     # @command
            'type' in item['command'] # @query, @action, etc.
        )

    def command_type_of(self, command_item):
        return command_item['command']['type']

    def subject_of(self,
            command_items: dict[str, Any],
            subject: list[str]
    ) -> list[str]:
        all_subjects = set() # Values ignored
        for command_item in command_items.values():
            if 'subjects' in command_item:
                all_subjects.update(command_item['subjects'])

        return [
            single_subject
            for single_subject in subject
            if single_subject in all_subjects
        ]

    def primary_subject_of(self, command_items: dict[str, Any]) -> list[str]:
        primary_subject: dict[str, Any] = {} # Values ignored

        for command_item in command_items.values():
            if 'primarySubject' in command_item:
                primary_subject[command_item['primarySubject']] = None
            elif 'subjects' in command_item:
                for subject in command_item['subjects']:
                    primary_subject[subject] = None

        return list(primary_subject.keys())

    # To Runnable Command
    # --------------------

    def interpolate_grouped(self,
            grouped_interpolatable: GroupedInterpolatable,
            data: dict[Subquery, str]
    ) -> tuple[str, ...]:
        return tuple(
            (
                group
                if isinstance(group, str)
                else self.interpolate(group, data)
            )
            for group in grouped_interpolatable
        )

    def interpolate(self,
            interpolatable: Interpolatable,
            data: dict[Subquery, str]
    ) -> str:
        return ''.join(
            (
                data[fragment]
                if isinstance(fragment, tuple)
                else fragment
            )
            for fragment in interpolatable
        )

    # To Human-Readable String
    # --------------------

    def format_text(self, command: CommandParseOnly) -> str:
        return ' && '.join(
            (
                self.format_text_system_subcommand(
                    subcommand['subcommand']
                )
                if subcommand['type'] == 'system'
                else self.format_text_limar_subcommand(subcommand['subcommand'])
            )
            for subcommand in command['subcommands']
        )

    def format_text_limar_subcommand(self,
            limar_command: LimarSubcommandData
    ) -> str:
        return (
            f"{limar_command[0]}.{limar_command[1]}(" +
            self.format_text_grouped_interpolatable(limar_command[2]) +
            ") " +
            (
                f": {limar_command[3]}"
                if limar_command[3] is not None
                else f":: {limar_command[4]}"
            )
        )

    def format_text_system_subcommand(self,
            system_subcommand: SystemSubcommandData
    ) -> str:
        return self.format_text_grouped_interpolatable(system_subcommand, ' ')

    def format_text_grouped_interpolatable(self,
            grouped_interpolatable: GroupedInterpolatable,
            separator: str = ', '
    ) -> str:
        return separator.join(
            self.format_text_interpolatable(interpolatable)
            for interpolatable in grouped_interpolatable
        )

    def format_text_interpolatable(self, interpolatable: Interpolatable) -> str:
        return ''.join(
            (
                part # Fragment
                if isinstance(part, str)
                else '{{ '+self.format_text_limar_subquery(part)+' }}' # Param
            )
            for part in interpolatable
        )

    def format_text_limar_subquery(self, limar_subquery: Subquery) -> str:
        return (
            f"{limar_subquery[0]}.{limar_subquery[1]}(" +
            ', '.join(limar_subquery[2]) +
            ") " +
            (
                f": {limar_subquery[3]}"
                if limar_subquery[3] is not None
                else f":: {limar_subquery[4]}"
            )
        )

    # Utils
    # --------------------------------------------------

    def _split_fragments_params(self,
            string: str
    ) -> tuple[list[str], list[Subquery]]:
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
            parameters: list[Subquery],
            delim: str,
            quote: str | None = None
    ) -> list[tuple[list[str], list[Subquery]]]:
        groups: list[tuple[list[str], list[Subquery]]] = [
            ([""], [])
        ]

        delim_regex = re.compile(delim)
        quote_regex = None
        if quote is not None:
            quote_regex = re.compile(quote)

        quote_open = False
        for fragment, parameter in zip_longest(
            fragments, parameters,
            fillvalue=None
        ):
            assert fragment is not None, 'len(fragments) == len(parameters) + 1'
            if quote_regex is not None:
                quote_fragments = quote_regex.split(fragment)
            else:
                quote_fragments = [fragment]

            first_quote_fragment = True
            for quote_fragment in quote_fragments:
                if not first_quote_fragment:
                    quote_open = not quote_open
                else:
                    first_quote_fragment = False

                if quote_open:
                    groups[-1][0][-1] = groups[-1][0][-1] + quote_fragment
                else:
                    split_fragment = delim_regex.split(quote_fragment)
                    groups[-1][0][-1] = groups[-1][0][-1] + split_fragment[0]
                    groups.extend(
                        ([initial_fragment], [])
                        for initial_fragment in split_fragment[1:]
                    )
                if parameter is not None:
                    groups[-1][1].append(parameter)

        return groups

    def _chain_fragments_params(self,
            fragments: list[str],
            parameters: list[Subquery]
    ) -> Interpolatable:
        return list_strip([
            *chain.from_iterable(
                zip(fragments, parameters)
            ),
            fragments[-1]
        ], '')
