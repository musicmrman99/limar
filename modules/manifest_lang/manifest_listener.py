from modules.manifest_lang.build.ManifestListener import ManifestListener

# Types
from modules.manifest_lang.build.ManifestParser import ManifestParser
from core.modules.log import Log

class Tags:
    def __init__(self, add_callback=None, remove_callback=None):
        self._tags = {}
        self._add_callback = add_callback
        self._remove_callback = remove_callback

    def add(self, **kwargs):
        for name, value in kwargs.items():
            self._tags[name] = value
            if self._add_callback is not None:
                self._add_callback(kwargs)

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

    def __init__(self,
            logger: Log,
            context_modules: 'dict[str, list]' = None
    ):
        """
        context_modules must be a dictionary of the following format:
            {'context-type-name': [context_module, ...], ...}
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
        self._tag_operand_stack = []

    def enterManifest(self, ctx: ManifestParser.ManifestContext):
        # Call - 'on_enter_manifest' on all context modules
        self._run_context_lifecycle_point('on_enter_manifest', [])

    def exitManifest(self, ctx: ManifestParser.ManifestContext):
        # Call - 'on_exit_manifest' on all context modules
        self._run_context_lifecycle_point('on_exit_manifest',
            [self.items, self.item_sets]
        )

        # Finalise - tag set
        for item in self.items.values():
            item['tags'] = item['tags'].raw()

    def enterContext(self, ctx: ManifestParser.ContextContext):
        # Extract
        context_type = ctx.typeName.text
        context_opts = {
            # Value is mandatory
            opt.kvPair().name.text: (
                opt.kvPair().value.getText()
                if opt.kvPair().value is not None
                else None
            )
            for opt in ctx.contextOpt()
        }

        # Validate
        if context_type not in self._context_modules.keys():
            self._logger.warning(
                f"Unsupported context type '{context_type}' found."
                " Ignoring context."
            )
            # Used to represent an unrecognised context (not an error for
            # forwards compatibility and to support dynamic modules)
            self._contexts.append(NotImplementedError)
            return

        # Transform
        context = {
            'type': context_type,
            'opts': context_opts,
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

    def exitContext(self, ctx: ManifestParser.ContextContext):
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

    def _on_add_item_tags(self, item_ref, tags):
        for tag_name in tags.keys():
            if tag_name not in self.item_sets.keys():
                self.item_sets[tag_name] = {}
            self.item_sets[tag_name][item_ref] = self.items[item_ref]

    def _on_remove_item_tags(self, item_ref, names):
        for tag_name in names:
            if item_ref in self.item_sets[tag_name].keys():
                del self.item_sets[tag_name][item_ref]
            if len(self.item_sets[tag_name]) == 0:
                del self.item_sets[tag_name]

    def enterItem(self, ctx: ManifestParser.ItemContext):
        # Extract
        item_ref = ctx.ref().getText()
        tags = {
            tag.kvPair().name.text: (
                tag.kvPair().value.getText()
                if tag.kvPair().value is not None
                else None
            )
            for tag in ctx.tag()
        }

        # Store
          # Add to main item set
        self.items[item_ref] = {
            'ref': item_ref,
            'tags': Tags(
                # If any context module updates this module's tags, also update
                # all relevant indexes.
                lambda tags: self._on_add_item_tags(item_ref, tags),
                lambda tags: self._on_remove_item_tags(item_ref, tags)
            )
        }

          # Add all declared tags
        self.items[item_ref]['tags'].add(**tags)

          # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['items'][item_ref] = self.items[item_ref]

        # Call - 'on_declare_item' on all context modules registered for all
        # active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_item',
                [context, self.items[item_ref]],
                context['type']
            )

    def enterSetItemSet(self, ctx: ManifestParser.SetItemSetContext):
        # Extract
        item_set_name = ctx.ref().getText()

        # Store
        item_set = {} # In case the item set isn't defined
        if item_set_name in self.item_sets:
            item_set = self.item_sets[item_set_name]
        self._tag_operand_stack.append(item_set)

    # TODO: For now, a tag (with a value) appearning in a set is treated the
    #       same as a ref (ie. without a value).
    def enterSetTag(self, ctx: ManifestParser.SetTagContext):
        # Extract
        item_set_name = ctx.tag().getText()

        # Store
        item_set = {} # In case the tag isn't defined
        if item_set_name in self.item_sets:
            item_set = self.item_sets[item_set_name]
        self._tag_operand_stack.append(item_set)

    def exitSetOp(self, ctx: ManifestParser.SetOpContext):
        # Extract
        operator = ctx.setItemOperator().SET_ITEM_OPERATOR().getText()
        right_item_set = self._tag_operand_stack.pop()
        left_item_set = self._tag_operand_stack.pop()

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
        self._tag_operand_stack.append(result)

    def exitItemSet(self, ctx: ManifestParser.ItemSetContext):
        # Extract
        item_set_ref = ctx.ref().getText()

        # Store
          # Add to main item sets
        self.item_sets[item_set_ref] = self._tag_operand_stack.pop()

          # Add to all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            context['item_sets'][item_set_ref] = (
                self.item_sets[item_set_ref]
            )

        # Call - 'on_declare_item_set' on all context modules registered for
        # all active contexts
        for context in self._contexts:
            if context is NotImplementedError:
                continue # Skip unrecognised contexts

            self._run_context_lifecycle_point('on_declare_item_set',
                [context, self.item_sets[item_set_ref]],
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
