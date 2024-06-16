from argparse import Namespace
import textwrap

from modules.manifest import Manifest
from modules.manifest_lang.build.ManifestListener import ManifestListener

# Types
from modules.manifest_lang.build.ManifestParser import ManifestParser
from core.modules.log import LogModule

class ManifestListenerImpl(ManifestListener):
    """
    An ANTLR4 Listener to parse the manifest file.

    For details of the expected structure of a manifest file, see the Manifest
    MM module's docstring.
    """

    def __init__(self,
            logger: LogModule,
            manifest: Manifest
    ):
        self._logger = logger
        self._manifest = manifest

    # Listen Points
    # --------------------------------------------------

    def enterManifest(self, ctx: ManifestParser.ManifestContext):
        self._manifest.enter()

    def exitManifest(self, ctx: ManifestParser.ManifestContext):
        self._manifest.exit()

    def enterExplScopedContext(self, ctx: ManifestParser.ExplScopedContextContext):
        self._enter_context(ctx.contextHeader())

    def enterImplScopedContext(self, ctx: ManifestParser.ImplScopedContextContext):
        self._enter_context(ctx.contextHeader())

    # Util
    def _enter_context(self, context_header: ManifestParser.ContextHeaderContext):
        context_type = context_header.typeName.text # type: ignore (dynamic)
        context_opts = {}
        for opt in context_header.contextOpt():
            kvpair = self._get_kvpair_content(opt.kvPair())
            context_opts[kvpair.name] = kvpair.value

        self._manifest.enter_context(context_type, context_opts)

    def exitExplScopedContext(self, ctx: ManifestParser.ExplScopedContextContext):
        self._manifest.exit_context()

    def exitImplScopedContext(self, ctx: ManifestParser.ImplScopedContextContext):
        self._manifest.exit_context()

    def enterTagDecl(self, ctx: ManifestParser.ItemContext):
        ref = self._get_ref_content(ctx.ref())
        tags = {}
        for tag in ctx.tag():
            kvpair = self._get_kvpair_content(tag.kvPair())
            tags[kvpair.name] = kvpair.value

        self._manifest.declare_tag(ref, tags)

    def enterItem(self, ctx: ManifestParser.ItemContext):
        ref = self._get_ref_content(ctx.ref())
        tags = {}
        for tag in ctx.tag():
            kvpair = self._get_kvpair_content(tag.kvPair())
            tags[kvpair.name] = kvpair.value

        self._manifest.declare_item(ref, tags)

    def enterItemSet(self, ctx: ManifestParser.ItemSetContext):
        # Stacks item set specs on the way in, then structures them into a
        # b-tree on the way out based on operators.
        self._set_stack = []

    def enterItemSetSpec_itemSet(self,
            ctx: ManifestParser.ItemSetSpec_itemSetContext
    ):
        item_set_ref = self._get_ref_content(ctx.ref())
        self._set_stack.append(item_set_ref)

    # TODO: For now, a tag (with a value) appearning in a set is treated the
    #       same as a ref (ie. without a value).
    def enterItemSetSpec_tag(self, ctx: ManifestParser.ItemSetSpec_tagContext):
        tag = self._get_kvpair_content(ctx.tag().kvPair())
        self._set_stack.append((tag.name, tag.value))

    def exitItemSetSpec_op(self, ctx: ManifestParser.ItemSetSpec_opContext):
        operator = ctx.setItemOperator().SET_ITEM_OPERATOR().getText()
        self._set_stack = [
            *self._set_stack[:-2],
            {
                'operator': operator,
                'left': self._set_stack[-2],
                'right': self._set_stack[-1]
            }
        ]

    def exitItemSet(self, ctx: ManifestParser.ItemSetContext):
        item_set_ref = self._get_ref_content(ctx.ref())
        self._manifest.declare_item_set(
            item_set_ref,
            self._set_stack[0] if len(self._set_stack) > 0 else None
        )

    # Util
    def _get_ref_content(self, ref):
        if ref.literalBlock() is not None:
            return self._get_literal_block_content(ref.literalBlock())
        else:
            return ref.getText()

    def _get_kvpair_content(self, kvpair):
        if kvpair.name().literalBlock() is not None:
            name = self._get_literal_block_content(kvpair.name().literalBlock())
        else:
            name = kvpair.name().getText()

        if kvpair.value() is None:
            value = None
        elif kvpair.value().literalBlock() is not None:
            value = self._get_literal_block_content(
                kvpair.value().literalBlock()
            )
        else:
            value = kvpair.value().getText()

        return Namespace(name=name, value=value)

    def _get_literal_block_content(self, block):
        return textwrap.dedent(block.literal().getText()).strip('\n')
