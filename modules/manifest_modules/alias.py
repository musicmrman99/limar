class Alias:
    @staticmethod
    def context_type():
        return 'alias'

    def on_declare_item(self, contexts, item, *_, **__):
        item['aliases'] = [
            alias
            for context in contexts
            for alias in context['opts']
        ]
