class Tags:
    @staticmethod
    def context_type():
        return 'tags'

    def on_declare_item(self, contexts, item):
        for context in contexts:
            item['tags'].add(**context['opts'])
