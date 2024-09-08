import os

from core.exceptions import LIMARException
from core.modules.docs_utils.docs_arg import docs_for

# Types
from argparse import ArgumentParser, Namespace

class EnvModule:
    """
    MM module to manage the shell environment that MM was run from.
    """

    def __init__(self):
        self._temp_proj_pattern = None
        self._temp_proj_path = None
        self._previous_dir = None

    def dependencies(self):
        return ['log', 'manifest', 'project-manifest']

    def configure_root_args(self, *, parser: ArgumentParser, **_):
        parser.add_argument('-cd', '--in-project',
            metavar="PROJECT_PATTERN",
            help="""
            Run the command in the root directory of the first project to match
            the given pattern, switching back once done.
            """)

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
        # Multiple Sub-Commands
        env_subparsers = parser.add_subparsers(dest="env_command")

        # Change Directory
        cd_subparser = env_subparsers.add_parser('cd', epilog=docs_for(self._cd))
        mod.docs.add_docs_arg(cd_subparser)
        cd_subparser.add_argument('project_pattern', metavar="PROJECT_PATTERN",
            help="""The pattern to match project names against.""")

    def start(self, *, mod: Namespace, args: Namespace, **_):
        # Get project path (temp)
        self._temp_proj_pattern = args.in_project

        if self._temp_proj_pattern is not None:
            item_set = mod.manifest.get_item_set('^project$')
            temp_proj = mod.manifest.get_item(
                self._temp_proj_pattern,
                item_set=item_set
            )
            try:
                self._temp_proj_path = temp_proj['path']
            except KeyError:
                raise LIMARException(
                    "'path' not a property of the project resolved from"
                    f" {self._temp_proj_pattern}. Are you missing the"
                    " manifest_context_uris module, or an '@uris' context in"
                    " your manifest?"
                )

        # Change dir (temp)
        mod.log.trace(f'_temp_proj_path = {self._temp_proj_path}')
        if self._temp_proj_path is not None:
            self._previous_dir = os.getcwd()

            mod.log.info(
                f'Temporarily changing directory to: {self._temp_proj_path}'
            )
            os.chdir(self._temp_proj_path)

    def __call__(self, *, mod: Namespace, args: Namespace, **_):
        if args.env_command == 'cd':
            self._cd(mod, args.project_pattern)

    def stop(self, *, mod: Namespace, **_):
        # Change dir back (temp)
        mod.log.trace(f'_previous_dir = {self._previous_dir}')
        if self._previous_dir is not None:
            os.chdir(self._previous_dir)
            mod.log.info(f'Changing directory back to: {self._previous_dir}')

    def _cd(self, mod: Namespace, project_pattern: str):
        """
        Change directory to the root directory of the first project to match
        the given pattern.
        """

        # Get project path
        item_set = mod.manifest.get_item_set('^project$')
        proj = mod.manifest.get_item(project_pattern, item_set=item_set)
        try:
            proj_path = proj['path']
        except KeyError:
            raise LIMARException(
                "'path' not a property of the project resolved from"
                f" {project_pattern}. Are you missing the"
                " manifest_context_uris module, or an '@uris' context in"
                " your manifest?"
            )

        # Change dir
        mod.log.info(f'Changing directory to: {proj_path}')
        mod.shell.add_command(f"cd '{proj_path}'")
