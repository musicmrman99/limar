LimarCommand = tuple[str, str, tuple[str, ...], str | None, str | None]
Interpolatable = list[str | LimarCommand] # Used for multiple dynamic types
InterpolatableLimarCommand = tuple[
    str,
    str,
    tuple[Interpolatable, ...],
    str | None,
    str | None
]

class QueryFormatter:
    def interpolatable(self, interpolatable: Interpolatable) -> str:
        return ''.join(
            (
                part # Fragment
                if isinstance(part, str)
                else '{{ '+self.limar_command(part)+' }}' # Parameter
            )
            for part in interpolatable
        )

    def limar_command(self,
            limar_command: LimarCommand | InterpolatableLimarCommand
    ) -> str:
        return (
            f"{limar_command[0]}.{limar_command[1]}(" +
            ", ".join(
                (
                    arg
                    if isinstance(arg, str)
                    else self.interpolatable(arg)
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
