from hashlib import md5
from operator import itemgetter
import re

from core.store import Store
from core.exceptions import VCSException

# Types
from core.modulemanager import ModuleManager
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace
from typing import Any, Callable

class Manifest():
    """
    MM module to parse all manifest files declared by added context modules and
    to provide information about the items they declare.

    ## Manifest Files

    Manifest files are made up of declarations, contexts, and comments. There
    are two types of declarations: items and item sets.

    Items declare a named thing to exist. Item declarations may include a list
    of tags (key-value pairs, where the value is optional, defaulting to True of
    omitted) in brackets after the name. Tags are separated by a comma, a
    newline, or both.

    Item sets declare a named set of things to exist. Item set declarations must
    include an expression stating what other item sets this item set includes.
    An implicit item set exists for each unique tag on any item, which includes
    all items with that tag. Item set expressions can include the names of these
    sets, as well as & (and/intersection) and | (or/union) operators between
    these names. Nested item set expressions with operators between them are
    also supported.

    ## Context Modules

    You can give an indexed list (ie. a dictionary) of 'context modules' when
    initialising this class. Context modules are used to extend the manifest
    format by defining custom contexts. Contexts may be implicit (ie. global),
    or may be explicitly given in the manifest. If given, contexts are declared
    with `@context-type`, may take options, and may be scoped to a set of
    declarations.

    The declarations a context applies to can be given by placing them within a
    pair of braces after the context type, called the 'context content'. Each
    declaration within the context content must be on a separate line. Nested
    contexts are supported, though how they behave depends on the context
    module.

    Context options are specified by placing key-value pairs (where the value is
    optional and defaults to 'True' if omitted) within a pair of brackets
    between the context type and the context content. Options are separated
    either by a comma, a newline, or both.

    Example of contexts:

        @context-type {
          # The 'type' tag is made up - tags are only useful if they're
          # interpreted by something, whether a context module, or whatever is
          # using the manifest.
          dir/project-a (project, git)
        }

        @context-type (someOption: /home/username/mystuff) {
          dir/project-b (project, git)
        }

        @context-type (
            optionA: /home/username/directory
            optionB: https://somegithost.com/username
        ) {
          dir/project-c (project, git)
        }

    ## Implementing a Context Module

    Each context module must be a Python class. The class must define one class
    methods:

    - `context_type()`
      - Return the context type that module is for as a string.

    It may define an additional class method:

    - `can_be_root()`
      - Return True if the context type supports being used as a root context,
        otherwise return False. Only one context module for a context type
        needs to return True for this for it to be applied. If this method
        is not defined for a context module, then it is equivalent to it
        returning False.

    It may define any of the following method-based hooks (at least one should
    be defined to make the context module do anything):

    - `on_enter_manifest()`
      - TODO

    - `on_enter_context(context)`
      - TODO

    - `on_declare_item(context, item)`
      - TODO

    - `on_declare_item_set(context, item_set)`
      - TODO

    - `on_exit_context(context, items, item_sets)`
      - TODO
        `items` and `item_sets` contain the items/item_sets that were declared
        in this context in a single manifest file.

    - `on_exit_manifest(items, item_sets)`
      - TODO
        `items` and `item_sets` contain all items/item_sets that were declared
        in a single manifest file.
    """

    # Lifecycle
    # --------------------

    def __init__(self, manifest_store: Store = None, cache: Store = None):
        self._manifest_store = manifest_store
        self._cache = cache

        self._ctx_mod_factories: dict[str, Callable[[], Any]] = {}
        self._manifest_names: list[str] = []

        self._projects: dict[str, dict[str, object]] = None
        self._project_sets: dict[str, dict[str, dict[str, object]]] = None

    def dependencies(self):
        return ['log']

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('ROOT')
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
        self._mod = mod # For methods that aren't directly given it

        if self._manifest_store is None:
            self._manifest_store = Store(env.VCS_MANIFEST_ROOT)

        if self._cache is None:
            self._cache = self._manifest_store

        self._default_project_set = env.VCS_MANIFEST_DEFAULT_PROJECT_SET

    def start(self, *_, **__):
        for manifest_name in self._manifest_names:
            self._load_manifest(manifest_name)

    def _load_manifest(self, name):
        try:
            manifest = self._manifest_store.get(name+'.manifest.txt')
        except KeyError:
            self._mod.log().trace(
                f"Manifest '{name}' not found. Skipping."
            )
            return

        # Determine cache filename for this version of the manifest file
        digest = md5(manifest.encode('utf-8')).hexdigest()
        cache_name = '.'.join([name, 'manifest', digest, 'pickle'])

        # Try cache
        try:
            self._cache.setattr(cache_name, 'type', 'pickle')
            projects, project_sets = itemgetter(
                'projects',
                'project_sets'
            )(self._cache.get(cache_name))

        except KeyError:
            # Import deps (these are slow to import, so only (re)parse the
            # manifest if needed)
            from antlr4 import InputStream, CommonTokenStream, ParseTreeWalker
            from modules.manifest_lang.build.ManifestLexer import ManifestLexer
            from modules.manifest_lang.build.ManifestParser import ManifestParser
            from modules.manifest_lang.manifest_listener import ManifestListenerImpl

            # Create context modules
            context_modules = {
                context_type: [
                    mod_factory()
                    for mod_factory in ctx_mod_factories
                ]
                for context_type, ctx_mod_factories in
                    self._ctx_mod_factories.items()
            }

            # Setup parser
            input_stream = InputStream(manifest)
            lexer = ManifestLexer(input_stream)
            tokens = CommonTokenStream(lexer)
            parser = ManifestParser(tokens)
            tree = parser.manifest()

            # Parse
            listener = ManifestListenerImpl(
                self._mod.log(),
                context_modules,
                [name]
            )
            walker = ParseTreeWalker()
            walker.walk(listener, tree)

            projects = listener.items
            project_sets = listener.item_sets
            self._mod.log().info(
                f"Loaded manifest '{name}' from '{self._manifest_store}'"
            )

            # Cache results
            self._cache.set(cache_name, {
                'projects': projects,
                'project_sets': project_sets
            })
            self._cache.flush()
            self._mod.log().trace(
                f"Cached result '{cache_name}' in '{self._cache}'"
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

    def add_context_modules(self, *modules):
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
                " inappropriate use of mod.manifest().add_context_modules() by"
                " the last ModuleManager module to be invoked (either directly"
                " or by another MM module)."
            )

        for module in modules:
            module_added = True
            if module.context_type() not in self._ctx_mod_factories:
                self._ctx_mod_factories[module.context_type()] = [module]

            elif module not in self._ctx_mod_factories[module.context_type()]:
                self._ctx_mod_factories[module.context_type()].append(module)

            else:
                module_added = False
            if (
                module_added and
                hasattr(module, 'can_be_root') and
                module.can_be_root()
            ):
                self._manifest_names.append(module.context_type())

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
