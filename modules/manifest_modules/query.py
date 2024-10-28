from core.exceptions import LIMARException

class Query:
    @staticmethod
    def context_type():
        return 'query'

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('query')

        try:
            parse_expression = next(
                context['opts']['parse']
                for context in reversed(contexts)
                if 'parse' in context['opts']
            )
        except StopIteration:
            raise LIMARException(
                f"Item '{item['ref']}' declared as query, but is missing a"
                " parse expression"
            )

        item['command']['type'] = 'query'
        item['command']['parse'] = parse_expression
