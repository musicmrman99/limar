import os.path

from core.exceptions import VCSException

class UrisRemote:
    @staticmethod
    def context_type():
        return 'uris'

    def on_declare_item(self, contexts, item):
        if 'project' not in item['tags'].raw():
            return

        # Remote protocol
        try:
            item['protocol'] = next(
                context['opts']['protocol']
                for context in reversed(contexts)
                if 'protocol' in context['opts']
            )
        except StopIteration:
            raise VCSException(
                "@uris (remote): Protocol not given in any parent context of"
                f" item '{item['ref']}'"
            )

        # Remote host
        try:
            item['host'] = next(
                context['opts']['host']
                for context in reversed(contexts)
                if 'host' in context['opts']
            )
        except StopIteration:
            raise VCSException(
                "@uris (remote): Remote host not given in any parent context"
                f" of item '{item['ref']}'"
            )

        # Remote path
        item['remotePath'] = item['ref']
        for context in reversed(contexts):
            if 'remote-path-exact' in context['opts']:
                item['remotePath'] = context['opts']['remote-path-exact']

            elif 'remote-path' in context['opts']:
                item['remotePath'] = os.path.join(
                    context['opts']['remote-path'], item['remotePath']
                )

        if not item['remotePath'].startswith('/'):
            # Assume the result is an absolute path if not already absolute
            item['remotePath'] = '/'+item['remotePath']
