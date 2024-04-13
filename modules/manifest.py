import hashlib
from operator import itemgetter
import pickle
import re

from core.exceptions import VCSException

# Types
from core.modulemanager import ModuleManager
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace

class Manifest():
    """
    MM module to parse a manifest file and provide information about the
    projects it defines.
    """

    # Lifecycle
    # --------------------

    def __init__(self):
        self._context_module_factories = []
        self._projects: dict[str, dict[str, object]] = None
        self._project_sets: dict[str, dict[str, dict[str, object]]] = None

    def dependencies(self):
        return ['log']

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('PATH')
        parser.add_variable('DEFAULT_PROJECT_SET', default_is_none=True)

    def configure_args(self, *, parser: ArgumentParser, **_):
        # Options
        parser.add_argument('-p', '--property',
            action='append',
            help="""
            Specify a property to include in the output. If given, excludes all
            properties not given. May be given more than once to include
            multiple properties. Supported properties include 'ref', 'tags', and
            any properties added by other MM modules.
            """)

        # Subcommands
        manifest_subparsers = parser.add_subparsers(dest="manifest_command")

        # Subcommands / Resolve Project
        resolve_parser = manifest_subparsers.add_parser('project')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to a project reference')

        resolve_parser.add_argument('--project-set',
            metavar='PROJECT_SET_PATTERN',
            help="""
            A pattern that matches the project set to use to resolve the project
            """)

        # Subcommands / Resolve Project Set
        resolve_parser = manifest_subparsers.add_parser('project-set')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to a project set')

    def configure(self, *, mod: ModuleManager, env: Namespace, **_):
        # For methods that aren't directly given it
        self._mod = mod

        self._manifest_path = env.VCS_MANIFEST_PATH
        self._default_project_set = env.VCS_MANIFEST_DEFAULT_PROJECT_SET

    def start(self, *, mod: ModuleManager, **_):
        # TODO: This opens/reads/closes the manifest file twice - is this a big
        #       enough performance hit to be worth fixing?

        # Determine cache filename
        with open(self._manifest_path, 'rb') as manifest:
            sha1 = hashlib.md5(manifest.read())
        cache_path = self._manifest_path+'.'+sha1.hexdigest()+'.pickle'

        # Try cache
        try:
            with open(cache_path, 'rb') as cache_file:
                projects, project_sets = itemgetter(
                    'projects',
                    'project_sets'
                )(pickle.load(cache_file))

        except FileNotFoundError:
            # Import deps (these are slow to import, so only (re)parse if needed)
            from antlr4 import FileStream, CommonTokenStream, ParseTreeWalker
            from modules.manifest_lang.build.ManifestLexer import ManifestLexer
            from modules.manifest_lang.build.ManifestParser import ManifestParser
            from modules.manifest_lang.manifest_listener import ManifestListenerImpl

            # Create context modules
            context_modules = {}
            for module_factory in self._context_module_factories:
                context_mod = module_factory()
                context_mod_type = context_mod.context_type()
                if context_mod_type not in context_modules:
                    context_modules[context_mod_type] = []
                context_modules[context_mod_type].append(context_mod)

            # Setup parser
            input_stream = FileStream(self._manifest_path)
            lexer = ManifestLexer(input_stream)
            tokens = CommonTokenStream(lexer)
            parser = ManifestParser(tokens)
            tree = parser.manifest()

            # Parse
            listener = ManifestListenerImpl(mod.log(), context_modules)
            walker = ParseTreeWalker()
            walker.walk(listener, tree)

            projects = listener.projects
            project_sets = listener.project_sets

            # Cache results
            with open(cache_path, 'wb') as cache_file:
                pickle.dump(
                    {
                        'projects': projects,
                        'project_sets': project_sets
                    },
                    cache_file
                )

        # Extract results
        self._projects = projects
        self._project_sets = project_sets

    def __call__(self, *, mod: ModuleManager, args: Namespace, **_):
        mod.log().trace(f"manifest(args={args})")

        output = ''

        if args.manifest_command == 'project':
            output = self.get_project(
                args.pattern,
                project_set_pattern=args.project_set,
                properties=args.property
            )
            print(self._format_project(output))

        if args.manifest_command == 'project-set':
            output = self.get_project_set(
                args.pattern,
                properties=args.property
            )
            print(self._format_project_set(output))

        return output

    # Configuration
    # --------------------

    def add_context_module(self, *modules):
        """
        Allows other modules to extend the manifest format with new contexts.
        """

        # It is only useful to configure context modules *before* the manifest
        # is parsed. If it's already been parsed, then registration will have no
        # effect. As such, fail loudly to tell ModuleManager module developers
        # that they've done something wrong.
        if self._projects is not None and len(modules) > 0:
            raise VCSException(
                f"Attempted registration of context module '{modules[0]}' after"
                " manifest has been parsed. This was probably caused by"
                " inappropriate use of mod.Manifest.add_context_module() by the"
                " last ModuleManager module to be invoked (possibly"
                " internally)."
            )

        for module in modules:
            if module not in self._context_module_factories:
                self._context_module_factories.append(module)

    # Invokation
    # --------------------

    def get_project_set(self,
            pattern: str = None,
            properties: 'list[str]' = None
    ):
        self._mod.log().trace(
            "manifest.get_project_set("
                +(f"{pattern}" if pattern is None else f"'{pattern}'")+","
                f" properties={properties}"
            ")"
        )

        if pattern is None:
            if self._default_project_set is None:
                project_set = self._projects
            else:
                project_set = self._project_sets[self._default_project_set]
        else:
            project_set_regex = re.compile(pattern)
            try:
                project_set = next(
                    self._project_sets[project_set_name]
                    for project_set_name in self._project_sets.keys()
                    if project_set_regex.search(project_set_name)
                )
            except (KeyError, StopIteration):
                raise VCSException(
                    f"Project set not found from pattern '{pattern}'"
                )

        if properties is None:
            return project_set
        else:
            return {
                name: self._filtered_project(project, properties)
                for name, project in project_set.items()
            }

    def get_project(self,
            pattern: str,
            *,
            project_set_pattern: str = None,
            properties: 'list[str]' = None
    ):
        self._mod.log().trace(
            "manifest.get_project("
                +(pattern if pattern is None else f"'{pattern}'")+","
                f" project_set_pattern={project_set_pattern},"
                f" properties={properties}"
            ")"
        )

        project_set = self.get_project_set(project_set_pattern)

        project_regex = re.compile(pattern)
        try:
            project = next(
                project
                for project in project_set.values()
                if project_regex.search(project['ref'])
            )
            self._mod.log().debug('found:', project)
        except StopIteration:
            raise VCSException(
                f"Project not found from pattern '{pattern}'"
            )

        # TODO:
        # - Check for existance of project, not just of manifest entry
        # - Map to relative if relative_to is 'manifest' or 'relative'
        #
        # Ideas:
        # - Verify (-v, --verify) makes resolve verify that the specified project exists (mutex with -c)
        # - Candidate (-c, --candidate) makes resolve come up with a proposed project path where the project/list could be stored in future (mutex with -v)

        if properties is None:
            return project
        else:
            return self._filtered_project(project, properties)

    # Utils
    # --------------------

    def _format_project(self, project: 'dict[str, object]'):
        extra_attrs = '\n'.join(
            f'{key}: {value}'
            for key, value in project.items()
            if key not in ['ref', 'tags']
        )
        return '\n'.join([
            *(
                [f"ref: {project['ref']}"]
                if 'ref' in project else []
            ),
            *(
                [f"tags: {', '.join(project['tags'].keys())}"]
                if 'tags' in project else []
            ),
            *(
                [extra_attrs]
                if extra_attrs != '' else []
            )
        ])

    def _format_project_set(self, project_set: 'dict[str, dict[str, object]]'):
        return '\n\n'.join(
            self._format_project(project)
            for project in project_set.values()
        )

    def _filtered_project(self, project, properties):
        return {
            property: project[property]
            for property in properties
            if property in project
        }
