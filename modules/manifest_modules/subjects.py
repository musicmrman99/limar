from core.exceptions import LIMARException

class Subjects:
    @staticmethod
    def context_type():
        return 'subjects'

    def on_declare_item(self, contexts, item, *_, **__):
        subjects = {}
        for context in contexts:
            if 'opts' in context:
                subjects.update(context['opts'])
        subjects = list(subjects.keys())

        item['tags'].add(*subjects)
        item['subjects'] = subjects
