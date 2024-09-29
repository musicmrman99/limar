from core.exceptions import LIMARException

class PrimarySubject:
    @staticmethod
    def context_type():
        return 'primary-subject'

    def __init__(self):
        self._primary_subject: str | None = None

    def on_enter_context(self, context, *_, **__):
        primary_subject = next(iter(context['opts'].keys()))
        if self._primary_subject is not None:
            raise LIMARException(
                "Can only have one nested @subjects context: tried to nest"
                f" primary-subject '{primary_subject}' inside primary-subject"
                f" '{self._primary_subject}'"
            )
        self._primary_subject = primary_subject

    def on_exit_context(self, *_, **__):
        self._primary_subject = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['primarySubject'] = self._primary_subject
