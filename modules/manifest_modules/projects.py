class Projects:
    def __init__(self):
        pass

    @staticmethod
    def context_type():
        return 'projects'

    @staticmethod
    def can_be_root():
        return True

    def on_declare_item(self, context, item):
        item['tags'].add('project')
