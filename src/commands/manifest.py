import os

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
        pass

    def __init__(self,
            cmd: CommandSet = None,
            env: Environment = None,
            args: Namespace = None
    ):
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
        pass
