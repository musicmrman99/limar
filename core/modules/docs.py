from core.modulemanager import ModuleAccessor
from core.modules.docs_utils.docs_arg import add_docs_arg

# Types
from argparse import ArgumentParser

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
