from itertools import chain, zip_longest
import random
import re
import string

from core.exceptions import LIMARException
from core.utils import list_strip

# Types
from typing import Any, cast

from modules.command_utils.command_types import (
    CommandParseOnly,
    Subcommand, LimarSubcommand, LimarSubcommandData, SystemSubcommandData,
    Subquery, Interpolatable, GroupedInterpolatable,
    Entity
)

class CommandTransformer:
    # Subjects
    # --------------------------------------------------

    def subject_mapping_from(self,
            subject_items: dict[str, Any]
    ) -> dict[str, str]:
        return {
            alias_ref: resolved_ref
            for resolved_ref, item in subject_items.items()
            for alias_ref in [
                resolved_ref,
                *(
                    item['aliases']
                    if 'aliases' in item
                    else []
                )
            ]
        }

    def resolved_subject(self,
            subject_mapping: dict[str, str],
            given_subject: list[str],
            keep_unrecognised: bool = False
    ) -> list[str]:
        if keep_unrecognised:
            return [
                subject_mapping[ref] if ref in subject_mapping else ref
                for ref in given_subject
            ]
        else:
            return [
                subject_mapping[ref]
                for ref in given_subject
                if ref in subject_mapping
            ]

    def subject_in(self,
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

    # Entities
    # --------------------------------------------------

    def entity_from(self,
            subject_items: dict[str, Any],
            resolved_subject: list[str],
            ids: list[str]
    ) -> dict[str, str]:
        return {
            subject_items[subject_entry]['id']: id
            for subject_entry, id in zip(resolved_subject, ids)
        }

    def merge_entities(self,
            subject_items: dict[str, Any],
            entities: list[Entity],
            subject: list[str]
    ) -> dict[str | tuple[str, ...], Entity]:
        # Get ID field names for the command's subject
        try:
            id_fields = tuple(
                subject_items[tag]['id']
                for tag in subject
            )
        except KeyError as e:
            raise LIMARException(
                f"Attempt to merge entities using undeclared subject"
                f" '{e.args[0]}'."
                f" If you did not intend '{e.args[0]}' to be treated as a"
                " subject, then re-check your command line. If that should"
                " be a valid subject, then there may be an issue with the"
                " subject manifest or command manifest."
            )

        # Get ID field values from each output entity
        merged_entities: dict[str | tuple[str, ...], Entity] = {}
        for entity_data in entities:
            try:
                id = tuple(entity_data[id_field] for id_field in id_fields)
            except KeyError as e:
                raise LIMARException(
                    "Entity being merged (below) is missing identity field"
                    f" '{e.args[0]}' mapped from subject"
                    f" '{subject[id_fields.index(e.args[0])]}'."
                    " This is likely to be an issue with the subject manifest"
                    f" or command manifest.\n\n{entity_data}"
                )

            # If there is only one item in the composite key, then unwrap
            # it. Neither jq nor yaql support indexing into dictionaries
            # with tuple keys. Unwrapping permits queries (and subqueries)
            # to be indexed into to improve performance when joining data
            # about different subjects.
            if len(id) == 1:
                id = id[0]

            if id not in merged_entities:
                merged_entities[id] = {}
            merged_entities[id].update(entity_data)

        return merged_entities

    # Commands
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
                'parameters': [],
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

                subcommand['parameters'] = list(
                    {param: None for param in params}.keys()
                )
                subcommand['subcommand'] = system_subcommand

            # Parse LIMAR subcommand
            elif subcommand['type'] == 'limar':
                match = re.match(
                    "^(?P<module>[a-z0-9-]*)\\.(?P<method>[a-z0-9_]*)(?:\\((?P<args>[^)]*)\\))? (: (?P<jqTransform>.*)|:: (?P<pqTransform>.*))$",
                    raw_subcommand
                )
                if match is None:
                    raise LIMARException(
                        f"Failed to parse limar subcommand '{raw_subcommand}'"
                    )
                # FIXME [?]: if this is blank or omitted, does this yield an
                #            empty tuple?
                fragments, params = self._split_fragments_params(
                    match.group('args') if match.group('args') != None else ""
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

                subcommand['parameters'] = list(
                    {param: None for param in params}.keys()
                )
                subcommand['subcommand'] = limar_subcommand

        return {
            'parameters': list({
                param: None
                for subcommand in subcommands
                for param in subcommand['parameters']
            }.keys()),
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
            (
                (
                    f"{limar_subquery[0]}.{limar_subquery[1]}("
                    + ', '.join(limar_subquery[2]) +
                    ")"
                )
                if limar_subquery[0] != '.'
                else '.'
            ) + " " + (
                f": {limar_subquery[3]}"
                if limar_subquery[3] is not None
                else f":: {limar_subquery[4]}"
            )
        )

    # Utils
    # --------------------

    def _split_fragments_params(self,
            subcommand: str
    ) -> tuple[list[str], list[Subquery]]:
        return (
            re.split(
                '\\{\\{ [a-z0-9-]*\\.[a-z0-9_]*(?:\\([^)]*\\))? ::? .* \\}\\}',
                subcommand
            ),
            [
                (
                    (
                        match.group('module')
                        if match.group('module') != ''
                        else '.'
                    ),
                    (
                        match.group('method')
                        if match.group('method') != ''
                        else ''.join(random.choices(string.hexdigits, k=32))
                    ),
                    (
                        tuple(match.group('args').split(', '))
                        if (
                            match.group('args') is not None and
                            len(match.group('args')) > 0
                        )
                        else tuple()
                    ),
                    match.groups()[4],
                    match.groups()[5]
                )
                for match in re.finditer(
                    '\\{\\{ (?P<module>[a-z0-9-]*)\\.(?P<method>[a-z0-9_]*)(?:\\((?P<args>[^)]*)\\))? (: (?P<jqTransform>.*)|:: (?P<pqTransform>.*)) \\}\\}',
                    subcommand
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
