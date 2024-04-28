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
        prefix = ''
        ref = item['ref']
        remotePath = None
        for context in reversed(contexts):
            if 'remote-path-abs' in context['opts']:
                remotePath = context['opts']['remote-path-abs']
                break

            if 'remote-path-ref' in context['opts'] and ref == item['ref']:
                ref = context['opts']['remote-path-ref']

            if 'remote-path' in context['opts']:
                # NOTE: A prefix that is already absolute will be unchanged
                prefix = os.path.join(context['opts']['remote-path'], prefix)

        if remotePath is None:
            remotePath = os.path.join(prefix, ref)

        # Assume the result is an absolute path if not already absolute
        item['remotePath'] = os.path.join('/', remotePath)
