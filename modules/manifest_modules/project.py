class Project:
    def __init__(self):
        pass

    @staticmethod
    def context_type():
        return 'project'

    @staticmethod
    def can_be_root():
        return True

    def on_declare_item(self, contexts, item, **_):
        item['tags'].add('project')
