from hashlib import md5
import re

from core.store import Store
from core.exceptions import VCSException

# Types
from core.modules.log import LogModule
from core.modulemanager import ModuleManager
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace
from typing import Any, Callable

class ManifestBuilder:
    def __init__(self,
            logger: LogModule,
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

        self._context_modules = context_modules
        self._default_contexts = default_contexts

        self._items = {}
        self._item_sets = {}

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

    def enter(self):
        # Call - 'on_enter_manifest' on all registered context modules
        self._run_manifest_lifecycle_point('on_enter_manifest', [])

        # Enter each default context
        for context_name in self._default_context_names:
            self.enter_context(context_name)

    def exit(self):
        # Exit each default context
        for _ in range(len(self._default_context_names)):
            self.exit_context()

        # Call - 'on_exit_manifest' on all registered context modules
        self._run_manifest_lifecycle_point('on_exit_manifest',
            [self._items, self._item_sets]
        )

        # Finalise - tag set
        for item in self._items.values():
            item['tags'] = item['tags'].raw()

    def enter_context(self, type, opts = None):
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

        # Call - 'on_enter_context' on all context modules registered with the
        # same context type as the context being entered (if any)
        self._run_context_lifecycle_point('on_enter_context',
            [context],
            context['type']
        )

    def exit_context(self):
        # Discard
        old_context = self._contexts.pop()

        # Validate
        if old_context is NotImplementedError:
            return # Ignore unrecognised contexts

        # Call - 'on_exit_context' on all context modules registered with the
        # same context type as the context being exited (if any)
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
            if tag_name not in self._item_sets.keys():
                self._item_sets[tag_name] = {}
            self._item_sets[tag_name][item_ref] = self._items[item_ref]

    # Util for _declare_item()
    def _on_remove_item_tags(self, item_ref, names):
        for tag_name in names:
            if item_ref in self._item_sets[tag_name].keys():
                del self._item_sets[tag_name][item_ref]
            if len(self._item_sets[tag_name]) == 0:
                del self._item_sets[tag_name]

    def declare_item(self, ref, tags = None):
        # Validate
        if ref in self._items:
            raise VCSException(f"Manifest item already exists with ref '{ref}'")

        # Store
        item = {
            'ref': ref,
            'tags': ManifestItemTags(
                # If any context module updates this item's tags, also update
                # all relevant indexes.
                lambda tags: self._on_add_item_tags(ref, tags),
                lambda tags: self._on_remove_item_tags(ref, tags)
            )
        }

          # Add to main item set
        self._items[ref] = item

          # Add all declared tags
        if tags is not None:
            item['tags'].add(**tags)

          # Add to all active contexts
        for context in self._contexts:
            if context is not NotImplementedError:
                context['items'][ref] = item

        # Call - 'on_declare_item' on all context modules registered for each
        # unique context type of all active contexts, passing all active
        # contexts of the same type as the context module being called.
        self._run_decl_lifecycle_point('on_declare_item',
            [item]
        )

    # Util for _declare_item_set()
    def _get_item_set(self, ref):
        return (
            self._item_sets[ref]
            if ref in self._item_sets
            else {} # In case the item set isn't defined
        )

    # Util for _declare_item_set()
    def _compute_set(self, ops_btree):
        if ops_btree is None:
            return {} # In case of an empty set

        if type(ops_btree) is str:
            return self._get_item_set(ops_btree)

        left_item_set = self._compute_set(ops_btree['left'])
        right_item_set = self._compute_set(ops_btree['right'])

        if ops_btree['operator'] == '&':
            return {
                item_set_name: left_item_set[item_set_name]
                for item_set_name in left_item_set.keys() & right_item_set.keys()
            }

        elif ops_btree['operator'] == '|':
            return {
                item_set_name: (
                    left_item_set[item_set_name]
                    if item_set_name in left_item_set
                    else right_item_set[item_set_name]
                )
                for item_set_name in left_item_set.keys() | right_item_set.keys()
            }

        else:
            raise VCSException(
                f"Unsupported set operator '{ops_btree['operator']}' when"
                " computing item set"
            )

    def declare_item_set(self, ref, ops_btree):
        # Compute
        item_set = self._compute_set(ops_btree)

        # Store
          # Add to main item sets
        self._item_sets[ref] = item_set

          # Add to all active contexts
        for context in self._contexts:
            if context is not NotImplementedError:
                context['item_sets'][ref] = item_set

        # Call - 'on_declare_item_set' on all context modules registered for
        # each unique context type of all active contexts, passing all active
        # contexts of the same type as the context module being called.
        self._run_decl_lifecycle_point('on_declare_item_set',
            [item_set]
        )

    def finalise(self):
        return Manifest(self._items, self._item_sets)

    # Utils

    def _run_manifest_lifecycle_point(self, name, args):
        mods = [
            mod
            for mod_set in self._context_modules.values()
            for mod in mod_set
        ]
        for module in mods:
            if hasattr(module, name):
                getattr(module, name)(*args)

    def _run_context_lifecycle_point(self, name, args, context_type):
        try:
            mods = self._context_modules[context_type]
        except KeyError:
            mods = []
        for module in mods:
            if hasattr(module, name):
                getattr(module, name)(*args)

    def _run_decl_lifecycle_point(self, name, args):
        active_contexts = [
            context
            for context in self._contexts
            if context is not NotImplementedError
        ]
        active_context_types = list(dict.fromkeys( # Preserve order
            context['type']
            for context in active_contexts
        ))
        for context_type in active_context_types:
            # Will exist in the list of registered context modules, or the
            # context would have been NotImplementedError, and so filtered out.
            for module in self._context_modules[context_type]:
                # Will not call the same context module more than once, as
                # context modules cannot be registered against more than one
                # context type.
                if hasattr(module, name):
                    getattr(module, name)(
                        [
                            context
                            for context in active_contexts
                            if context['type'] == context_type
                        ],
                        *args
                    )

class Manifest:
    def __init__(self,
            items: dict[str, dict[str, object]],
            item_sets: dict[str, dict[str, dict[str, object]]]
    ):
        self._items = items
        self._item_sets = item_sets

    @staticmethod
    def from_raw(data):
        return Manifest(data['items'], data['item_sets'])

    def raw(self):
        return {
            'items': self._items,
            'item_sets': self._item_sets
        }

    def items(self):
        return self._items

    def item_sets(self):
        return self._item_sets

    def item(self, ref):
        self._items[ref]

    def item_set(self, ref):
        self._item_sets[ref]

class ManifestItemTags:
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

    def __eq__(self, value):
        return hasattr(value, '_tags') and self._tags == value._tags

class ManifestModule():
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
          collection/thing-a (thing, thing-type)
        }

        @context-type (someOption: /home/username/mystuff) {
          collection/thing-b (thing, thing-type)
        }

        @context-type (
            optionA: /home/username/directory
            optionB: https://someurl.com/username
        ) {
          collection/thing-c (thing, thing-type)
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

        self._manifests: list[Manifest] = None

        # Used as an internal cache of the combination of all manifests
        self._all_items_data = None
        self._all_item_sets_data = None
        self._all_tags_data = None
        self._all_extra_props_data = None

    def dependencies(self):
        return ['log']

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('ROOT')
        parser.add_variable('DEFAULT_ITEM_SET', default_is_none=True)

    def configure_args(self, *, parser: ArgumentParser, **_):
        # Options
        parser.add_argument('-p', '--property',
            action='append',
            help="""
            Specify a property to include for each output item. If given one or
            more times, excludes all properties not given. If given more than
            once, includes all properties specified. Supported properties
            include 'ref', 'tags', and any properties added by context modules.
            """)

        parser.add_argument('-t', '--tag',
            action='append',
            help="""
            Specify a tag to include for each output item. If given one or more
            times, excludes all tags not given. If given more than once,
            includes all tags specified.
            """)

        parser.add_argument('-f', '--format', default='compact',
            help="""
            Specify the formatter to use. May be one of:

            `compact` - Formats each item into a single line, showing the ref
            (default)   and all tags (in brackets, separated by commas), and
                        omits the blank line between items if formatting an item
                        set.
            `tabular` - Same as compact, but aligns the project ref and tag
                        key/value pairs into columns, as applicable.
            `object`  - Formats each item's ref, tags, and any other properties
                        each on their own line, or where a property's value is
                        multiple (ie. a list), then each value on its own line
                        with a header line for the property name.
            """)

        # Subcommands
        manifest_subparsers = parser.add_subparsers(dest="manifest_command")

        # Subcommands / Resolve Item
        resolve_parser = manifest_subparsers.add_parser('item')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to an item reference')

        resolve_parser.add_argument('--item-set',
            metavar='ITEM_SET_PATTERN',
            help="""
            A pattern that matches the item set to use to resolve the item
            """)

        # Subcommands / Resolve Item Set
        resolve_parser = manifest_subparsers.add_parser('item-set')

        resolve_parser.add_argument('pattern', metavar='PATTERN',
            help='A regex pattern to resolve to an item set')

    def configure(self, *, mod: ModuleManager, env: Namespace, **_):
        self._mod = mod # For methods that aren't directly given it

        if self._manifest_store is None:
            self._manifest_store = Store(env.VCS_MANIFEST_ROOT)

        if self._cache is None:
            self._cache = self._manifest_store

        self._default_item_set = env.VCS_MANIFEST_DEFAULT_ITEM_SET

    def start(self, *_, **__):
        for manifest_name in self._manifest_names:
            self._load_manifest(manifest_name)

    def _load_manifest(self, name):
        try:
            manifest_text = self._manifest_store.get(name+'.manifest.txt')
        except KeyError:
            self._mod.log().trace(
                f"Manifest '{name}' not found. Skipping."
            )
            return

        # Determine cache filename for this version of the manifest file
        digest = md5(manifest_text.encode('utf-8')).hexdigest()
        cache_name = '.'.join([name, 'manifest', digest, 'pickle'])

        # Try cache
        try:
            self._cache.setattr(cache_name, 'type', 'pickle')
            manifest = Manifest.from_raw(self._cache.get(cache_name))

        except KeyError:
            # Import Deps (these are slow to import, so only (re)parse the
            # manifest if needed)
            from antlr4 import InputStream, CommonTokenStream, ParseTreeWalker
            from modules.manifest_lang.build.ManifestLexer import ManifestLexer
            from modules.manifest_lang.build.ManifestParser import ManifestParser
            from modules.manifest_lang.manifest_listener import ManifestListenerImpl

            # Create Context Modules
            context_modules = {
                context_type: [
                    mod_factory()
                    for mod_factory in ctx_mod_factories
                ]
                for context_type, ctx_mod_factories in
                    self._ctx_mod_factories.items()
            }

            # Setup Parser
            input_stream = InputStream(manifest_text)
            lexer = ManifestLexer(input_stream)
            tokens = CommonTokenStream(lexer)
            parser = ManifestParser(tokens)
            tree = parser.manifest()

            # Start Builder
            manifest_builder = ManifestBuilder(
                self._mod.log(),
                context_modules,
                [name]
            )

            # Parse
            listener = ManifestListenerImpl(self._mod.log(), manifest_builder)
            walker = ParseTreeWalker()
            walker.walk(listener, tree)

            # Finalise
            manifest = manifest_builder.finalise()
            self._mod.log().info(
                f"Loaded manifest '{name}' from '{self._manifest_store}'"
            )

            # Cache Results
            self._cache.set(cache_name, manifest.raw())
            self._cache.flush()
            self._mod.log().trace(
                f"Cached result '{cache_name}' in '{self._cache}'"
            )

        # Add Manifest
        if self._manifests is None:
            self._manifests = []
        self._manifests.append(manifest)

    def __call__(self, *, mod: ModuleManager, args: Namespace, **_):
        mod.log().trace(f"manifest(args={args})")

        output = ''

        if args.manifest_command == 'item':
            item_set = self.get_item_set(args.item_set)
            output = self.get_item(args.pattern, item_set=item_set)

            output = self._filter_item(
                output,
                properties=args.property,
                tags=args.tag
            )
            output = self._format_item(output, format=args.format)
            print(output)

        if args.manifest_command == 'item-set':
            output = self.get_item_set(args.pattern)
            output = {
                name: self._filter_item(
                    output[name],
                    properties=args.property,
                    tags=args.tag
                )
                for name in output.keys()
            }
            output = self._format_item_set(output, format=args.format)
            print(output)

        return output

        # TODO:
        # - Check for existance of item, not just of manifest entry
        #   - Verify (-v, --verify) that the specified item exists locally,
        #     remotely, etc.
        #
        # - Map to relative if relative_to is 'manifest' or 'relative'
        #   - This now means outputting various values (eg. ref only, a specific
        #     tag, or another property)

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
        if self._manifests is not None and len(modules) > 0:
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

    def get_item_set(self, pattern: str = None) -> dict[str, dict[str, object]]:
        self._mod.log().trace(
            "manifest.get_item_set("
                +(f"{pattern}" if pattern is None else f"'{pattern}'")+
            ")"
        )

        if pattern is None:
            if self._default_item_set is None:
                item_set = self._all_items()
            else:
                item_set = self._all_item_sets()[self._default_item_set]
        else:
            item_set_regex = re.compile(pattern)
            try:
                item_set = next(
                    self._all_item_sets()[item_set_name]
                    for item_set_name in self._all_item_sets().keys()
                    if item_set_regex.search(item_set_name)
                )
            except (KeyError, StopIteration):
                raise VCSException(
                    f"item set not found from pattern '{pattern}'"
                )

        return item_set

    def get_item(self,
            pattern: str,
            *,
            item_set: dict[str, dict[str, object]] = None,
            properties: 'list[str]' = None
    ) -> dict[str, object]:
        self._mod.log().trace(
            "manifest.get_item("
                +(pattern if pattern is None else f"'{pattern}'")+","
                f" item_set={item_set},"
                f" properties={properties}"
            ")"
        )

        item_regex = re.compile(pattern)
        try:
            item = next(
                item
                for item in item_set.values()
                if item_regex.search(item['ref'])
            )
            self._mod.log().debug('found:', item)
        except StopIteration:
            raise VCSException(
                f"item not found from pattern '{pattern}'"
            )

        return item

    # Utils
    # --------------------

    def _all_items(self):
        if self._all_items_data is None:
            self._all_items_data = {
                ref: item
                for manifest in self._manifests
                for ref, item in manifest.items().items()
            }
        return self._all_items_data

    def _all_item_sets(self):
        if self._all_item_sets_data is None:
            self._all_item_sets_data = {
                ref: item_set
                for manifest in self._manifests
                for ref, item_set in manifest.item_sets().items()
            }
        return self._all_item_sets_data

    def _all_tags(self, item_set=None):
        # Cache the result for all items

        all_tags_data = []

        if item_set is None and self._all_tags_data is not None:
            return self._all_tags_data

        # NOTE: Key/value *pairs* are unique, not keys, so return a list
        process_items = item_set if item_set is not None else self._all_items()
        all_tags_data = list(dict.fromkeys(
            (tag_name, tag_value)
            for item in process_items.values()
            for tag_name, tag_value in item['tags'].items()
        ))

        if item_set is None:
            self._all_tags_data = all_tags_data

        return all_tags_data

    def _all_extra_props(self, item_set=None):
        # Cache the result for all items

        all_extra_props_data = []

        if item_set is None and self._all_extra_props_data is not None:
            return self._all_extra_props_data

        # NOTE: Key/value *pairs* are unique, not keys, so return a list
        process_items = item_set if item_set is not None else self._all_items()
        all_extra_props_data = list(dict.fromkeys(
            prop_name
            for item in process_items.values()
            for prop_name in item.keys()
            if prop_name not in ('ref', 'tags')
        ))

        if item_set is None:
            self._all_extra_props_data = all_extra_props_data

        return all_extra_props_data

    def _filter_item(self,
            item: 'dict[str, object]',
            properties=None,
            tags=None
    ):
        output = item
        if properties is not None:
            output = self._filter_obj(output, include=properties)
        if tags is not None:
            output = dict(output)
            output['tags'] = self._filter_obj(
                output['tags'],
                include=tags
            )
        return output

    def _format_item(self, item: 'dict[str, object]', format='object'):
        formatters = {
            'compact': self._format_item_compact,
            'object': self._format_item_object,
            'table': self._format_item_table
        }
        return formatters[format](item)

    def _format_item_compact(self, item: 'dict[str, object]'):
        extra_props = self._filter_obj(item, exclude=('ref', 'tags'))
        return ' '.join([
            *(
                [item['ref']]
                if 'ref' in item else []
            ),
            *(
                ['(' + ', '.join(
                    name+(': '+value if value is not None else '')
                    for name, value in item['tags'].items()
                ) + ')']
                if 'tags' in item else []
            ),
            *(
                ['|', ', '.join(
                    f'{key}: {value}'
                    for key, value in extra_props.items()
                )]
                if len(extra_props) > 0 else []
            )
        ])

    def _format_item_object(self, item: 'dict[str, object]'):
        extra_props = self._filter_obj(item, exclude=('ref', 'tags'))
        return '\n'.join([
            *(
                [f"ref: {item['ref']}"]
                if 'ref' in item else []
            ),
            *(
                [f"tags:", '\n'.join(
                    '  '+name+(': '+value if value is not None else '')
                    for name, value in item['tags'].items()
                )]
                if 'tags' in item else []
            ),
            *(
                [
                    f'{key}: {value}'
                    for key, value in extra_props
                ]
                if len(extra_props) > 0 else []
            )
        ])

    def _format_item_table(self,
            item: 'dict[str, object]',
            ref_width: int,
            tag_cols: dict[str, int],
            prop_cols: dict[str, int]
    ):
        ref_parts = (
            [f"{item['ref']:<{ref_width}}"]
            if 'ref' in item else []
        )

        if 'tags' in item:
            tag_strs = []
            for name, width in tag_cols.items():
                tag_str = f"{'':<{width}}"
                if name in item['tags']:
                    if item['tags'][name] is None:
                        tag_str = f"{name:^{width}}"
                    else:
                        value = item['tags'][name]
                        tag_str = f"{self._format_tag(name, value):<{width}}"
                tag_strs.append(tag_str)

            tag_parts = (
                ['(' + ', '.join(tag_strs) + ')']
                if len(tag_strs) > 0
                else []
            )
        else:
            tag_parts = []

        if len(prop_cols) > 0:
            prop_strs = []
            for name, width in prop_cols.items():
                prop_str = f"{'':<{width}}"
                if name in item and item[name] is not None:
                    value = item[name]
                    prop_str = f"{self._format_prop(name, value):<{width}}"
                prop_strs.append(prop_str)

            prop_parts = (
                ['|', ', '.join(prop_strs)]
                if len(prop_strs) > 0
                else []
            )
        else:
            prop_parts = []

        return ' '.join([*ref_parts, *tag_parts, *prop_parts])

    def _format_item_set(self,
            item_set: 'dict[str, dict[str, object]]',
            format='object'
    ):
        formatters = {
            'compact': self._format_item_set_compact,
            'object': self._format_item_set_object,
            'table': self._format_item_set_table
        }
        return formatters[format](item_set)

    def _format_item_set_compact(self, item_set: 'dict[str, dict[str, object]]'):
        item_set = {
            name: self._format_item(
                item_set[name],
                format='compact'
            )
            for name in item_set.keys()
        }
        return '\n'.join(item_set.values())

    def _format_item_set_object(self, item_set: 'dict[str, dict[str, object]]'):
        item_set = {
            name: self._format_item(
                item_set[name],
                format='object'
            )
            for name in item_set.keys()
        }
        return '\n\n'.join(item_set.values())

    def _format_item_set_table(self, item_set: 'dict[str, dict[str, object]]'):
        ref_width = max(len(item['ref']) for item in item_set.values())
        tag_cols = {
            name: max(
                (
                    len(self._format_tag(name, item['tags'][name]))
                    if name in item['tags']
                    else 0
                )
                for item in item_set.values()
            )
            for name, _ in self._all_tags(item_set)
        }
        prop_cols = {
            name: max(
                (
                    len(self._format_prop(name, item[name]))
                    if name in item
                    else 0
                )
                for item in item_set.values()
            )
            for name in self._all_extra_props(item_set)
        }

        item_set = {
            name: self._format_item_table(
                item_set[name],
                ref_width=ref_width,
                tag_cols=tag_cols,
                prop_cols=prop_cols
            )
            for name in item_set.keys()
        }
        return '\n'.join(item_set.values())

    def _format_tag(self, name, value=None):
        return name+(': '+value if value is not None else '')

    def _format_prop(self, name, value):
        return f'{name}: {value}'

    def _filter_obj(self, item, include=None, exclude=None):
        if include is None:
            include = item.keys()
        if exclude is None:
            exclude = ()
        return {
            prop: item[prop]
            for prop in include
            if prop in item and prop not in exclude
        }
