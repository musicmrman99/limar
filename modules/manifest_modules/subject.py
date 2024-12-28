from core.exceptions import LIMARException

class Subject:
    @staticmethod
    def context_type():
        return 'subject'

    @staticmethod
    def can_be_root():
        return True

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('subject')

        # Ignore any items with a tag that starts with `__`
        if any(
            name.startswith('__')
            for name in item['tags'].raw().keys()
        ):
            return

        # Add ID field and subject dependencies
        if 'id' not in item['tags']:
            raise LIMARException(f"@subject '{item['ref']}' missing 'id' tag")
        item['id'] = item['tags'].get('id')

        dependencies = []
        for tag, value in item['tags'].raw().items():
            if value is None and tag.startswith('/'):
                dependencies.append(tag)
        item['dependencies'] = dependencies
