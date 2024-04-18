import os.path
import re

from core.exceptions import VCSException

class UrisRemote:
    def __init__(self) -> None:
        self._projects = set()

    def context_type(self):
        return 'uris'

    def on_declare_item(self, context, project):
        proj_ref = project['ref']
        if 'remote' not in project:
            project['remote'] = proj_ref

        try:
            context_remote_url = context['opts']['remote']
            if not re.match('^https?://', context_remote_url):
                raise ValueError('remote mapped URI is not a HTTP(S) URL')

            project['remote'] = os.path.join(context_remote_url, proj_ref)

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
                if not re.match('^https?://', project['remote']):
                    raise ValueError('project path is not a HTTP(S) URL')
            except KeyError:
                raise VCSException(
                    f"Remote of project '{project['ref']}' not defined"
                    " (required by @uris context)"
                )
            except ValueError:
                raise VCSException(
                    f"Remote of project '{project['ref']}' not a valid HTTP(S)"
                    " URL (required by @uris context)"
                )
