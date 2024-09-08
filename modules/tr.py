from itertools import chain

import jq
import yaql
from rich.table import Table
from rich.tree import Tree
from rich.console import RenderableType

from core.exceptions import LIMARException
from core.modulemanager import ModuleAccessor

# Types
from argparse import ArgumentParser, Namespace
from typing import Any, Iterable, Mapping, Sequence, Set

class TrModule:
    """
    Transforms forwarded data in various ways.
    """

    def __init__(self):
        self.yaql_engine = yaql.factory.YaqlFactory().create()

    def dependencies(self):
        return ['console']

    def configure_args(self, *, parser: ArgumentParser, **_):
        # Query
        parser.add_argument('-jq', '--json-query', default=None,
            help="The `jq`-language query to apply.")

        parser.add_argument('-pq', '--python-query', default=None,
            help="The `yaql`-language query to apply.")

        parser.add_argument('-1', '--first',
            action='store_true', default=False,
            help="""
            If doing a json query, only return the first result in the output
            stream.
            """)

        # Index
        parser.add_argument('-i', '--index',
            action='store_true', default=False,
            help="""
            Index the data by its 'ref' attribute. This may be needed after
            querying if the query language does not support building dicts with
            dynamic keys.
            """)

        # Tabulate
          # Data
        parser.add_argument('-t', '--tabulate',
            action='store_true', default=False,
            help="Format data into a table for output. Cannot be forwarded.")

        parser.add_argument('-d', '--delimiter', default=None,
            help="""
            Delimiter for tabulation (for when input is a list of strings).
            """)

        parser.add_argument('-o', '--object-mapping',
            choices=('values', 'all'), default=None,
            help="""
            Object mapping mode for tabulation.

            'values' maps a `list[dict[str, Any]]` (ie. a list of
            JSON-compmatible objects) to a `list[list[Any]]` (ie. a table).
            'all' does the same, but adds the list of property names as a header
            row.

            If 'all' is given and the result is not being forwarded, then '-H'
            is assumed.
            """)

        parser.add_argument('-a', '--align',
            choices=('left', 'right'), default=None,
            help="Alignment for tabulation")

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

        parser.add_argument('-A', '--multi-output',
            action='store_true', default=False,
            help="""
            Whether to destructure the output data into `mod.console.print()`
            instead of returning it.
            """)

    def __call__(self, *,
            mod: Namespace,
            args: Namespace,
            forwarded_data: Any,
            output_is_forward: bool,
            **_
    ):
        output = forwarded_data

        if args.json_query is not None:
            output = self.query(
                args.json_query, output,
                lang='jq', first=args.first
            )

        if args.python_query is not None:
            output = self.query(
                args.python_query, output,
                lang='yaql'
            )

        if args.index is True:
            output = self.index(output)

        if args.tabulate:
            output = self.tabulate(
                output,
                delim=args.delimiter,
                obj_mapping=args.object_mapping,
                align=args.align
            )

            has_headers_assumed = (
                args.object_mapping == 'all' and not output_is_forward
            )
            if not output_is_forward and not args.raw_output:
                output = self.render_table(
                    output,
                    has_metadata=args.has_metadata,
                    has_headers=args.has_headers or has_headers_assumed
                )

        if args.multi_output:
            if isinstance(output, Mapping):
                mod.console.print(*chain.from_iterable(output.items()))
            elif isinstance(output, Iterable):
                mod.console.print(*output)
            else:
                mod.console.print(output)
            return None
        else:
            return output

    @ModuleAccessor.invokable_as_service
    def query(self, query: str, data: Any, *, lang: str, first=False):
        if lang == 'jq':
            transformer = jq.first if first is True else jq.all

        elif lang == 'yaql':
            transformer = lambda qeury_, data_: (
                self.yaql_engine(qeury_).evaluate(data=data_)
            )

        else:
            raise LIMARException(f"Unsupported query language '{lang}'")

        return transformer(query, data)

    @ModuleAccessor.invokable_as_service
    def index(self,
            objs: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        return {obj['ref']: obj for obj in objs}

    @ModuleAccessor.invokable_as_service
    def tabulate(self,
            data: Any,
            delim: str | None = None,
            obj_mapping: str | None = None,
            align: str | None = None
    ):
        """
        If data is a string, then first split it on newline into an array,
        otherwise assumed it's an array. If delim is given, then interpret data
        as a list[str] and split on delim into a list[list[str]].

        If obj_mapping is 'values', then interpret data as a
        list[dict[str, Any]] and convert it into a list[list[Any]] with one
        column for each unique key in any of the dicts. Dictionary order is
        preserved. If obj_mapping is 'all', then do the same, but also insert
        the list of unique dict keys as a header row.

        If none of the above transformations are applied, data is assumed to
        already be a list[list[Any]].

        If align is 'left', then align the data to the left by padding the
        end of all rows with blank items to make all rows the same length. If
        align is 'right', then do the same but insert the items at the start of
        rows.
        """

        # str or list[str] -> list[list[str]]
        if isinstance(data, str):
            data = data.splitlines()
        if delim is not None:
            data = [item.split(delim) for item in data]
        if isinstance(data, dict):
            data = data.values()

        # list[dict[str, Any]] -> list[list[Any]] (with optional header)
        if obj_mapping is not None:
            data = self._objs_to_table(data, obj_mapping == 'all')

        # Make all inner lists the same length, padding as specified
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
            **table_kwargs
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

        table = Table(*headers, show_header=has_headers, **table_kwargs)
        if has_metadata:
            for row in data:
                table.add_row(*row[1:], **row[0])
        else:
            for row in data:
                table.add_row(*[
                    self._render(item)
                    for item in row
                ])

        return table

    @ModuleAccessor.invokable_as_service
    def render_tree(self,
            data: Any,
            label: str | None = None,
            _parent: Tree | None = None,
            **tree_kwargs
    ):
        if _parent is None:
            _parent = Tree(self._render(label), **tree_kwargs)
        if isinstance(data, dict):
            for child_label, child_content in data.items():
                child = _parent.add(self._render(child_label))
                self.render_tree(child_content, _parent=child)
        elif isinstance(data, list):
            for child_content in data:
                self.render_tree(child_content, _parent=_parent)
        else:
            _parent.add(self._render(data))
        return _parent

    # Utils
    # --------------------------------------------------

    def _objs_to_table(self,
            objs: list[dict[str, Any]],
            include_header: bool = False
    ) -> list[list[Any]]:
        all_props = list(dict.fromkeys(
            prop_name
            for item in objs
            for prop_name in item.keys()
        ))

        return [
            *[all_props if include_header else []],
            *[
                [
                    (obj[prop] if prop in obj else None)
                    for prop in all_props
                ]
                for obj in objs
            ]
        ]

    def _render(self, data):
        """Convert the given item into a form that Rich can render."""
        if isinstance(data, RenderableType):
            rendered = data
        elif data is None:
            rendered = ''
        else:
            rendered = str(data)
        return rendered
