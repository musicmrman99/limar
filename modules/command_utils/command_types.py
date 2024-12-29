from typing import Literal, TypedDict

# Commands
# --------------------

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
    parameters: list[Subquery]
    subcommand: SystemSubcommandData

class LimarSubcommand(TypedDict):
    type: Literal['limar']
    allowedToFail: bool
    parameters: list[Subquery]
    subcommand: LimarSubcommandData

Subcommand = SystemSubcommand | LimarSubcommand

class CommandParseOnly(TypedDict):
    parameters: list[Subquery]
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

# Entities
# --------------------

Entity = dict[str, str]
