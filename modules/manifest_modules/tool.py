from core.exceptions import VCSException

class Tool:
    @staticmethod
    def context_type():
        return 'tool'

    def __init__(self):
        self._tools = {}
        self._current_tool = None

    def on_enter_context(self, context, *_, **__):
        if self._current_tool is not None:
            raise VCSException(
                "Can only have one nested @tool context: tried to nest"
                f" '{context['opts']['command']}' inside"
                f" '{self._current_tool['command']}'"
            )

        tool_command = context['opts']['command']
        if tool_command not in self._tools:
            self._tools[tool_command] = context['opts']
        self._current_tool = self._tools[tool_command]

    def on_exit_context(self, *_, **__):
        self._current_tool = None

    def on_declare_item(self, contexts, item, *_, **__):
        assert self._current_tool is not None, 'Must be set to a value, because must be in an @tool context, or Manifest would not have run this method'

        item['tags'].add(tool=self._current_tool['command'])
        item['tool'] = self._current_tool
