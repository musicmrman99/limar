from itertools import chain
from os.path import dirname, basename, isfile, join
import glob
import re
from shutil import get_terminal_size
from textwrap import dedent, wrap

from typing import Any, Callable

def modules_adjacent_to(file):
    """
    Utility for getting a list of all python modules in the same directory
    as the given python file path.

    Can be used make a package support being registered with
    `register_package()` by placing the following in the package's
    `__init__.py`:
    ```
    from core.modulemanager_utils import modules_adjacent_to
    __all__ = modules_adjacent_to(__file__)
    ```
    """

    # Based on: https://stackoverflow.com/a/1057534/16967315
    modules = glob.glob(join(dirname(file), "*.py"))
    return [
        basename(module)[:-3]
        for module in modules
        if isfile(module) and not basename(module).startswith('__')
    ]

def list_split_fn(
        list_: list[Any],
        should_split: Callable[[Any], bool]
) -> tuple[list[list[Any]], list[Any]]:
    lists: list[list[Any]] = [[]]
    splits: list[Any] = []
    for item in list_:
        if should_split(item):
            lists.append([])
            splits.append(item)
        else:
            lists[-1].append(item)
    return lists, splits

def list_split_eq(list_: list[Any], sep: str):
    return list_split_fn(list_, sep.__eq__)[0]

def list_split_match(list_: list[Any], sep: str):
    regex = re.compile(sep)
    return list_split_fn(list_, lambda item: bool(regex.match(item)))

def list_strip(list_: list[Any], str_: str):
    while len(list_) > 0 and list_[0] == str_:
        list_ = list_[1:]
    while len(list_) > 0 and list_[-1] == str_:
        list_ = list_[:-1]
    return list_

def tabulate(
        data: Any,
        delim: str | None = None,
        obj_mapping: str | None = None,
        align: str | None = None
) -> list[list[Any]]:
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
        data = objs_to_table(data, obj_mapping == 'all')

    # Make all inner lists the same length, padding as specified
    if align is not None:
        max_items = max([len(row) for row in data])

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

        data = [pad(row, max_items) for row in data]

    return data

def objs_to_table(
        objs: list[dict[Any, Any]],
        include_header: bool = False
) -> list[list[Any]]:
    """
    Convert a list of dictionaries to a list of lists by transforming unique
    keys into columns.
    """

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

def render_table(
        data: list[list[str]],
        has_headers = False,
        column_separator: str = ' | ',
        header_row_column_separator: str = '-+-',

        column_weights: list[int | None] | None = None,
        max_table_width: int | None = None,
        max_rowheight: int | None = None
) -> str:
    """
    Render the given data as a table.

    If has_headers is True, take the first row of the data as the header line.

    If the total table width is wider than max_table_width and column_weights is
    given, then wrap items to redistribute space according to the relative
    weights given in column_weights. Any None values in column_weights mean
    'do not wrap'. If the wrapping exceeds max_rowheight lines for a row, then
    truncate all exceeding items to max_rowheight lines for that row.

    If max_table_width is not given, it defaults to the width of the terminal,
    as determined by `shutil.get_terminal_size((80, 20))`.
    """

    if max_table_width is None:
        max_table_width = get_terminal_size((80, 20))[0]

    # Basic width calculations
    num_columns = max([
        0,
        (
            len(data[0])
            if len(data) > 0
            else 0
        )
    ])

    if column_weights is None:
        column_weights = [None for _ in range(num_columns)]

    # Initial width calculation
    column_widths = [
        max(len(row[i]) for row in data)
        for i in range(num_columns)
    ]

    # Redistribute space if the table is too wide
    total_column_separator_width = (num_columns - 1) * len(column_separator)
    total_table_width = sum(column_widths) + total_column_separator_width

    if total_table_width > max_table_width:
        remaining_space = (
            max_table_width -
            total_column_separator_width -
            sum(
                column_width
                for column_width, column_weight in zip(
                    column_widths, column_weights
                )
                if column_weight is None
            )
        )
        total_column_weight = sum(
            column_weight
            for column_weight in column_weights
            if column_weight is not None
        )
        column_widths = [
            (
                remaining_space * column_weight // total_column_weight
                if column_weight is not None
                else column_width
            )
            for column_width, column_weight in zip(
                column_widths, column_weights
            )
        ]

        data_lines = [
            [
                [
                    (
                        f"{line: <{column_width}}"
                        if max_rowheight is None or i < max_rowheight
                        else f"{'...': <{column_width}}"
                    )
                    for i, line in enumerate(
                        line
                        for paragraph in dedent(item).strip().split('\n')
                        for line in (
                            wrap(paragraph, column_width)
                            if paragraph != ''
                            else ['']
                        )
                    )
                    if max_rowheight is None or i <= max_rowheight
                ]
                for item, column_width in zip(row, column_widths)
            ]
            for row in data
        ]
        row_heights = [
            max(len(lines) for lines in row)
            for row in data_lines
        ]
        data = [
            [
                (
                    item_lines[line_num]
                    if len(item_lines) >= line_num + 1
                    else ' '*column_width
                )
                for item_lines, column_width in zip(row, column_widths)
            ]
            for row, row_height in zip(data_lines, row_heights)
            for line_num in range(row_height)
        ]
    else:
        data = [
            [
                f"{item: <{column_width}}"
                for item, column_width in zip(row, column_widths)
            ]
            for row in data
        ]

    headers = None
    if has_headers:
        headers = data[0]
        data = data[1:]

    return '\n'.join(chain(
        (
            [
                column_separator.join(headers),
                header_row_column_separator.join([
                    '-'*column_width
                    for column_width in column_widths
                ])
            ]
            if headers is not None
            else []
        ),
        (column_separator.join(row) for row in data)
    ))
