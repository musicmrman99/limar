from core.exceptions import VCSException

class Query:
    @staticmethod
    def context_type():
        return 'query'

    def __init__(self):
        self._current_query = None

    def on_enter_context(self, context, *_, **__):
        if 'command' not in context['opts']:
            raise VCSException(
                "@query context must be given a `command` to execute"
            )

        if self._current_query is not None:
            raise VCSException(
                "Can only have one nested @query context: tried to nest"
                f" '{context['opts']['command']}' inside"
                f" '{self._current_query['command']}'"
            )

        self._current_query = {
            'type': 'query',
            **context['opts']
        }

    def on_exit_context(self, *_, **__):
        self._current_query = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('query')
        item['command'] = self._current_query
