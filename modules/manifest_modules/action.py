class Action:
    @staticmethod
    def context_type():
        return 'action'

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('action')
        item['command']['type'] = 'action'
        try:
            item['command']['parse'] = next(
                context['opts']['parse']
                for context in reversed(contexts)
                if 'parse' in context['opts']
            )
        except StopIteration:
            pass

