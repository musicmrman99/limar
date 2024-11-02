LimarSubcommand = tuple[str, str, tuple[str, ...], str | None, str | None]
InterpolatableSubcommand = list[str | LimarSubcommand] # Used for multiple dynamic types
InterpolatableLimarSubcommand = tuple[
    str,
    str,
    tuple[InterpolatableSubcommand, ...],
    str | None,
    str | None
]

class SubcommandFormatter:
    def interpolatable_subcommand(self, interpolatable: InterpolatableSubcommand) -> str:
        return ''.join(
            (
                part # Fragment
                if isinstance(part, str)
                else '{{ '+self.limar_subcommand(part)+' }}' # Parameter
            )
            for part in interpolatable
        )

    def limar_subcommand(self,
            limar_command: LimarSubcommand | InterpolatableLimarSubcommand
    ) -> str:
        return (
            f"{limar_command[0]}.{limar_command[1]}(" +
            ", ".join(
                (
                    arg
                    if isinstance(arg, str)
                    else self.interpolatable_subcommand(arg)
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
