from modules.manifest import ManifestBuilder
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
            manifestBuilder: ManifestBuilder
    ):
        self._logger = logger
        self._manifest_builder = manifestBuilder

    # Listen Points
    # --------------------------------------------------

    def enterManifest(self, ctx: ManifestParser.ManifestContext):
        self._manifest_builder.enter()

    def exitManifest(self, ctx: ManifestParser.ManifestContext):
        self._manifest_builder.exit()

    def enterExplScopedContext(self, ctx: ManifestParser.ExplScopedContextContext):
        self._enter_context(ctx.contextHeader())

    def enterImplScopedContext(self, ctx: ManifestParser.ImplScopedContextContext):
        self._enter_context(ctx.contextHeader())

    # Util
    def _enter_context(self, context_header: ManifestParser.ContextHeaderContext):
        context_type = context_header.typeName.text
        context_opts = {
            opt.kvPair().name.text: (
                opt.kvPair().value.getText()
                if opt.kvPair().value is not None
                else None
            )
            for opt in context_header.contextOpt()
        }

        self._manifest_builder.enter_context(context_type, context_opts)

    def exitContext(self, ctx: ManifestParser.ContextContext):
        self._manifest_builder.exit_context()

    def enterItem(self, ctx: ManifestParser.ItemContext):
        ref = self._get_ref_content(ctx.ref())
        tags = {
            tag.kvPair().name.text: (
                tag.kvPair().value.getText()
                if tag.kvPair().value is not None
                else None
            )
            for tag in ctx.tag()
        }

        self._manifest_builder.declare_item(ref, tags)

    def enterItemSet(self, ctx: ManifestParser.ItemSetContext):
        # Stacks item set specs on the way in, then structures them into a
        # b-tree on the way out based on operators.
        self._set_stack = []

    def enterSetItemSet(self, ctx: ManifestParser.SetItemSetContext):
        item_set_ref = self._get_ref_content(ctx.ref())
        self._set_stack.append(item_set_ref)

    # TODO: For now, a tag (with a value) appearning in a set is treated the
    #       same as a ref (ie. without a value).
    def enterSetTag(self, ctx: ManifestParser.SetTagContext):
        item_set_ref = ctx.tag().kvPair().name.text
        self._set_stack.append(item_set_ref)

    def exitSetOp(self, ctx: ManifestParser.SetOpContext):
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
        self._manifest_builder.declare_item_set(
            item_set_ref,
            self._set_stack[0] if len(self._set_stack) > 0 else None
        )

    # Util
    def _get_ref_content(self, ref):
        if ref.refLiteral() is not None:
            return ref.refLiteral().getText()
        else:
            return ref.refNormal().getText()
