import jq
import json
from rich.table import Table

from core.modulemanager import ModuleAccessor

# Types
from argparse import ArgumentParser, Namespace
from typing import Any

class TrModule:
    """
    Transforms forwarded data in various ways.
    """

    def configure_args(self, *, parser: ArgumentParser, **_):
        # Permit data forwarding
        parser.add_argument('---',
            action='store_true', default=False, dest='output_is_forward',
            help="""
            Specifies that the result of this module call should be forwarded to
            another module. This option terminates this module call.
            """)

        # Query
        parser.add_argument('-q', '--query', default=None,
            help="The `jq`-language query to apply.")

        parser.add_argument('-1', '--first',
            action='store_true', default=False,
            help="")

        # Tabulate
          # Data
        parser.add_argument('-t', '--tabulate',
            action='store_true', default=False,
            help="Format data into a table for output. Cannot be forwarded.")

        parser.add_argument('-d', '--delimiter', default=None,
            help="""
            Delimiter for tabulation (for when input is a list of strings).
            """)

        parser.add_argument('-a', '--align', default=None,
            help="Alignment for tabulation ('left' or 'right').")

          # Formatting
        parser.add_argument('-H', '--has-headers',
            action='store_true', default=False,
            help="Whether the input data's first row is a header row.")

        parser.add_argument('-M', '--has-metadata',
            action='store_true', default=False,
            help="Whether the input data's first column is a metadata column.")

        parser.add_argument('-R', '--raw-output',
            action='store_true', default=False,
            help="Whether to omit pretty formatting for the output data.")

    def __call__(self, *, args: Namespace, forwarded_data: Any, **_):
        output = forwarded_data

        if args.query is not None:
            output = self.query(args.query, output, first=args.first)

            if (
                # Don't format if there's further processing to do
                not args.tabulate and

                not args.output_is_forward and
                not args.raw_output
            ):
                output = self.render_query(output)

        if args.tabulate:
            output = self.tabulate(
                output,
                delim=args.delimiter,
                align=args.align
            )

            if not args.output_is_forward and not args.raw_output:
                output = self.render_table(
                    output,
                    has_metadata=args.has_metadata,
                    has_headers=args.has_headers
                )

        return output

    @ModuleAccessor.invokable_as_service
    def query(self, query: str, data: Any, first=False):
        # If it's actually just a string, you probably wouldn't be trying to
        # `jq` it, so assume that it's stringified JSON.
        if isinstance(data, str):
            data = json.loads(data)

        transformer = jq.first if first is True else jq.all
        return transformer(query, data)

    @ModuleAccessor.invokable_as_service
    def render_query(self, data: list | Any):
        if isinstance(data, list):
            return '\n'.join(data)

        return data

    @ModuleAccessor.invokable_as_service
    def tabulate(self,
            data: Any,
            delim: str | None = None,
            align = None
    ):
        """
        If data is a string, then first split it on newline into an array,
        otherwise assumed it's an array. If delim is given, then interpret data
        as a list[str] and split on delim into a list[list[str]], otherwise
        interpret it as a as list[list[Any]].

        If align is 'left', then align the data to the left by padding the
        end of all rows with blank items to make all rows the same length. If
        align is 'right', then do the same but insert the items at the start of
        rows.
        """

        if isinstance(data, str):
            data = data.splitlines()
        if delim is not None:
            data = [item.split(delim) for item in data]

        if align is not None:
            if align == 'left':
                pad = lambda row, to_len: (
                    [*row, *[None for _ in range(to_len - len(row))]]
                    if len(row) < max_items
                    else row
                )
            elif align == 'right':
                pad = lambda row, to_len: (
                    [*[None for _ in range(to_len - len(row))], *row]
                    if len(row) < max_items
                    else row
                )

            max_items = max([len(row) for row in data])
            data = [pad(row, max_items) for row in data]

        return data

    @ModuleAccessor.invokable_as_service
    def render_table(self,
            data: list[list[Any]],
            has_headers = False,
            has_metadata = False,
    ):
        """
        Transform the input data into a human-readable table.

        If has_headers, the first row will be used as the header row.

        If has_metadata, then the first column will be used as the metadata for
        the console (for styling).
        """

        headers = []
        if has_headers:
            headers = data[0]
            data = data[1:]

        table = Table(*headers, show_header=has_headers)
        if has_metadata:
            for row in data:
                table.add_row(*row[1:], **row[0])
        else:
            for row in data:
                table.add_row(*row)

        return table
