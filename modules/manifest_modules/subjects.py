from core.exceptions import LIMARException

class Subjects:
    @staticmethod
    def context_type():
        return 'subjects'

    def __init__(self):
        self._subjects: dict[str, str] | None = None

    def on_enter_context(self, context, *_, **__):
        subjects: dict[str, str] = context['opts']
        if self._subjects is not None:
            raise LIMARException(
                "Can only have one nested @subjects context: tried to nest"
                f" subjects '{subjects}' inside subjects"
                f" '{self._subjects}'"
            )
        self._subjects = subjects

    def on_exit_context(self, *_, **__):
        self._subjects = None

    def on_declare_item(self, contexts, item, *_, **__):
        assert self._subjects is not None, f'{self.on_declare_item.__name__}() called before {self.on_enter_context.__name__}()'

        item['tags'].add(*self._subjects.keys())
        item['subjects'] = self._subjects
