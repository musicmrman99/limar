from core.exceptions import LIMARException
import shlex

from core.utils import list_split

class Query:
    @staticmethod
    def context_type():
        return 'query'

    def __init__(self):
        self._current_query = None

    def on_enter_context(self, context, *_, **__):
        if 'command' not in context['opts']:
            raise LIMARException(
                "@query context must be given a `command` to execute"
            )

        commands = list_split(
            shlex.split(context['opts']['command']),
            '&&'
        )

        if self._current_query is not None:
            fmt_commands = lambda commands: (
                ' && '.join(' '.join(command) for command in commands)
            )
            raise LIMARException(
                "Can only have one nested @query context: tried to nest"
                f" '{fmt_commands(commands)}' inside"
                f" '{fmt_commands(self._current_query['commands'])}'"
            )

        self._current_query = {
            'type': 'query',
            'commands': commands,
            'parse': context['opts']['parse']
        }

    def on_exit_context(self, *_, **__):
        self._current_query = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('query')
        item['command'] = self._current_query
