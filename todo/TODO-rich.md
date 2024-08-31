# `rich` (Rich text output)

## `Console`

console = Console(soft_wrap=[False])
  - soft_wrap=True will output text literally, without inserting line breaks (or cropping)
    - which will make your terminal do the wrapping for you
err_console = Console(stderr=True)
console = Console(file=open_w_file_handle)
  - can't use Path.write_text() - it is written as-and-when
  - you may want to set width=, or soft_wrap=True

console.print(overflow=)
  - overflow=fold, crop, ellipsis, ignore+crop=False
console.print_json()
console.log()
console.log(JSON())
console.out()
console.rule() - horizontal rule

with console.status(spinner=): - status messages (async)
  - spinner=dots ('waiting'-style process)
  - spinner=simpleDotsScrolling ('moving forward'-style process)
  - spinner=toggle (git?)

console.input()
  - make sure to `import readline` (try/catch - it's not always available)
    - which will make input() support history and fancy line editing

export_svg() - for making docs :D

with console.pager(styles=[False]): - buffers output and sends to pager at end of 'with'

with console.screen() as screen: - supports full-screen apps (separate from normal output)
  - EXPERIMENTAL
  - screen.update(renderable)

from rich.text import Text
  Text.from_markup()
from rich.align import Align
  Align.center()
from rich.panel import Panel
  Panel()

### For testing

from io import StringIO
from rich.console import Console
console = Console(file=StringIO())
console.print("[bold red]Hello[/] World")
str_output = console.file.getvalue()

## Styles

- `((not? (fgcolor | fgstyle))+ | 'default') (' on ' ((not? bgcolor)+ | 'default'))?`

- `fgstyle`s:
  - `reverse` (fore/back colours reversed)
  - `bold`
  - `italic` (not supported on Windows)
  - `strike`
  - `underline`
  - `overline` (limited support)
  - `link <url>` (turns text into a hyperlink)

- these are parsed to a `Style` instance
  - you can make these yourself
  - you can combine them with `+`

- Theme(inherit=[True]) - a map of names to Style objects (or parsable strings)
  - when you provide a theme to the Console, you can use each name as a string to mean its corresponding style
  - `styleName : [a-z][a-z._-]*`

- 'standard colours'
  - https://rich.readthedocs.io/en/latest/appendix/colors.html#appendix-colors

# Other Stuff

- `Table`s!
  - https://rich.readthedocs.io/en/latest/tables.html
