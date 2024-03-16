import os
import re

from antlr4 import FileStream, CommonTokenStream, ParseTreeWalker
from modules.manifest_lang.build.ManifestLexer import ManifestLexer
from modules.manifest_lang.build.ManifestParser import ManifestParser
from modules.manifest_lang.build.ManifestListener import ManifestListener

from core.exceptions import VCSException

# Types
from core.modulemanager import ModuleManager
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace
from core.modules.log import Log

class ManifestListenerImpl(ManifestListener):
    def __init__(self,
            logger: Log,
            context_modules: 'dict[str, list]' = None
    ):
        """
        Initialises the manifest listener.

        context_modules must be a dictionary of the following format:

            {'context-type-name': [context_module, ...], ...}

        Each module must define a `context_type()` method that returns the
        context type that module is for as a string, and may define any of the
        following methods:

        - `on_enter_manifest()`
        - `on_enter_context(context)`
        - `on_declare_project(context, project)`
        - `on_declare_project_set(context, project_set)`
        - `on_exit_context(context, projects, project_sets)`
          - Note that projects and project_sets only contain those that were
            declared in this context.
        - `on_exit_manifest(projects, project_sets)`
        """

        # Outputs
        self.projects = {}
        self.project_sets = {}

        # Internal operations
        self._logger = logger

        self._context_modules = context_modules
        if self._context_modules is None:
            self._context_modules = {}

        self._contexts = []
        self._tag_operand_stack = []

    def enterManifest(self, ctx: ManifestParser.ManifestContext):
        # Call 'on_enter_manifest' on all context modules
        self._run_context_lifecycle_point('on_enter_manifest', [])

    def exitManifest(self, ctx: ManifestParser.ManifestContext):
        # Call 'on_exit_manifest' on all context modules
        self._run_context_lifecycle_point('on_exit_manifest',
            [self.projects, self.project_sets]
        )

    def enterContext(self, ctx: ManifestParser.ContextContext):
        context_type = ctx.typeName.text
        if context_type not in self._context_modules.keys():
            self._logger.warn(
                f"Unsupported context type '{context_type}' found."
                " Ignoring context."
            )
            # Symbolises an unrecognised context (not an error for forwards
            # compatibility and to support dynamic modules)
            self._contexts.append(NotImplementedError)
            return

        context = {
            'type': context_type,
            'opts': {},
            'projects': {},
            'project_sets': {}
        }

        if ctx.contextOpts() is not None:
            for opt in ctx.contextOpts().contextOpt():
                context['opts'][opt.optName.text] = opt.optValue.getText()

        self._contexts.append(context)

        # Call 'on_enter_context' on all context modules registered for this
        # context
        self._run_context_lifecycle_point('on_enter_context',
            [context],
            context['type']
        )

    def exitContext(self, ctx: ManifestParser.ContextContext):
        old_context = self._contexts.pop()
        if old_context is NotImplementedError:
            return # Ignore unrecognised contexts

        # Call 'on_exit_context' on all context modules registered for this
        # context
        self._run_context_lifecycle_point('on_exit_context',
            [
                old_context,
                old_context['projects'],
                old_context['project_sets']
            ],
            old_context['type']
        )

    def enterProject(self, ctx: ManifestParser.ProjectContext):
        proj_ref = ctx.ref().getText()

        # Add to main project set
        self.projects[proj_ref] = {
            'ref': proj_ref,
            'tags': {}
        }
        if ctx.tagList() is not None:
            self.projects[proj_ref]['tags'] = {
                tag.getText(): None
                for tag in ctx.tagList().tag()
            }

        # Add to all relevant project sets
        for tag in self.projects[proj_ref]['tags']:
            if tag not in self.project_sets.keys():
                self.project_sets[tag] = {}
            self.project_sets[tag][proj_ref] = self.projects[proj_ref]

        # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['projects'][proj_ref] = self.projects[proj_ref]

        # Call 'on_declare_project' on all context modules registered for all
        # active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_project',
                [context, self.projects[proj_ref]],
                context['type']
            )

    def enterTagBase(self, ctx: ManifestParser.TagBaseContext):
        project_set_name = ctx.tag().getText()
        project_set = {} # In case the project set isn't defined
        if project_set_name in self.project_sets:
            project_set = self.project_sets[project_set_name]
        self._tag_operand_stack.append(project_set)

    def exitTagOp(self, ctx: ManifestParser.TagOpContext):
        right_proj_set = self._tag_operand_stack.pop()
        left_proj_set = self._tag_operand_stack.pop()
        if ctx.op.text == '&':
            result = {
                proj_set_name: left_proj_set[proj_set_name]
                for proj_set_name in left_proj_set.keys() & right_proj_set.keys()
            }
        elif ctx.op.text == '|':
            result = {
                proj_set_name: (
                    left_proj_set[proj_set_name]
                    if proj_set_name in left_proj_set
                    else right_proj_set[proj_set_name]
                )
                for proj_set_name in left_proj_set.keys() | right_proj_set.keys()
            }
        self._tag_operand_stack.append(result)

    def exitProjectSet(self, ctx: ManifestParser.ProjectSetContext):
        proj_set_ref = ctx.ref().getText()

        # Add to main project sets
        self.project_sets[proj_set_ref] = self._tag_operand_stack.pop()

        # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['project_sets'][proj_set_ref] = (
                self.project_sets[proj_set_ref]
            )

        # Call 'on_declare_project_set' on all context modules registered for
        # all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_project_set',
                [context, self.project_sets[proj_set_ref]],
                context['type']
            )

    def _run_context_lifecycle_point(self, name, args, context_type=None):
        """
        Run the named context lifecycle point for all context modules, passing
        args.

        If context_type is given, then only run the lifecycle point on context
        modules for that context type.
        """

        if context_type is not None:
            try:
                module_set = self._context_modules[context_type]
            except KeyError:
                module_set = []
        else:
            module_set = [
                mod
                for mod_set in self._context_modules.values()
                for mod in mod_set
            ]

        for module in module_set:
            if hasattr(module, name):
                getattr(module, name)(*args)

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

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('PATH')
        parser.add_variable('DEFAULT_PROJECT_SET', default_is_none=True)

    def configure_args(self, *, parser: ArgumentParser, **_):
        manifest_subparsers = parser.add_subparsers(dest="manifest_command")

        # Resolve Project
        resolve_parser = manifest_subparsers.add_parser('project')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to a project reference')

        # Resolve Project: Options
        resolve_parser.add_argument('-p', '--property',
            action='append',
            help="""
            Specify a property to include in the output. If given, excludes all
            properties not given. May be given more than once to include
            multiple properties. Supported properties include 'ref', 'tags', and
            any properties added by other MM modules.
            """)

        resolve_parser.add_argument('--project-set',
            metavar='PROJECT_SET_PATTERN',
            help="""
            A pattern that matches the project set to use to resolve the project
            """)

        # Resolve Project Set
        resolve_parser = manifest_subparsers.add_parser('project-set')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to a project set')

        # Resolve Project Set: Options
        resolve_parser.add_argument('-p', '--property',
            action='append',
            help="""
            Specify a property to include in the output. If given, excludes all
            properties not given. May be given more than once to include
            multiple properties. Supported properties include 'ref', 'tags', and
            any properties added by other MM modules.
            """)

    def configure(self, *, mod: ModuleManager, env: Namespace, **_):
        # For methods that aren't directly given it
        self._mod = mod

        self._manifest_path = env.VCS_MANIFEST_PATH
        self._default_project_set = env.VCS_MANIFEST_DEFAULT_PROJECT_SET

    def start(self, *, mod: ModuleManager, **_):
        # Create context modules
        context_modules = {}
        for module_factory in self._context_module_factories:
            context_mod = module_factory()
            if context_mod.context_type() not in context_modules:
                context_modules[context_mod.context_type()] = []
            context_modules[context_mod.context_type()].append(context_mod)

        # Setup parser
        input_stream = FileStream(os.path.join(self._manifest_path))
        lexer = ManifestLexer(input_stream)
        tokens = CommonTokenStream(lexer)
        parser = ManifestParser(tokens)
        tree = parser.manifest()

        # Parse
        listener = ManifestListenerImpl(mod.log(), context_modules)
        walker = ParseTreeWalker()
        walker.walk(listener, tree)

        # Extract results
        self._projects = listener.projects
        self._project_sets = listener.project_sets

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

        return self._filtered(project_set, properties)

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
            self._mod.log().trace('found:', project)
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

        return self._filtered(project, properties)

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

    def _filtered(self, obj, props):
        if props is None:
            return obj
        else:
            return {
                prop: obj[prop]
                for prop in props
                if prop in obj
            }
