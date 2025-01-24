from core.envparse import EnvironmentParser
from core.modulemanager import ModuleAccessor
from core.modules.docs_utils.docs_arg import add_docs_arg, docs_for

# Types
from typing import Callable
from argparse import ArgumentParser, Namespace

class DocsModule:
    """
    MM module that provides other MM modules with an option to show the
    long-form help test for each of their commands.
    """

    @ModuleAccessor.invokable_as_function
    def add_docs_arg(self, parser: ArgumentParser):
        """
        Add an option to the given parser to show its help text with the
        extended documentation for the command included. Extended docs should be
        added to each subparser as an epilog.
        """

        add_docs_arg(parser)

    @ModuleAccessor.invokable_as_function
    def docs_for(self,
            processor: Callable,
            env_names: list[str] | None = None,
            *,
            env_parser: EnvironmentParser | None = None,
            env: Namespace | None = None
    ) -> str | None:
        """
        Generate documentation for an argument parser or subparser in a standard
        format.

        If the given arguments supply no documentation, return None.
        """

        return docs_for(
            processor,
            env_names,
            env_specs=(
                env_parser.get_variables(collapse_prefixes=True)
                if env_parser is not None
                else None
            ),
            env=env
        )
