import os

from core.exceptions import VCSException

# Types
from core.modulemanager import ModuleManager
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace

class Env():
    """
    MM module to manage the shell environment it was run from.
    """

    def __init__(self):
        self._temp_proj_pattern = None
        self._temp_proj_path = None
        self._previous_dir = None

        self._proj_pattern = None
        self._proj_path = None

    def dependencies(self):
        return [
            'log',
            'manifest',
            'project-manifest'
        ]

    def configure_args(self, *,
            parser: ArgumentParser,
            root_parser: ArgumentParser,
            **_
    ):
        # Root Parser - Options
        root_parser.add_argument('-cd', '--in-project',
            metavar="PROJECT_PATTERN",
            help="""
            Run the command in the root directory of the first project to match
            the given pattern, switching back once done.
            """)

        # Multiple Sub-Commands
        env_subparsers = parser.add_subparsers(dest="manifest_command")

        # Change Directory
        cd_subparser = env_subparsers.add_parser('cd')

        # Change Directory - Arguments
        cd_subparser.add_argument('project_pattern', metavar="PROJECT_PATTERN",
            help="""
            Change directory to the root directory of the first project to match
            the given pattern.
            """)

    def configure(self, *, args: Namespace, **_):
        self._temp_proj_pattern = args.in_project
        if hasattr(args, 'project_pattern'):
            self._proj_pattern = args.project_pattern

    def start(self, *, mod: ModuleManager, **_):
        # Find projects and get paths
        if self._temp_proj_pattern is not None:
            temp_proj = mod.manifest().get_project(self._temp_proj_pattern)
            try:
                self._temp_proj_path = temp_proj['path']
            except KeyError:
                raise VCSException(
                    "'path' not a property of the project resolved from"
                    f" {self._temp_proj_pattern}. Are you missing the"
                    " manifest_context_uris module, or an '@uris' context in"
                    " your manifest?"
                )

        if self._proj_pattern is not None:
            proj = mod.manifest().get_project(self._proj_pattern)
            try:
                self._proj_path = proj['path']
            except KeyError:
                raise VCSException(
                    "'path' not a property of the project resolved from"
                    f" {self._proj_pattern}. Are you missing the"
                    " manifest_context_uris module, or an '@uris' context in"
                    " your manifest?"
                )

        mod.log().trace(f'_temp_proj_path = {self._temp_proj_path}')
        if self._temp_proj_path is not None:
            self._previous_dir = os.getcwd()

            mod.log().info(
                f'Temporarily changing directory to: {self._temp_proj_path}'
            )
            os.chdir(self._temp_proj_path)

    def __call__(self, *, mod: ModuleManager, **_):
        mod.log().info(f'Changing directory to: {self._proj_path}')
        mod.add_shell_command(f"cd '{self._proj_path}'")
        pass

    def stop(self, *, mod: ModuleManager, **_):
        mod.log().trace(f'_previous_dir = {self._previous_dir}')
        if self._previous_dir is not None:
            os.chdir(self._previous_dir)
            mod.log().info(f'Changing directory back to: {self._previous_dir}')
