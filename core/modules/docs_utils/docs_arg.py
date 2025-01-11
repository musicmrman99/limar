from argparse import ArgumentParser, Action, Namespace
from textwrap import dedent

from core.modules.docs_utils.helpformatter import MMHelpFormatter

# Types
from typing import Callable

# See MMHelpFormatter for how this works. Yes, this is a somewhat ugly hack, but
# is better than needing two parse passes and varying the argument help text
# across all modules based on whether `--docs`` was given. That would require
# custom handling in MM itself. This solution also requires that a tiny bit, but
# in a way that's not exposed to modules.
class DocsAction(Action):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string == '--docs':
            MMHelpFormatter.show_extended()
        parser.print_help()
        parser.exit()

def add_docs_arg(parser: ArgumentParser):
    """
    Add an option to the given parser to show its help text with the extended
    documentation for the command included.
    """

    parser.formatter_class = MMHelpFormatter
    parser.add_argument('--docs', action=DocsAction,
        help="""Show help text with the extended documentation included.""")

def docs_for(processor: Callable, env: Namespace):
    env_dict = vars(env) if env is not None else None
    docs = '\n\n'.join(
        part for part in (
            (
                dedent(processor.__doc__).strip()
                if processor.__doc__ is not None
                else None
            ), (
                (
                    'Environment Variables:\n' +
                    '\n'.join(env_dict.keys())
                )
                if env_dict is not None and len(env_dict) > 0
                else None
            )
        )
        if part is not None and part != ''
    )
    return docs if docs != '' else None
