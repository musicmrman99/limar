from itertools import chain
import re

from core.exceptions import LIMARException
from core.utils import list_strip

Subquery = tuple[str, str, tuple[str, ...], str | None, str | None]
Interpolatable = list[str | Subquery]
GroupedInterpolatable = tuple[Interpolatable, ...]

SystemSubcommand = GroupedInterpolatable
LimarSubcommand = tuple[
    str,
    str,
    GroupedInterpolatable,
    str | None,
    str | None
]

class CommandTransformer:
    # Interface
    # --------------------------------------------------

    def parse(self, raw_command):
        # Split into subcommands
        raw_subcommands = [
            subcommand.strip()
            for subcommand in re.split(
                '[ \\n]&&[ \\n]',
                raw_command
            )
        ]

        # Parse each subcommand
        subcommands = [{} for _ in range(len(raw_subcommands))]
        for subcommand, raw_subcommand in zip(subcommands, raw_subcommands):
            # Parse markers
            subcommand['type'] = 'system'
            subcommand['allowedToFail'] = False

            if raw_subcommand[:1] == '!':
                subcommand['allowedToFail'] = True
                raw_subcommand = raw_subcommand[1:]

            if raw_subcommand[:1] == '-':
                subcommand['type'] = 'limar'
                raw_subcommand = raw_subcommand[1:]

            if raw_subcommand[:1] != ' ':
                raise LIMARException(
                    "Missing space after markers in subcommand"
                    f" '{self.format_text(raw_subcommand)}'"
                )
            raw_subcommand = raw_subcommand[1:]

            # Parse system command
            if subcommand['type'] == 'system':
                # Cannot shlex.split() until we know all of the arguments
                fragments, params = self._split_fragments_params(raw_subcommand)
                system_subcommand: SystemSubcommand = tuple(
                    self._chain_fragments_params(fragments, params)
                    for fragments, params in self._group_fragments_params(
                        fragments, params, '[ \t\n]+'
                    )
                )

                subcommand['parameters'] = set(params)
                subcommand['subcommand'] = system_subcommand

            # Parse LIMAR command
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
                limar_subcommand: LimarSubcommand = (
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

        return {
            'parameters': {
                param
                for subcommand in subcommands
                for param in subcommand['parameters']
            },
            'subcommands': subcommands
        }

    def format_text(self, command):
        return ' && '.join(
            (
                self.format_text_interpolatable_subcommand(
                    subcommand['subcommand']
                )
                if subcommand['type'] == 'system'
                else self.format_text_limar_subcommand(subcommand)
            )
            for subcommand in command['subcommands']
        )

    def format_text_interpolatable_subcommand(self,
            interpolatable_subcommand: Interpolatable
    ) -> str:
        return ''.join(
            (
                part # Fragment
                if isinstance(part, str)
                else '{{ '+self.format_text_limar_subcommand(part)+' }}' # Param
            )
            for part in interpolatable_subcommand
        )

    def format_text_limar_subcommand(self,
            limar_command: Subquery | LimarSubcommand
    ) -> str:
        return (
            f"{limar_command[0]}.{limar_command[1]}(" +
            ", ".join(
                (
                    arg
                    if isinstance(arg, str)
                    else self.format_text_interpolatable_subcommand(arg)
                )
                for arg in limar_command[2]
            ) +
            ") " +
            (
                f": {limar_command[3]}"
                if limar_command[3] is not None
                else f":: {limar_command[4]}"
            )
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

    def interpolate_grouped(self,
            grouped_interpolatable: GroupedInterpolatable,
            data: dict[Subquery, str]
    ):
        return tuple(
            (
                group
                if isinstance(group, str)
                else self.interpolate(group, data)
            )
            for group in grouped_interpolatable
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
            delim: str
    ) -> list[tuple[list[str], list[Subquery]]]:
        groups: list[tuple[list[str], list[Subquery]]] = [
            ([], [])
        ]

        delim_regex = re.compile(delim)

        for fragment, parameter in zip(fragments[:-1], parameters):
            split_fragment = delim_regex.split(fragment)
            groups[-1][0].append(split_fragment[0])
            groups.extend(
                ([initial_fragment], [])
                for initial_fragment in split_fragment[1:]
            )
            groups[-1][1].append(parameter)

        split_fragment = delim_regex.split(fragments[-1])
        groups[-1][0].append(split_fragment[0])
        groups.extend(
            ([initial_fragment], [])
            for initial_fragment in split_fragment[1:]
        )

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
