import os
from argparse import ArgumentParser, Namespace
import re

from commandset import CommandSet
from environment import Environment
from exceptions import VCSException

# TODO:
# - Verify (-v, --verify) makes resolve verify that the specified path exists (mutex with -c)
# - Candidacy (-c, --candidate) makes resolve come up with a proposed path where the project/list could be stored in future (mutex with -v)

class Resolve():
    @staticmethod
    def setup_args(parser: ArgumentParser, **_):
        # Arguments
        parser.add_argument('resolve_target',
            choices=['project', 'project-list'],
            help="""
            The type of object to resolve the pattern to; one of
              'project-list' (resolve to a project list reference)
              or 'project' (resolve to a project reference)
            """)

        parser.add_argument('pattern', metavar='PATTERN',
            help='The regex pattern to resolve to a reference')

        # Options
        parser.add_argument('-l', '--location',
            choices=['local', 'remote'],
            help='Specify the location to reosolve the project pattern to')

        parser.add_argument('-r', '--relative-to',
            choices=['root', 'manifest', 'current'],
            help="""
            Specify the location that the output reference should be relative
            to, or one of:
                'root' (resolve to an aboslute URI),
                'manifest' (resolve to a URI relative to either
                    the manifest directory (if resolving a project list), or
                    the relevant URI in the closest @map-uris context to the
                        resolved project in the manifest (if resolving a
                        project)),
                or 'current' (relative to the current directory)
            """)

        parser.add_argument('--project-list', metavar='PROJECT_LIST_PATTERN',
            help="""
            If resolving a project, this is a pattern that matches the
            project list to use to resolve the project
            """)

    def __init__(self,
            cmd: CommandSet = None,
            env: Environment = None,
            args: Namespace = None
    ):
        self._cmd = cmd
        self._env = env
        self._file_cache = {}

        self._search_project_list = env.get('resolve.default.project_list')
        if args.project_list is not None:
            self._search_project_list = args.project_list

    def __call__(self, args):
        output = ''

        if args.resolve_target == 'project':
            output = self.project(
                args.pattern,
                project_list=args.project_list,
                location=args.location,
                relative_to=args.relative_to
            )
            self._cmd.log().info('resolved project to:', output)

        elif args.resolve_target == 'project-list':
            output = self.project_list(
                args.pattern,
                relative_to=args.relative_to
            )
            self._cmd.log().info('resolved project list to:', output)

        return output

    def project(self,
            pattern,
            *_,
            project_list=None,
            location=None,
            relative_to=None
    ):
        if project_list is None:
            project_list = self._search_project_list
        if location is None:
            location = 'local'
        if relative_to is None:
            relative_to = 'root'
        self._cmd.log().trace(f"resolve.project('{pattern}', project_list='{project_list}', location={location}, relative_to={relative_to})")

        self._cmd.log().trace('loading project list for project resolve ...')
        project_list_path = self.project_list(project_list)
        project_list_data = self._get_project_list(project_list_path)
        self._cmd.log().trace('project list data:', project_list_data)

        project_regex = re.compile(pattern)
        try:
            found = next(
                project
                for project in project_list_data
                if project_regex.search(project)
            )
            self._cmd.log().trace('found:', found)
            # check for existance of project, not just of manifest entry
        except StopIteration:
            raise VCSException(f"Project list not found from pattern '{pattern}'")

        return found

    def project_list(self,
            pattern,
            *_,
            relative_to=None
    ):
        if relative_to is None:
            relative_to = 'root'
        self._cmd.log().trace(f'resolve.project_list({pattern}, relative_to={relative_to})')

        self._cmd.log().trace('searching for project list in:', self._env.get('resolve.manifest'))
        manifest_root = self._env.get('resolve.manifest')
        project_list_regex = re.compile(f'^{pattern}-projects.txt')

        try:
            found = next(
                os.path.join(dirname, file)
                for dirname, dirs, files in os.walk(manifest_root)
                for file in files
                if project_list_regex.match(file)
            )
            self._cmd.log().trace('found:', found)
        except StopIteration:
            raise VCSException(f"Project list not found from pattern '{pattern}'")

        if relative_to == 'manifest':
            found = os.path.relpath(found, manifest_root)
            self._cmd.log().trace('mapped (relative_to=manifest):', found)

        return found

    def _get_project_list(self, path):
        if path not in self._file_cache.keys():
            with open(path) as file:
                self._file_cache[path] = file.read().splitlines()
        return self._file_cache[path]

    def _exists(self, path):
        pass # Needed for '--verify-exists'
