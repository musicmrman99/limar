import os.path

from core.exceptions import VCSException

class UrisLocal:
    def __init__(self):
        self._projects = set()

    @staticmethod
    def context_type():
        return 'uris'

    def on_declare_item(self, context, project):
        proj_ref = project['ref']
        if 'path' not in project:
            project['path'] = proj_ref

        try:
            context_local_path = context['opts']['local']
            if not context_local_path.startswith('/'):
                raise ValueError('local mapped URI not absolute')

            project['path'] = os.path.join(context_local_path, proj_ref)

        except (KeyError, ValueError):
            pass # For now, until all nested contexts have been tried

    def on_exit_context(
            self, context, projects, project_sets
    ):
        self._projects = self._projects | projects.keys()

    def on_exit_manifest(self, projects, project_sets):
        projects = (
            project
            for project in projects.values()
            if project['ref'] in self._projects
        )

        for project in projects:
            try:
                if not project['path'].startswith('/'):
                    raise ValueError('project path is not absolute')
            except KeyError:
                raise VCSException(
                    f"Path of project '{project['ref']}' not defined"
                    " (required by @uris context)"
                )
            except ValueError:
                raise VCSException(
                    f"Path of project '{project['ref']}' not absolute"
                    " (required by @uris context)"
                )
