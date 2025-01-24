from argparse import ArgumentParser, Action, Namespace
from textwrap import dedent

from core.utils import render_table, tabulate
from core.envparse import EnvVariableSpecs
from core.modules.docs_utils.helpformatter import MMHelpFormatter

# Types
from typing import Callable

# See MMHelpFormatter for how this works. Yes, this is a somewhat ugly hack, but
# is better than needing two parse passes and varying the argument help text
# across all modules based on whether `--docs` was given. That would require
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

def docs_for(
        processor: Callable,
        env_names: list[str] | None = None,
        *,
        env_specs: EnvVariableSpecs | None = None,
        env: Namespace | None = None
):
    if env_names is None:
        env_names = []
        env_specs = {}
        env = Namespace()
    else:
        if env_specs is None or env is None:
            raise ValueError(
                'If passing env_names, then env_specs and env are required'
                ' keyword arguments'
            )

    env_dict = vars(env)
    env_data = (
        [
            {
                'Name': name,
                'Current Value': (
                    repr(env_dict[name])
                    if name in env_dict
                    else 'Undefined'
                ),
                # Env specs must be declared for all names given
                'Description': str(env_specs[name]['help'])
            }
            for name in env_names
        ]
        if len(env_dict) > 0
        else []
    )
    env_table = tabulate(env_data, obj_mapping='all')

    docs = '\n\n'.join(
        part
        for part in (
            (
                dedent(processor.__doc__).strip()
                if processor.__doc__ is not None
                else None
            ), (
                (
                    'Environment Variables:\n\n'+
                    render_table(
                        env_table,
                        has_headers=True,
                        column_weights=[None, None, 1]
                    )
                )
                if len(env_data) > 0
                else None
            )
        )
        if part is not None and part != ''
    )
    return docs if docs != '' else None
