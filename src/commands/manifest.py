import os
import re

from antlr4 import FileStream, CommonTokenStream, ParseTreeWalker
from manifest.build.ManifestLexer import ManifestLexer
from manifest.build.ManifestParser import ManifestParser
from manifest.build.ManifestListener import ManifestListener

from exceptions import VCSException

from pprint import pprint

# Types
from commandset import CommandSet
from environment import Environment
from argparse import ArgumentParser, Namespace

class ManifestListenerImpl(ManifestListener):
    def __init__(self):
        # Outputs
        self.projects = {}
        self.project_sets = {}

        # Internal operations
        self._contexts = []
        self._tag_operand_stack = []

    def enterContext(self, ctx: ManifestParser.ContextContext):
        self._contexts.append({'type': ctx.typeName.text, 'opts': {}})
        for opt in ctx.contextOpts().contextOpt():
            self._contexts[-1]['opts'][opt.optName.text] = opt.optValue.getText()

    def exitContext(self, ctx: ManifestParser.ContextContext):
        self._contexts.pop()

    def enterProject(self, ctx: ManifestParser.ProjectContext):
        proj_ref = ctx.path().getText()
        proj_path = proj_ref
        try:
            context_local_path = next(
                context
                for context in reversed(self._contexts)
                if (
                    context['type'] == 'map-uris' and     # Has context
                    'local' in context['opts'].keys() and # Local is defined
                    context['opts']['local'][0] == '/'    # Local is absolute
                )
            )['opts']['local']

            proj_path = os.path.join(context_local_path, proj_path)

        except (KeyError, StopIteration):
            if proj_path[0] != '/':
                raise VCSException(
                    f"Project '{proj_path}' is not an absolute path and is"
                    " not contained in an @map-uris context with an absolute"
                    " local path"
                )

        self.projects[proj_path] = {
            'ref': proj_ref,
            'path': proj_path,
            'tags': set()
        }
        if ctx.tagList() is not None:
            self.projects[proj_path]['tags'] = set(
                tag.getText()
                for tag in ctx.tagList().tag()
            )

        for tag in self.projects[proj_path]['tags']:
            if tag not in self.project_sets.keys():
                self.project_sets[tag] = set()
            self.project_sets[tag].add(proj_path)

    def enterTagBase(self, ctx: ManifestParser.TagBaseContext):
        project_set_name = ctx.tag().getText()
        tag_set = set()
        if project_set_name in self.project_sets:
            tag_set = self.project_sets[project_set_name]
        self._tag_operand_stack.append(tag_set)

    def exitTagOp(self, ctx: ManifestParser.TagOpContext):
        right_operand = self._tag_operand_stack.pop()
        left_operand = self._tag_operand_stack.pop()
        if ctx.op.text == '&':
            result = left_operand.intersection(right_operand)
        elif ctx.op.text == '|':
            result = left_operand.union(right_operand)
        self._tag_operand_stack.append(result)

    def exitProjectSet(self, ctx: ManifestParser.ProjectSetContext):
        self.project_sets[ctx.path().getText()] = self._tag_operand_stack.pop()

class Manifest():
    @staticmethod
    def setup_args(parser: ArgumentParser, **_):
        manifest_subparsers = parser.add_subparsers(dest="manifest_command")

        # Resolve Subcommand
        resolve_parser = manifest_subparsers.add_parser('resolve')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='The regex pattern to resolve to a project reference')

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
                    @map-uris context that is closest to the resolved project in
                    the manifest that includes this URI type),
                or 'current' (relative to the current directory)
            """)

        resolve_parser.add_argument('--project-set',
            metavar='PROJECT_SET_PATTERN',
            help="""
            A pattern that matches the project set to use to resolve the project
            """)

    def __init__(self,
            cmd: CommandSet = None,
            env: Environment = None,
            args: Namespace = None
    ):
        self._cmd = cmd
        self._default_project_set = env.get('manifest.default_project_set')

        # Load the manifest
        input_stream = FileStream(
            os.path.join(env.get('manifest.root'), 'manifest.txt')
        )
        lexer = ManifestLexer(input_stream)
        tokens = CommonTokenStream(lexer)
        parser = ManifestParser(tokens)
        tree = parser.manifest()

        listener = ManifestListenerImpl()
        walker = ParseTreeWalker()
        walker.walk(listener, tree)

        self.projects = listener.projects
        self.project_sets = listener.project_sets

    def __call__(self, args):
        output = ''

        if args.manifest_command == 'resolve':
            output = self.resolve(
                args.pattern,
                project_set_pattern=args.project_set,
                location=args.location,
                relative_to=args.relative_to
            )
            self._cmd.log().info('resolved project to:', output)

        return output

    def resolve(self,
            pattern,
            *_,
            project_set_pattern=None,
            location=None,
            relative_to=None
    ):
        if location is None:
            location = 'local'
        if relative_to is None:
            relative_to = 'root'

        self._cmd.log().trace(
            "manifest.resolve("
                f"'{pattern}',"
                f" project_set_pattern={project_set_pattern},"
                f" location={location},"
                f" relative_to={relative_to}"
            ")"
        )

        if project_set_pattern is None:
            if self._default_project_set is None:
                project_set = set(self.projects.keys())
            else:
                project_set = self.project_sets[self._default_project_set]
        else:
            project_set_regex = re.compile(project_set_pattern)
            try:
                project_set = next(
                    self.project_sets[project_set_name]
                    for project_set_name in self.project_sets.keys()
                    if project_set_regex.search(project_set_name)
                )
            except (KeyError, StopIteration):
                raise VCSException(
                    f"Project set not found from pattern '{project_set_pattern}'"
                )

        project_regex = re.compile(pattern)
        try:
            project = next(
                project
                for project in project_set
                if project_regex.search(project)
            )
            self._cmd.log().trace('found:', project)
        except StopIteration:
            raise VCSException(
                f"Project not found from pattern '{pattern}'"
            )

        # TODO:
        # - Check for existance of project, not just of manifest entry
        # - Map to relative if relative_to is 'manifest' or 'relative'
        #
        # Ideas:
        # - Verify (-v, --verify) makes resolve verify that the specified path exists (mutex with -c)
        # - Candidate (-c, --candidate) makes resolve come up with a proposed path where the project/list could be stored in future (mutex with -v)

        return project
