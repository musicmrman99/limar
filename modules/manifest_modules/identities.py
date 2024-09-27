from core.exceptions import LIMARException

class Identities:
    @staticmethod
    def context_type():
        return 'identities'

    def __init__(self):
        self._identities = None

    def on_enter_context(self, context, *_, **__):
        identities = context['opts']
        if self._identities is not None:
            raise LIMARException(
                "Can only have one nested @identities context: tried to nest"
                f" identities '{identities}' inside identities"
                f" '{self._identities}'"
            )
        self._identities = identities

    def on_exit_context(self, *_, **__):
        self._identities = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['identities'] = self._identities
