from argparse import Namespace
import os.path

from core.exceptions import LIMARException
from core.modules.log import LogModule

class UrisRemote:
    KEY_NAMES = Namespace(
        REMOTE_HOST='remote-host',
        REMOTE_PROTOCOL='remote-protocol',
        REMOTE_PATH='remote-path',
        REMOTE_PATH_REF='remote-path-ref',
        REMOTE_PATH_ABS='remote-path-abs'
    )

    URL_FORMATTERS = {
        'https': lambda host, path, _: (
            f"https://{host}{path}"
        ),
        'ssh': lambda host, path, opts: (
            f"{opts['remote-user']}@{host}:{path[1:]}"
        )
    }

    @staticmethod
    def context_type():
        return 'uris'

    def on_declare_item(self, contexts, item, *, logger: LogModule):
        if 'project' not in item['tags']:
            return

        # Remote host
        try:
            host = item['remoteHost'] = next(
                context['opts'][self.KEY_NAMES.REMOTE_HOST]
                for context in reversed(contexts)
                if self.KEY_NAMES.REMOTE_HOST in context['opts']
            )
        except StopIteration:
            logger.warning( # TODO: Make this use the log module
                f"@uris (remote): '{self.KEY_NAMES.REMOTE_HOST}' option not"
                f" given in any parent context of item '{item['ref']}'. Remote"
                " interaction will not be usable on this item."
            )

        # Remote protocols
        protocols = list(dict.fromkeys(
            context['opts'][self.KEY_NAMES.REMOTE_PROTOCOL]
            for context in reversed(contexts)
            if self.KEY_NAMES.REMOTE_PROTOCOL in context['opts']
        ))
        if len(protocols) == 0:
            logger.warning(
                f"@uris (remote): '{self.KEY_NAMES.REMOTE_PROTOCOL}' option"
                f" not given in any parent context of item '{item['ref']}'."
                " Remote interaction will not be usable on this item."
            )
        for protocol in protocols:
            if protocol not in self.URL_FORMATTERS:
                raise LIMARException(
                    f"Unsupported remote protocol '{protocol}' specified"
                    f" for project '{item['ref']}'"
                )
        item['remoteProtocols'] = protocols

        # Remote path
        prefix = ''
        ref = item['ref']
        path = None
        for context in reversed(contexts):
            # Take lowest instance (defines the whole path)
            if self.KEY_NAMES.REMOTE_PATH_ABS in context['opts']:
                path = context['opts'][self.KEY_NAMES.REMOTE_PATH_ABS]
                break

            # Take lowest instance (but keep looking for path fragments)
            if (
                self.KEY_NAMES.REMOTE_PATH_REF in context['opts'] and
                ref == item['ref']
            ):
                ref = context['opts'][self.KEY_NAMES.REMOTE_PATH_REF]

            # Combine instances up to the lowest absolute path
            if self.KEY_NAMES.REMOTE_PATH in context['opts']:
                prefix = os.path.join(
                    context['opts'][self.KEY_NAMES.REMOTE_PATH],
                    prefix
                )

        if path is None:
            path = os.path.join(prefix, ref)
        path = item['remotePath'] = os.path.abspath(os.path.join('/', path))

        # Construct the full URL for the remote path for each protocol
        formatter_opts = {
            opt_name: opt_value
            for context in contexts
            for opt_name, opt_value in context['opts'].items()
            if (
                opt_name.startswith('remote-') and
                opt_name not in vars(self.KEY_NAMES).values()
            )
        }

        for protocol in protocols:
            formatter = self.URL_FORMATTERS[protocol]
            try:
                item[f'remote:{protocol}'] = (
                    formatter(host, path, formatter_opts)
                )
            except KeyError as e:
                raise LIMARException(
                    f"Context option '{e.args[0]}' not found, but required"
                    f" by URL formatter for '{protocol}' protocol when"
                    f" formatting remote URL for item '{item['ref']}'"
                )
