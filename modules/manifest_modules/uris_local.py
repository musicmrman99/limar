import os.path

class UrisLocal:
    @staticmethod
    def context_type():
        return 'uris'

    def on_declare_item(self, contexts, item, **_):
        if 'project' not in item['tags'].raw():
            return

        # Local path
        prefix = ''
        ref = item['ref']
        path = None
        for context in reversed(contexts):
            if 'path-abs' in context['opts']:
                path = context['opts']['path-abs']
                break

            if 'path-ref' in context['opts'] and ref == item['ref']:
                ref = context['opts']['path-ref']

            if 'path' in context['opts']:
                # NOTE: A prefix that is already absolute will be unchanged
                prefix = os.path.join(context['opts']['path'], prefix)

        if path is None:
            path = os.path.join(prefix, ref)

        # Assume the result is an absolute path if not already absolute
        item['tags'].add(path=os.path.join('/', path))
