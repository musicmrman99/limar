from core.exceptions import LIMARException
from modules.command_utils.command_transformer import CommandTransformer

class Command:
    def __init__(self):
        self._current_command = None
        self._command_tr = CommandTransformer()

    @staticmethod
    def context_type():
        return 'command'

    @staticmethod
    def can_be_root():
        return True

    def on_enter_context(self, context, *_, **__):
        # Ignore 'requirement' contexts
        if len(context['opts']) == 0:
            return

        # Require command in 'declaration' contexts
        if 'command' not in context['opts']:
            raise LIMARException(
                "A declaration @command context must be given a `command` to"
                " execute"
            )

        command = self._command_tr.parse(context['opts']['command'])

        if self._current_command is not None:
            raise LIMARException(
                "Can only have one nested @query context: tried to nest"
                f" '{self._command_tr.format_text(command)}' inside"
                f" '{self._command_tr.format_text(self._current_command)}'"
            )

        self._current_command = command

    def on_exit_context(self, *_, **__):
        self._current_command = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('command')
        item['command'] = self._current_command

    def on_exit_manifest(self, items, item_sets, *_, **__):
        # Verify that required contexts were declared for all commands
        for item in items.values():
            if (
                'command' in item['tags'] and
                'command' not in item and

                # Ignore any items with a tag that starts with `__`
                all(
                    not name.startswith('__')
                    for name in item['tags'].raw().keys()
                )
            ):
                raise LIMARException(
                    "@command context requires a command to be declared for"
                    f" item '{item['ref']}'"
                )
