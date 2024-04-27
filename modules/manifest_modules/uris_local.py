import os.path

class UrisLocal:
    @staticmethod
    def context_type():
        return 'uris'

    def on_declare_item(self, contexts, item):
        if 'project' not in item['tags'].raw():
            return

        # Local path
        item['path'] = item['ref']
        for context in reversed(contexts):
            if 'path-exact' in context['opts']:
                item['path'] = context['opts']['path-exact']

            elif 'path' in context['opts']:
                item['path'] = os.path.join(
                    context['opts']['path'], item['path']
                )

        if not item['path'].startswith('/'):
            # Assume the result is an absolute path if not already absolute
            item['path'] = '/'+item['path']
