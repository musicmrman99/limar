import os.path

from core.modules.log import LogModule

class UrisRemote:
    @staticmethod
    def context_type():
        return 'uris'

    def on_declare_item(self, contexts, item, *, logger: LogModule):
        if 'project' not in item['tags']:
            return

        # Remote protocol
        try:
            item['remoteProtocol'] = next(
                context['opts']['remote-protocol']
                for context in reversed(contexts)
                if 'remote-protocol' in context['opts']
            )
        except StopIteration:
            logger.warning(
                "@uris (remote): `remote-protocol` not given in any parent"
                f" context of item '{item['ref']}'. Remote interaction will not"
                " be usable on this item."
            )

        # Remote host
        try:
            item['remoteHost'] = next(
                context['opts']['remote-host']
                for context in reversed(contexts)
                if 'remote-host' in context['opts']
            )
        except StopIteration:
            logger.warning( # TODO: Make this use the log module
                "@uris (remote): `remote-host` not given in any parent context"
                f" of item '{item['ref']}'. Remote interaction will not be"
                " usable on this item."
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
