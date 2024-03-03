import os
import re

from antlr4 import FileStream, CommonTokenStream, ParseTreeWalker
from manifest.build.ManifestLexer import ManifestLexer
from manifest.build.ManifestParser import ManifestParser
from manifest.build.ManifestListener import ManifestListener

from exceptions import VCSException

# Types
from commandset import CommandSet
from environment import Environment
from argparse import ArgumentParser, Namespace
from commands.log import Log

class ManifestListenerImpl(ManifestListener):
    def __init__(self,
            logger: Log,
            context_hooks: 'dict[str, dict[str, list[function]]]' = None
    ):
        """
        Initialises the manifest listener.

        context_hooks must be a dictionary of the following format:

            {'context-type-name': {'hook_name': [hook(), ...]}, ...}

        The following hook_names must be defined for every context type given:

        - on_enter_manifest
          - Hook Spec: hook()

        - on_enter_context
          - Hook Spec: hook(context)

        - on_declare_project
          - Hook Spec: hook(context, project)

        - on_declare_project_set
          - Hook Spec: hook(context, project_set)

        - on_exit_context
          - Hook Spec: hook(context, projects, project_sets)
          - Note that projects and project_sets only contain those that were
            declared in this context.

        - on_exit_manifest
          - Hook Spec: hook(projects, project_sets)
        """

        # Outputs
        self.projects = {}
        self.project_sets = {}

        # Internal operations
        self._logger = logger

        self._context_hooks = context_hooks
        if self._context_hooks is None:
            self._context_hooks = {}

        self._contexts = []
        self._tag_operand_stack = []

    def enterManifest(self, ctx: ManifestParser.ManifestContext):
        # Call all registered 'on_enter_manifest' hooks
        for context_hooks in self._context_hooks.values():
            for hook in context_hooks['on_enter_manifest']:
                hook()

    def exitManifest(self, ctx: ManifestParser.ManifestContext):
        # Call all registered 'on_enter_manifest' hooks
        for context_hooks in self._context_hooks.values():
            for hook in context_hooks['on_exit_manifest']:
                hook(self.projects, self.project_sets)

    def enterContext(self, ctx: ManifestParser.ContextContext):
        context_type = ctx.typeName.text
        if context_type not in self._context_hooks.keys():
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

        # Call all 'on_enter_context' hooks registered for the context
        context_hooks = self._context_hooks[context['type']]
        for hook in context_hooks['on_enter_context']:
            hook(context)

    def exitContext(self, ctx: ManifestParser.ContextContext):
        old_context = self._contexts.pop()
        if old_context is NotImplementedError:
            return # Ignore unrecognised contexts

        # Call all 'on_exit_context' hooks registered for the context
        context_hooks = self._context_hooks[old_context['type']]
        for hook in context_hooks['on_exit_context']:
            hook(
                old_context,
                old_context['projects'],
                old_context['project_sets']
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

        # Call all registered 'on_declare_project' hooks for all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context_hooks = self._context_hooks[context['type']]
            for hook in context_hooks['on_declare_project']:
                hook(context, self.projects[proj_ref])

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

        # Call all registered 'on_declare_project_set' hooks for all active
        # contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context_hooks = self._context_hooks[context['type']]
            for hook in context_hooks['on_declare_project_set']:
                hook(context, self.project_sets[proj_set_ref])

class Manifest():
    @staticmethod
    def setup_args(parser: ArgumentParser, **_):
        manifest_subparsers = parser.add_subparsers(dest="manifest_command")

        # Resolve Subcommand
        resolve_parser = manifest_subparsers.add_parser('project')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to a project reference')

        # Options
        resolve_parser.add_argument('-l', '--location',
            choices=['local', 'remote'],
            help='Specify the location to reosolve the project pattern to')

        resolve_parser.add_argument('-r', '--relative-to',
            choices=['root', 'manifest', 'current'],
            help="""
            Specify the location that the output reference should be relative
            to, or one of:
                'root' (resolve to an aboslute URI),
                'manifest' (resolve to a URI relative to the relevant URI in the
                    @uris context that is closest to the resolved project in
                    the manifest that includes this URI type),
                or 'current' (relative to the current directory)
            """)

        resolve_parser.add_argument('--project-set',
            metavar='PROJECT_SET_PATTERN',
            help="""
            A pattern that matches the project set to use to resolve the project
            """)

        # Resolve Subcommand
        resolve_parser = manifest_subparsers.add_parser('project-set')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to a project set')

    def __init__(self, *,
            cmd: CommandSet,
            env: Environment,
            args: Namespace = None
    ):
        self._logger: Log = cmd.log()
        self._manifest_root = env.get('manifest.root')
        self._default_project_set = env.get('manifest.default_project_set')

        self._supported_contexts: dict[str, dict[str, list[function]]] = {}
        self._projects: dict[str, dict[str, object]] = None
        self._project_sets: dict[str, dict[str, dict[str, object]]] = None

    def register_context_hooks(
            self,
            typeName: str,
            **hooks
    ):
        # It is only useful to register context hooks *before* the manifest is
        # parsed. If it's already been parsed, then registration will have no
        # effect. As such, fail loudly to tell command developers that they've
        # done something wrong.
        if self._projects is not None:
            raise VCSException(
                f"Attempted registration of context type '{typeName}' after"
                " manifest has been parsed. This was probably caused by"
                " inappropriate use of"
                " commands.Manifest.register_context_option() by the last"
                " command to be invoked (possibly internally)."
            )

        sup_ctx = self._supported_contexts
        if typeName not in sup_ctx:
            sup_ctx[typeName] = {
                'on_enter_manifest': [],
                'on_enter_context': [],
                'on_declare_project': [],
                'on_declare_project_set': [],
                'on_exit_context': [],
                'on_exit_manifest': []
            }

        sup_ctx[typeName] = {
            key: [
                *sup_ctx[typeName][key],
                *([hooks[key]] if key in hooks.keys() else [])
            ]
            for key in sup_ctx[typeName].keys()
        }

    def _load_manifest(self):
        self._logger.trace(f"manifest._load_manifest()")

        input_stream = FileStream(
            os.path.join(self._manifest_root, 'manifest.txt')
        )
        lexer = ManifestLexer(input_stream)
        tokens = CommonTokenStream(lexer)
        parser = ManifestParser(tokens)
        tree = parser.manifest()

        listener = ManifestListenerImpl(self._logger, self._supported_contexts)
        walker = ParseTreeWalker()
        walker.walk(listener, tree)

        self._projects = listener.projects
        self._project_sets = listener.project_sets

    def __call__(self, args):
        self._logger.trace(f"manifest(args={args})")

        output = ''

        if args.manifest_command == 'project':
            output = self.get_project(
                args.pattern,
                project_set_pattern=args.project_set,
                location=args.location,
                relative_to=args.relative_to
            )
            self._logger.info('resolved project to:', output)

        if args.manifest_command == 'project-set':
            output = self.get_project_set(args.pattern)
            self._logger.info('resolved project set to:', output)

        return output

    def get_project_set(self, pattern: str = None):
        self._logger.trace(
            "manifest.get_project_set("
                +(f"{pattern}" if pattern is None else f"'{pattern}'")+
            ")"
        )

        if self._projects is None:
            self._load_manifest()

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

        return project_set

    def get_project(self,
            pattern: str,
            *_,
            project_set_pattern=None,
            location=None,
            relative_to=None
    ):
        if location is None:
            location = 'local'
        if relative_to is None:
            relative_to = 'root'

        self._logger.trace(
            "manifest.get_project("
                +(pattern if pattern is None else f"'{pattern}'")+","
                f" project_set_pattern={project_set_pattern},"
                f" location={location},"
                f" relative_to={relative_to}"
            ")"
        )

        if self._projects is None:
            self._load_manifest()

        project_set = self.get_project_set(project_set_pattern)

        project_regex = re.compile(pattern)
        try:
            project = next(
                project
                for project in project_set.values()
                if project_regex.search(project['ref'])
            )
            self._logger.trace('found:', project)
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

        return project
