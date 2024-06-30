class FinancialAccount:
    @staticmethod
    def context_type():
        return 'account'

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('account')
        item['tags'].add(
            type=next(context['opts']['type'] for context in reversed(contexts))
        )
