from core.exceptions import VCSException
from modules.manifest_lang.build.ManifestListener import ManifestListener

# Types
from modules.manifest_lang.build.ManifestParser import ManifestParser
from core.modules.log import Log

class Tags:
    def __init__(self, add_callback=None, remove_callback=None):
        self._tags = {}
        self._add_callback = add_callback
        self._remove_callback = remove_callback

    def add(self, *names, **tags):
        for name, value in tags.items():
            self._tags[name] = value
            if self._add_callback is not None:
                self._add_callback(tags)

        if len(names) > 0:
            self.add(**{name: None for name in names})

    def remove(self, *names):
        for name in names:
            del self._tags[name]
            if self._remove_callback is not None:
                self._remove_callback(names)

    def raw(self):
        return self._tags

class ManifestListenerImpl(ManifestListener):
    """
    An ANTLR4 Listener to parse the manifest file.

    For details of the expected structure of a manifest file, see the Manifest
    MM module's docstring.
    """

    def __init__(self,
            logger: Log,
            context_modules: dict[str, list] = None,
            default_contexts: list[str] = None
    ):
        """
        `context_modules` must be a dictionary of the following format:
            {'context-type-name': [context_module, ...], ...}

        `default_contexts` is a list of context type names to enter immediately
        after entering the manifest. Enter the contexts in the order the names
        are given, passing no options to each. Raise a VCSException if any
        module names given in `default_contexts` are not defined in
        `context_modules`.
        """

        # Outputs
        self.items = {}
        self.item_sets = {}

        # Internal operations
        self._logger = logger

        self._context_modules = context_modules
        if self._context_modules is None:
            self._context_modules = {}

        self._contexts = []

        self._default_context_names = (
            default_contexts
            if default_contexts is not None
            else []
        )
        for name in self._default_context_names:
            if name not in self._context_modules:
                raise VCSException('Default context')

    # Listen Points
    # --------------------------------------------------

    def enterManifest(self, ctx: ManifestParser.ManifestContext):
        self._enter_manifest()

    def exitManifest(self, ctx: ManifestParser.ManifestContext):
        self._exit_manifest()

    def enterContext(self, ctx: ManifestParser.ContextContext):
        context_type = ctx.typeName.text
        context_opts = {
            opt.kvPair().name.text: (
                opt.kvPair().value.getText()
                if opt.kvPair().value is not None
                else None
            )
            for opt in ctx.contextOpt()
        }

        self._enter_context(context_type, context_opts)

    def exitContext(self, ctx: ManifestParser.ContextContext):
        self._exit_context()

    def enterItem(self, ctx: ManifestParser.ItemContext):
        ref = ctx.ref().getText()
        tags = {
            tag.kvPair().name.text: (
                tag.kvPair().value.getText()
                if tag.kvPair().value is not None
                else None
            )
            for tag in ctx.tag()
        }

        self._declare_item(ref, tags)

    def enterItemSet(self, ctx: ManifestParser.ItemSetContext):
        self._item_set_operand_stack = []

    def enterSetItemSet(self, ctx: ManifestParser.SetItemSetContext):
        # Extract
        item_set_name = ctx.ref().getText()

        # Store (text-only - not a logical operation)
        item_set = (
            self.item_sets[item_set_name]
            if item_set_name in self.item_sets
            else {} # In case the item set isn't defined
        )
        self._item_set_operand_stack.append(item_set)

    # TODO: For now, a tag (with a value) appearning in a set is treated the
    #       same as a ref (ie. without a value).
    def enterSetTag(self, ctx: ManifestParser.SetTagContext):
        # Extract
        item_set_name = ctx.tag().getText()

        # Store (text-only - not a logical operation)
        item_set = (
            self.item_sets[item_set_name]
            if item_set_name in self.item_sets
            else {} # In case the item set isn't defined
        )
        self._item_set_operand_stack.append(item_set)

    def exitSetOp(self, ctx: ManifestParser.SetOpContext):
        # Extract
        operator = ctx.setItemOperator().SET_ITEM_OPERATOR().getText()
        right_item_set = self._item_set_operand_stack.pop()
        left_item_set = self._item_set_operand_stack.pop()

        # Store
        if operator == '&':
            result = {
                item_set_name: left_item_set[item_set_name]
                for item_set_name in left_item_set.keys() & right_item_set.keys()
            }
        elif operator == '|':
            result = {
                item_set_name: (
                    left_item_set[item_set_name]
                    if item_set_name in left_item_set
                    else right_item_set[item_set_name]
                )
                for item_set_name in left_item_set.keys() | right_item_set.keys()
            }
        self._item_set_operand_stack.append(result)

    def exitItemSet(self, ctx: ManifestParser.ItemSetContext):
        item_set_ref = ctx.ref().getText()
        self._declare_item_set(item_set_ref, self._item_set_operand_stack.pop())

    # Operations
    # --------------------------------------------------

    def _enter_manifest(self):
        # Call - 'on_enter_manifest' on all context modules
        self._run_context_lifecycle_point('on_enter_manifest', [])

        for context_name in self._default_context_names:
            self._enter_context(context_name)

    def _exit_manifest(self):
        for context_name in reversed(self._default_context_names):
            self._exit_context(context_name)

        # Call - 'on_exit_manifest' on all context modules
        self._run_context_lifecycle_point('on_exit_manifest',
            [self.items, self.item_sets]
        )

        # Finalise - tag set
        for item in self.items.values():
            item['tags'] = item['tags'].raw()

    def _enter_context(self, type, opts = None):
        # Validate
        if type not in self._context_modules.keys():
            self._logger.warning(
                f"Unsupported context type '{type}' found."
                " Ignoring context."
            )
            # Used to represent an unrecognised context (not an error for
            # forwards compatibility and to support dynamic modules)
            self._contexts.append(NotImplementedError)
            return

        # Structure
        context = {
            'type': type,
            'opts': opts if opts is not None else {},
            'items': {},
            'item_sets': {}
        }

        # Store
        self._contexts.append(context)

        # Call - 'on_enter_context' on all context modules registered for this
        # context
        self._run_context_lifecycle_point('on_enter_context',
            [context],
            context['type']
        )

    def _exit_context(self):
        # Discard
        old_context = self._contexts.pop()

        # Validate
        if old_context is NotImplementedError:
            return # Ignore unrecognised contexts

        # Call - 'on_exit_context' on all context modules registered for this
        # context
        self._run_context_lifecycle_point('on_exit_context',
            [
                old_context,
                old_context['items'],
                old_context['item_sets']
            ],
            old_context['type']
        )

    # Util for _declare_item()
    def _on_add_item_tags(self, item_ref, tags):
        for tag_name in tags.keys():
            if tag_name not in self.item_sets.keys():
                self.item_sets[tag_name] = {}
            self.item_sets[tag_name][item_ref] = self.items[item_ref]

    # Util for _declare_item()
    def _on_remove_item_tags(self, item_ref, names):
        for tag_name in names:
            if item_ref in self.item_sets[tag_name].keys():
                del self.item_sets[tag_name][item_ref]
            if len(self.item_sets[tag_name]) == 0:
                del self.item_sets[tag_name]

    def _declare_item(self, ref, tags = None):
        # Store
          # Add to main item set
        self.items[ref] = {
            'ref': ref,
            'tags': Tags(
                # If any context module updates this item's tags, also update
                # all relevant indexes.
                lambda tags: self._on_add_item_tags(ref, tags),
                lambda tags: self._on_remove_item_tags(ref, tags)
            )
        }

          # Add all declared tags
        if tags is not None:
            self.items[ref]['tags'].add(**tags)

          # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['items'][ref] = self.items[ref]

        # Call - 'on_declare_item' on all context modules registered for all
        # active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_item',
                [context, self.items[ref]],
                context['type']
            )

    def _declare_item_set(self, ref, items):
        # Store
          # Add to main item sets
        self.item_sets[ref] = items

          # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['item_sets'][ref] = (
                self.item_sets[ref]
            )

        # Call - 'on_declare_item_set' on all context modules registered for
        # all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_item_set',
                [context, self.item_sets[ref]],
                context['type']
            )

    # Utils
    # --------------------------------------------------

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
