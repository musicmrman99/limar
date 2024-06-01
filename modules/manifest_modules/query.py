from core.exceptions import VCSException

class Query:
    @staticmethod
    def context_type():
        return 'query'

    def on_declare_item(self, contexts, item, **_):
        if 'commands' not in item:
            commands = item['commands'] = {}
        if 'queries' not in item['commands']:
            queries = commands['queries'] = []

        item['tags'].add('queryable')

        for context in contexts:
            opts = context['opts']

            if 'command' not in opts:
                raise VCSException(
                    "@query context must be given a `command` to execute"
                )
            queries.append({'command': opts['command']})

            # If `parse` (a `jq` expression) is omitted, then assumes the command's
            # output is already in the desired JSON structure.
            if 'parse' in opts:
                queries[-1]['parse'] = opts['parse']
