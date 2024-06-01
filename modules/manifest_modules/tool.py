from core.exceptions import VCSException

class Tool:
    @staticmethod
    def context_type():
        return 'tool'

    @staticmethod
    def can_be_root():
        return True

    def on_declare_item(self, contexts, item, **_):
        # Verify correct context nesting
        contexts_with_options = [
            context
            for context in contexts
            if len(context['opts']) > 0
        ]
        if len(contexts_with_options) != 1:
            raise VCSException(
                "Each item in an @tool context must have exactly one nested"
                f" @tool context with options: '{item['ref']}' had"
                f" {len(contexts_with_options)} nested contexts with options"
            )
        options = contexts_with_options[0]['opts']

        # Set data
        item['tags'].add('tool')
        if 'context' in options:
            item['context'] = options['context']
        if 'description' in options:
            item['description'] = options['description']

    def on_exit_manifest(self, items, item_sets, **_):
        # Verify that required contexts were declared
        for item in items.values():
            if 'tool' in item['tags'] and 'commands' not in item:
                raise VCSException(
                    "@tool context requires a command type to be declared for"
                    f" item '{item['ref']}'"
                )
