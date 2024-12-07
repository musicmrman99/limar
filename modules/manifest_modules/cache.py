class Cache:
    def __init__(self):
        self._current_cache_config = None

    @staticmethod
    def context_type():
        return 'cache'

    def on_declare_item(self, contexts, item, *_, **__):
        cache = {}

        try:
            cache['enabled'] = next(
                not 'disabled' in context['opts'] # 'disabled' has higher precedence
                for context in reversed(contexts)
                if 'enabled' in context['opts'] or 'disabled' in context['opts']
            )
        except StopIteration:
            cache['enabled'] = True

        try:
            cache['retention'] = next(
                context['opts']['retension']
                for context in reversed(contexts)
                if 'retention' in context['opts']
            )
        except StopIteration:
            cache['retention'] = 'batch'

        item['cache'] = cache

    def on_exit_manifest(self, items, item_sets, *_, **__):
        # Update cache properties to reflect transitive dependencies
        for item in items.values():
            if 'command' not in item or 'cache' not in item:
                continue

            item['cache']['enabled'] = item['cache']['enabled'] and all(
                'cache' in items[dep_ref] and items[dep_ref]['cache']['enabled']
                for dep_ref in item['command']['transitiveDependencies']
            )
