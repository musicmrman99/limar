from hashlib import md5
import re
import random

from core.store import Store
from core.modulemanager import ModuleAccessor
from core.exceptions import LIMARException
from core.modules.phase_utils.phase_system import PhaseSystem

# Types
from core.modules.log import LogModule
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, Namespace
from typing import Any, Callable, Iterable

ItemRef = str
ItemSetRef = str | tuple[str, str] # (tag_name, tag_value)

Item = dict[str, Any]
ItemSet = dict[ItemRef, Item]
ItemSetSet = dict[ItemSetRef, ItemSet]

ContextModule = Any

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

    def get(self, name, default=None):
        return self._tags.get(name, default)

    def raw(self):
        return self._tags

    def __eq__(self, value):
        return hasattr(value, '_tags') and self._tags == value._tags

    def __contains__(self, value):
        return value in self._tags

class Manifest:

    TAG_OPT_CONTINUOUS = 'continuous'

    STAGES_ORDERED = [
        'initialising',
        'entered',
        'exited'
    ]
    STAGES = Namespace(**{
        name: name
        for name in STAGES_ORDERED
    })

    # Constructors
    # --------------------

    def __init__(self,
            logger: LogModule,
            digest: str,
            initial_items: ItemSet | None = None,
            initial_item_sets: ItemSetSet | None = None,
            initial_contexts: list[str] | None = None,
            context_modules: dict[str, list[ContextModule]] | None = None,
    ):
        """
        Use `initial_items` and `initial_item_sets` as the initial items and
        item sets of this Manifest. Further items and item sets can be declared
        using this Manifest's methods.

        `initial_contexts` is a list of context type names to enter immediately
        after entering the manifest. Enter the contexts in the order the names
        are given, passing no options to each. Raise a LIMARException if any
        module names given in `initial_contexts` are not defined in
        `context_modules`.

        `context_modules` must be a dictionary of the following format:
            {'context-type-name': [context_module, ...], ...}
        """

        # Inputs
        self._logger = logger
        self._digest = digest
        self._context_modules = (
            context_modules if context_modules is not None else {}
        )
        self._initial_contexts = (
            initial_contexts if initial_contexts is not None else []
        )
        for name in self._initial_contexts:
            if name not in self._context_modules:
                raise LIMARException(
                    f"Initial context '{name}' not available to manifest"
                )

        # Inputs and Outputs
        self._items: ItemSet = (
            initial_items
            if initial_items is not None
            else {}
        )
        self._item_sets: ItemSetSet = (
            initial_item_sets
            if initial_item_sets is not None
            else {}
        )

        # Internal
        # Note: Same signature as an ItemSet, but different structure
        self._tags: dict[str, dict[str, Any]] = {}
        self._contexts = []
        self._stage = self.STAGES.initialising

    @staticmethod
    def from_raw(
            logger: LogModule,
            raw_data: dict[str, Any],
            initial_contexts: list[str] | None = None,
            context_modules: dict[str, list[ContextModule]] | None = None
    ):
        return Manifest(
            logger,
            raw_data['digest'],
            raw_data['items'],
            raw_data['item_sets'],
            initial_contexts,
            context_modules
        )

    # Mutators
    # --------------------

    def enter(self):
        if self._stage != self.STAGES.initialising:
            raise LIMARException(
                "Attempt to call Manifest.enter() outside of"
                f" '{self.STAGES.initialising}' stage (was in '{self._stage}'"
                f" stage)"
            )
        self._stage = self.STAGES.entered

        # Call - 'on_enter_manifest' on all registered context modules
        self._run_manifest_lifecycle_point('on_enter_manifest', [])

        # Enter each initial context
        for context_name in self._initial_contexts:
            self.enter_context(context_name)

    def exit(self):
        if self._stage != self.STAGES.entered:
            raise LIMARException(
                "Attempt to call Manifest.exit() outside of"
                f" '{self.STAGES.entered}' stage (was in '{self._stage}' stage)"
            )

        # Exit each initial context
        for _ in range(len(self._initial_contexts)):
            self.exit_context()

        # Call - 'on_exit_manifest' on all registered context modules
        self._run_manifest_lifecycle_point('on_exit_manifest',
            [self._items, self._item_sets]
        )

        # Finalise - tag set
        for item in self._items.values():
            item['tags'] = item['tags'].raw()

        self._stage = self.STAGES.exited

    def enter_context(self, type, opts = None):
        if self._stage != self.STAGES.entered:
            raise LIMARException(
                "Attempt to call Manifest.enter_context() outside of"
                f" '{self.STAGES.entered}' stage (was in '{self._stage}' stage)"
            )

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
        if self._stage != self.STAGES.entered:
            raise LIMARException(
                "Attempt to call Manifest.exit_context() outside of"
                f" '{self.STAGES.entered}' stage (was in '{self._stage}' stage)"
            )

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

    def declare_tag(self, ref, tags = None):
        if (
            self._stage != self.STAGES.entered and
            len(self._context_modules) > 0
        ):
            raise LIMARException(
                "Attempt to call Manifest.declare_tag() outside of"
                f" '{self.STAGES.entered}' stage with uninitialised context"
                f" modules present (was in '{self._stage}' stage)"
            )

        # Validate
        if ref in self._tags:
            raise LIMARException(f"Manifest tag already exists with ref '{ref}'")

          # Add to main item set
        self._tags[ref] = tags if tags is not None else {}

    # Util for _declare_item()
    def _on_add_item_tags(self, item_ref, tags):
        for tag_name, tag_value in tags.items():
            if tag_name not in self._item_sets.keys():
                self._item_sets[tag_name] = {}
            self._item_sets[tag_name][item_ref] = self._items[item_ref]

            if (
                tag_value is not None and
                not ( # Value indexing not disabled for this tag
                    tag_name in self._tags and
                    self.TAG_OPT_CONTINUOUS in self._tags[tag_name]
                )
            ):
                indexed_tag = (tag_name, tag_value)
                if indexed_tag not in self._item_sets.keys():
                    self._item_sets[indexed_tag] = {}
                self._item_sets[indexed_tag][item_ref] = self._items[item_ref]

    # Util for _declare_item()
    def _on_remove_item_tags(self, item_ref, names):
        for tag_name in names:
            if item_ref in self._item_sets[tag_name].keys():
                del self._item_sets[tag_name][item_ref]

            if len(self._item_sets[tag_name]) == 0:
                del self._item_sets[tag_name]

    def declare_item(self, ref: ItemRef, tags = None):
        if (
            self._stage != self.STAGES.entered and
            len(self._context_modules) > 0
        ):
            raise LIMARException(
                "Attempt to call Manifest.declare_item() outside of"
                f" '{self.STAGES.entered}' stage with uninitialised context"
                f" modules present (was in '{self._stage}' stage)"
            )

        # Validate
        if ref in self._items:
            raise LIMARException(
                f"Manifest item already exists with ref '{ref}'"
            )

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
    def _get_item(self, ref: str):
        return (
            self._items[ref]
            if ref in self._items
            else None
        )

    # Util for _declare_item_set()
    def _get_item_set(self, ref: str, value: str | None = None):
        if ref not in self._item_sets:
            return None
        elif value is None:
            return self._item_sets[ref]
        else:
            return self._item_sets[(ref, value)]

    # Util for _declare_item_set()
    def _compute_set(self, ops_btree) -> ItemSet:
        # Base Case: Empty set
        if ops_btree is None:
            return {}

        # Base Case: Declared or tag item set or item
        if type(ops_btree) is str:
            item_set = self._get_item_set(ops_btree)
            if item_set is not None:
                return item_set

            item = self._get_item(ops_btree)
            if item is not None:
                return {item['ref']: item}

            return {} # Empty item set

        # Base Case: Tag item set with indexed value
        if type(ops_btree) is tuple:
            item_set = self._get_item_set(*ops_btree)
            if item_set is not None:
                return item_set

            return {} # Empty item set

        # Recursive Case: Binary operation
        left_item_set = self._compute_set(ops_btree['left'])
        right_item_set = self._compute_set(ops_btree['right'])

        combined_set = {}
        combined_set.update(left_item_set)
        combined_set.update(right_item_set)

        if ops_btree['operator'] == '&':
            return {
                item_name: item
                for item_name, item in combined_set.items()
                if item_name in left_item_set and item_name in right_item_set
            }

        elif ops_btree['operator'] == '|':
            return combined_set

        else:
            raise LIMARException(
                f"Unsupported set operator '{ops_btree['operator']}' when"
                " computing item set"
            )

    def declare_item_set(self, ref: ItemSetRef, ops_btree):
        if (
            self._stage != self.STAGES.entered and
            len(self._context_modules) > 0
        ):
            raise LIMARException(
                "Attempt to call Manifest.declare_item_set() outside of"
                f" '{self.STAGES.entered}' stage with uninitialised context"
                f" modules present (was in '{self._stage}' stage)"
            )

        # Validate
        if ref in self._item_sets:
            raise LIMARException(
                f"Manifest item set already exists with ref '{ref}'"
            )

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

    # Getters
    # --------------------

    def digest(self) -> str:
        return self._digest

    def items(self) -> ItemSet:
        return self._items

    def item_sets(self) -> ItemSetSet:
        return self._item_sets

    def item(self, ref: ItemRef) -> Item:
        return self._items[ref]

    def item_set(self, ref: ItemSetRef) -> ItemSet:
        return self._item_sets[ref]

    def raw(self) -> dict[str, Any]:
        return {
            'digest': self._digest,
            'items': self._items,
            'item_sets': self._item_sets
        }

    # Utils
    # --------------------

    def _run_manifest_lifecycle_point(self, name, args):
        mods = [
            mod
            for mod_set in self._context_modules.values()
            for mod in mod_set
        ]
        for module in mods:
            if hasattr(module, name):
                getattr(module, name)(*args, logger=self._logger)

    def _run_context_lifecycle_point(self, name, args, context_type):
        try:
            mods = self._context_modules[context_type]
        except KeyError:
            mods = []
        for module in mods:
            if hasattr(module, name):
                getattr(module, name)(*args, logger=self._logger)

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
                        *args,
                        logger=self._logger
                    )

MANIFEST_LIFECYCLE = PhaseSystem(
    f'{__name__}:lifecycle',
    (
        'INITIALISE',
        'GET',
        'FLATTEN',
        'TABULATE',
        'RENDER'
    ),
    initial_phase='INITIALISE'
)

class ManifestModule:
    """
    MM module to parse all manifest files declared by added context modules and
    to provide information about the items they declare.

    # Manifest Files

    Manifest files are made up of declarations, contexts, and comments.

    ## Comments

    Comments begin with a '#' and can be placed on their own lines, or after
    most lines. Multi-line comments aren't supported (apart from by using
    multiple single-line comments).

    ## Declarations

    There are two types of declarations: items and item sets.

    Items declare a named thing to exist. Item declarations may include a list
    of tags (key-value pairs, where the value is optional, defaulting to None if
    omitted) in brackets after the name and one or more spaces. Tags are
    separated by a comma, a newline, or both.

    Item sets declare a named set of things to exist. Item set declarations must
    include an expression stating what other items and item sets this item set
    includes. An implicit item set exists for each unique tag associated with
    any item, which includes all items with that tag. Item set expressions
    consist of the names of items, implicit item sets, and explicit item sets,
    with each name separated by either the `&` (and/intersection) or `|`
    (or/union) operators to combine the referenced sets in the relevant ways.
    Nested item set expressions with operators between them are also supported.

    All items are declared in a single global scope. They must all have
    different refs, even across files. All items in a file up to the declaration
    of an item set may be included in that set.

    ## Context Modules

    During the configuration phase (as long as it's after manifest's own
    configuration), other MM modules can register 'context modules' with the
    ManifestModule. Context modules are used to extend the manifest format by
    implementing custom 'context types'. Each context module declares itself as
    being of a single context type. In a manifest file, a context of a given
    type is 'applied' by using the syntax `@context-type` (where `context-type`
    may be any valid context type name), which gives all context modules
    declared as being of that type an opportunity to customise the data
    generated from all items and item sets that the context applies to, usually
    to extend items with custom tags and fields.

    A context applies to all declarations up to the first blank line after it,
    or to all declarations within a pair of braces after the context type and
    zero or more spaces. The set of declarations that a context applies to is
    called the 'context content'. Each declaration within the context content
    must be on a separate line. Nested contexts are supported. The
    semantics/behaviour of nested contexts depends on the context modules
    registered for the nested context type(s) being applied.

    Contexts may also take options. Options are specified by placing key-value
    pairs (where the value is optional and defaults to 'None' if omitted) within
    a pair of brackets after the context type and zero or more spaces. Options
    are separated either by a comma, a newline, or both.

    Some context types are also 'root' context types. ManifestModule reads all
    manifest files from the manifest root directory that have the same names as
    the registered root context types with the '.manifest.txt' file extension.
    For each manifest file that is read, the corresponding root context type is
    applied by default to all declarations within the file.

    ## Implementing a Context Module

    Each context module must be a Python class. The class must define one class
    method:

    - `context_type()`
      - Return the context type (a string) for this context module.

    It may also define an additional class method:

    - `can_be_root()`
      - Return True if the context type supports being used as a root context,
        otherwise return False. Only one context module for a context type
        needs to return True for this method for that context type to be
        applied. This method not being defined for a context module is
        equivalent to it returning False.

    It may define any of the following method-based hooks (at least one must be
    defined to make the context module do anything):

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

    # Examples

    ```text
    example-item
    example-item-tagged (tagA)
    example-item-multi-tag (tagA, tagB, tagC)

    # The 'example-item' item will also contain the tag `tagA` without a value
    # and the tag `some-tag` with the value '/home/username/mystuff' if the
    # `Tags` context module is registered. The same system applies for all the
    # following context examples.
    @tags (tagA, some-tag: /home/username/mystuff)
    example-item2 (thing, thing-type)

    # Contexts that are stacked like this are actually nested.
    @project
    @uris (path: /home/username/Source)
    # Refs can contain slashes, but tag names can't
    collection/thing-a (thing, thing-typeA)
    collection/thing-b (thing, thing-typeB)
    collection/thing-c (thing, thing-typeC)
    other              (other)
    # Refs can contain anything except tripple quote if tripple quoted
    \"\"\"!"£$%^&*()_+-=[]{};:'@#~,<.>/?\\|\"\"\" (yay)

    # Can now declare a set containing items declared above it.
    item-set-example [thing-typeB | other]

    # Items can be anything - contexts may add data to them, possibly pulling it
    # from various sources. Other MM modules that use ManifestModule may also
    # interpret the data that items define in their own ways.
    @house (
        # You can't put comments after the end of a key-value pair unless it
        # it has a comma after it (the context option separator, meaning it's
        # not the last context option)
        address: 100 My Place; Riverdale; Nationale, # Like this
        controller: https://example.com/my-house/controller
    ) {
        @room (kitchen)
        chair/x (furnature, legs: 3, broken)
        chair/y (furnature, legs: 4)
        chair/z (furnature, legs: 4)
        table   (furnature)
        knife-1 (cutlery)
        fork-1  (cutlery)
        fork-2  (cutlery)
        plate-1 (crockery)
        bowl-1  (crockery)

        # @room doesn't apply to these item sets
        dinner-set [cutlery | crockery]
    }
    ```
    """

    # Lifecycle
    # --------------------

    def __init__(self, manifest_store: Store | None = None):
        self._manifest_store = manifest_store

        self._ctx_mod_factories: dict[str, list[Callable[[], Any]]] = {}
        self._manifest_names: list[str] = []

        self._manifests: dict[str, Manifest] = {}
        self._global_manifest: Manifest | None = None

        # Internal caches
        self._all_tags_data = None
        self._all_extra_props_data = None

    def dependencies(self):
        return ['log', 'phase', 'cache', 'tr']

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('ROOT')
        parser.add_variable('DEFAULT_ITEM_SET', default_is_none=True)

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
        parser.add_argument('--input-format', default=None,
            help="""
            The format of the forwarded input. Irrelevant without using `-L` to
            start at a phase after GET. The default is item-set, unless the
            forwarded input contains both the `ref` and `tags` properties, in
            which case it defaults to `item`.
            """)

        # Subcommands
        manifest_subparsers = parser.add_subparsers(dest="manifest_command")

        # Subcommands / Resolve Item
        item_parser = manifest_subparsers.add_parser('item')
        mod.docs.add_docs_arg(item_parser)

        item_parser.add_argument('pattern', metavar='PATTERN', nargs='?',
            help='A regex pattern to resolve to an item')

        item_parser.add_argument('--item-set',
            metavar='ITEM_SET_PATTERN',
            help="""
            A pattern that matches the item set to use to resolve the item
            """)

        # Subcommands / Resolve Item - Output Controls
        item_parser.add_argument('-T', '--tags', default=':all',
            help="""
            Specify a comma-separated list of item tags to include in the
            output. Use the value ':all' to show all tags, or ':none' to show no
            tags. The default is ':all'.
            """)

        item_parser.add_argument('-P', '--properties', default=':none',
            help="""
            Specify a comma-separated list of extra item properties (ie. other
            than 'ref' and 'tags') to include in the output. Use the value
            ':all' to show all extra properties, or ':none' to show no extra
            properties. The default is ':none'.
            """)

        mod.phase.configure_phase_control_args(item_parser)

        # Subcommands / Resolve Item Set
        item_set_parser = manifest_subparsers.add_parser('item-set')
        mod.docs.add_docs_arg(item_set_parser)

        item_set_parser.add_argument('-s', '--item-set-spec',
            action='store_true', default=False,
            help="""
            Interpret the item set PATTERN as an item set spec (ie. the part
            between `[` and `]` in an item set declaration of a manifest file).
            This allows dynamically extracting sets of items from multiple
            manifest files.

            Note: The set is actually declared in the manifest for the duration
            of the app run, but is created with a randomly generated ref, so is
            effectively inaccessible.
            """)

        item_set_parser.add_argument('pattern', metavar='PATTERN', nargs='?',
            help="""
            A regex pattern to resolve to an item set, or an item set spec if
            `--set` was given (see its help for details).
            """)

        # Subcommands / Resolve Item Set - Output Controls
        item_set_parser.add_argument('-T', '--tags', default=':all',
            help="""
            Specify a comma-separated list of item tags to include in the
            output. Use the value ':all' to show all tags, or ':none' to show no
            tags. The default is ':all'.
            """)

        item_set_parser.add_argument('-P', '--properties', default=':none',
            help="""
            Specify a comma-separated list of extra item properties (ie. other
            than 'ref' and 'tags') to include in the output. Use the value
            ':all' to show all extra properties, or ':none' to show no extra
            properties. The default is ':none'.
            """)

        item_set_parser.add_argument('-G', '--grid',
            action='store_true', default=False,
            help="""
            Render lines between rows of the table (useful for wide tables, but
            almost doubles the table hight).
            """)

        mod.phase.configure_phase_control_args(item_set_parser)

    def configure(self, *, mod: Namespace, env: Namespace, **_):
        self._mod = mod # For methods that aren't directly given it

        mod.phase.register_system(MANIFEST_LIFECYCLE)

        if self._manifest_store is None:
            self._manifest_store = Store(env.ROOT)

        self._default_item_set = env.DEFAULT_ITEM_SET

    def start(self, *_, mod: Namespace, **__):
        for manifest_name in self._manifest_names:
            self._load_manifest(manifest_name)

        all_items = {}
        for manifest in self._manifests.values():
            for ref, item in manifest.items().items():
                if ref in all_items:
                    raise LIMARException(
                        f"Manifest item with ref '{ref}' already declared in"
                        " another manifest"
                    )
                all_items[ref] = item

        all_item_sets = {}
        for manifest in self._manifests.values():
            for ref, item_set in manifest.item_sets().items():
                if ref in all_item_sets:
                    mod.log.warning(
                        f"Manifest item set with ref '{ref}' already declared"
                        " in another manifest. Merging into existing item set."
                    )
                    all_item_sets[ref].update(item_set)
                else:
                    all_item_sets[ref] = item_set

        self._global_manifest = Manifest(
            self._mod.log,
            md5(
                ''.join(
                    manifest.digest()
                    for manifest in self._manifests.values()
                ).encode('utf-8')
            ).hexdigest(),
            all_items,
            all_item_sets
        )

    def _load_manifest(self, name):
        assert self._manifest_store is not None, 'ManifestModule._load_manifest() called before ManifestModule.configure()'
        try:
            manifest_text = self._manifest_store.get(name+'.manifest.txt')
        except KeyError:
            self._mod.log.trace(
                f"Manifest '{name}' not found. Skipping."
            )
            return

        # Determine cache filename for this version of the manifest file
        digest = md5(manifest_text.encode('utf-8')).hexdigest()
        cached_name = '.'.join(['manifest', name, digest, 'pickle'])

        # Try cache
        try:
            manifest = Manifest.from_raw(
                self._mod.log,
                self._mod.cache.get(cached_name)
            )

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
            manifest = Manifest(
                self._mod.log,
                digest,
                None,
                None,
                [name],
                context_modules
            )

            # Parse
            listener = ManifestListenerImpl(self._mod.log, manifest)
            walker = ParseTreeWalker()
            walker.walk(listener, tree)

            # Log
            self._mod.log.info(
                f"Loaded manifest '{name}' from '{self._manifest_store}'"
            )

            # Cache Results
            self._mod.cache.set(cached_name, manifest.raw())

        # Add Manifest
        self._manifests[name] = manifest

    def __call__(self, *,
            mod: Namespace,
            args: Namespace,
            forwarded_data: Any,
            output_is_forward: bool,
            **_
    ):
        mod.log.trace(f"manifest(args={args})")

        # Set up phase process and a common transition function
        # WARNING: THIS MUTATES STATE, even though it's used in `if` statements
        transition_to_phase = mod.phase.create_process(MANIFEST_LIFECYCLE, args)

        output: Any = forwarded_data
        # Very likely to be an item, not an item set, but can be overridden with
        # `--input-format item-set`
        if args.input_format == 'item-set':
            pass
        elif (
            args.input_format == 'item' or
            isinstance(output, dict) and 'ref' in output and 'tags' in output
        ):
            output = {output['ref']: output}

        if args.manifest_command == 'item':
            if transition_to_phase(MANIFEST_LIFECYCLE.PHASES.GET):
                if args.pattern is None:
                    raise LIMARException(
                        'PATTERN is required if running GET phase'
                    )

                item_set = self.get_item_set(args.item_set)
                output = self.get_item(args.pattern, item_set=item_set)

            if transition_to_phase(
                MANIFEST_LIFECYCLE.PHASES.FLATTEN, not output_is_forward
            ):
                output = self._list_flattened_items(
                    {'': output},
                    filter_tags=self._filter_str_to_list(args.tags),
                    filter_extra_props=self._filter_str_to_list(args.properties)
                )

            if transition_to_phase(
                MANIFEST_LIFECYCLE.PHASES.TABULATE, not output_is_forward
            ):
                output = mod.tr.tabulate(output, obj_mapping='all')

            if transition_to_phase(
                MANIFEST_LIFECYCLE.PHASES.RENDER, not output_is_forward
            ):
                output = mod.tr.render_table(output, has_headers=True)

        elif args.manifest_command == 'item-set':
            if transition_to_phase(MANIFEST_LIFECYCLE.PHASES.GET):
                if args.pattern is None:
                    raise LIMARException(
                        'PATTERN is required if running GET phase'
                    )

                if args.item_set_spec:
                    ref = f'{random.getrandbits(4*32):0{32}x}'
                    self.declare_item_set(ref, args.pattern)
                    output = self.get_item_set(ref)
                else:
                    output = self.get_item_set(args.pattern)

            if transition_to_phase(
                MANIFEST_LIFECYCLE.PHASES.FLATTEN, not output_is_forward
            ):
                output = self._list_flattened_items(
                    output,
                    filter_tags=self._filter_str_to_list(args.tags),
                    filter_extra_props=self._filter_str_to_list(args.properties)
                )

            if transition_to_phase(
                MANIFEST_LIFECYCLE.PHASES.TABULATE, not output_is_forward
            ):
                output = mod.tr.tabulate(output, obj_mapping='all')

            if transition_to_phase(
                MANIFEST_LIFECYCLE.PHASES.RENDER, not output_is_forward
            ):
                output = mod.tr.render_table(
                    output, has_headers=True, show_lines=args.grid
                )

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

    @ModuleAccessor.invokable_as_config
    def add_context_modules(self, *modules: Any) -> None:
        """
        Allows other modules to extend the manifest format with new contexts.
        """

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
                module.can_be_root() and
                module.context_type() not in self._manifest_names
            ):
                self._manifest_names.append(module.context_type())

    # Invokation
    # --------------------

    @ModuleAccessor.invokable_as_service
    def get_manifest_digest(self, name: str) -> str:
        return self._manifests[name].digest()

    @ModuleAccessor.invokable_as_service
    def declare_item_set(self, ref: str, item_set_spec):
        assert self._global_manifest is not None, '_global_manifest is initialised in STARTING phase, but this method is only run during RUNNING phase'

        # This is effectively parsing a fragment of a manifest, rather than a
        # whole manifest, but this way makes sure it goes through exactly the
        # same process as parsing a real manifest, just with no contexts.

        # Import Deps (these are slow to import, so only (re)parse the
        # manifest if needed)
        from antlr4 import InputStream, CommonTokenStream, ParseTreeWalker
        from modules.manifest_lang.build.ManifestLexer import ManifestLexer
        from modules.manifest_lang.build.ManifestParser import ManifestParser
        from modules.manifest_lang.manifest_listener import ManifestListenerImpl

        # Setup Parser
        input_stream = InputStream(f'"""{ref}""" [{item_set_spec}]')
        lexer = ManifestLexer(input_stream)
        tokens = CommonTokenStream(lexer)
        parser = ManifestParser(tokens)
        tree = parser.itemSet()

        # Parse
        listener = ManifestListenerImpl(self._mod.log, self._global_manifest)
        walker = ParseTreeWalker()
        walker.walk(listener, tree)

    @ModuleAccessor.invokable_as_service
    def get_item_set(self, pattern: str | None = None) -> ItemSet:
        assert self._global_manifest is not None, '_global_manifest is initialised in STARTING phase, but this method is only run during RUNNING phase'

        self._mod.log.trace(
            "manifest.get_item_set("
                +(f"{pattern}" if pattern is None else f"'{pattern}'")+
            ")"
        )

        item_set = None
        if pattern is None:
            if self._default_item_set is None:
                item_set = self._global_manifest.items()
            else:
                item_set = self._global_manifest.item_set(self._default_item_set)

        if pattern is not None and item_set is None:
            try:
                item_set = self._global_manifest.item_set(pattern)
            except KeyError:
                self._mod.log.debug(f"No item set with ref '{pattern}'")

        if pattern is not None and item_set is None:
            item_set_regex = re.compile(pattern)
            try:
                ref, item_set = next(
                    (ref, item_set)
                    for ref, item_set in self._global_manifest.item_sets().items()
                    if (
                        (type(ref) == str and item_set_regex.search(ref)) or
                        (type(ref) == tuple and item_set_regex.search(ref[0]))
                    )
                )
                self._mod.log.info(f"Matched item set '{ref}'")
                self._mod.log.debug('Item set refs:', tuple(item_set.keys()))
            except (KeyError, StopIteration):
                self._mod.log.debug(
                    f"Item set not found from pattern '{pattern}'"
                )

        if item_set is None:
            raise LIMARException(f"Item set not found from pattern '{pattern}'")

        return item_set

    @ModuleAccessor.invokable_as_service
    def get_item(self,
            pattern: str,
            *,
            item_set: ItemSet | None = None,
            properties: list[str] | None = None
    ) -> Item:
        assert self._global_manifest is not None, '_global_manifest is initialised in STARTING phase, but this method is only run during RUNNING phase'

        self._mod.log.trace(
            "manifest.get_item("
                +(pattern if pattern is None else f"'{pattern}'")+","
                f" item_set={item_set},"
                f" properties={properties}"
            ")"
        )

        if item_set is None:
            item_set = self._global_manifest.items()

        item = None
        try:
            item = item_set[pattern]
        except KeyError:
            self._mod.log.debug(
                f"No item with ref '{pattern}', trying pattern matching ..."
            )

        if item is None:
            item_regex = re.compile(pattern)
            try:
                ref, item = next(
                    (ref, item)
                    for ref, item in item_set.items()
                    if item_regex.search(ref)
                )
                self._mod.log.info(f"Matched item '{ref}'")
                self._mod.log.debug('Item data:', item)
            except StopIteration:
                self._mod.log.debug(
                    f"Item not found from pattern '{pattern}'"
                )

        if item is None:
            raise LIMARException(f"Item not found from pattern '{pattern}'")

        return item

    @ModuleAccessor.invokable_as_service
    def get_items(self,
            patterns: list[str],
            *,
            item_set: ItemSet | None = None,
            properties: list[str] | None = None
    ) -> ItemSet:
        return self._mod.tr.index([
            self.get_item(pattern, item_set=item_set, properties=properties)
            for pattern in patterns
        ])

    # Utils
    # --------------------

    # Transformation Stage

    def _filter_str_to_list(self, list_: str) -> list[str] | None:
        if list_ == ':all':
            return None # None = no filter = all
        elif list_ == ':none':
            return []
        else:
            return list_.split(',')

    def _list_flattened_items(self,
            item_set: ItemSet,
            filter_tags: list[str] | None = None,
            filter_extra_props: list[str] | None = None
    ) -> list[dict[str, Any]]:
        return [
            self._flatten_item(
                item,
                self._all_tags(item_set),
                self._all_extra_props(item_set),
                filter_tags=filter_tags,
                filter_extra_props=filter_extra_props
            )
            for item in item_set.values()
        ]

    def _flatten_item(self,
            item: Item,
            all_tags: list[str] | None = None,
            all_extra_props: list[str] | None = None,
            filter_tags: list[str] | None = None,
            filter_extra_props: list[str] | None = None
    ) -> dict[str, Any]:
        all_tags_computed: Iterable[str] = []
        if all_tags is not None:
            all_tags_computed = all_tags
        elif 'tags' in item:
            all_tags_computed = item['tags']

        all_extra_props_computed: Iterable[str] = []
        if all_extra_props is not None:
            all_extra_props_computed = all_extra_props
        else:
            all_extra_props_computed = [
                key
                for key in item.keys()
                if key not in ['ref', 'tags']
            ]

        return {
            'ref': item['ref'],
            **(
                {
                    f':{tag}': self._format_item_tag(item, tag)
                    for tag in all_tags_computed
                    if filter_tags is None or tag in filter_tags
                }
                if filter_tags is None or len(filter_tags) > 0
                else {}
            ),
            **(
                {
                    f'.{prop}': self._format_item_prop(item, prop)
                    for prop in all_extra_props_computed
                    if filter_extra_props is None or prop in filter_extra_props
                }
                if filter_extra_props is None or len(filter_extra_props) > 0
                else {}
            )
        }

    def _format_item_tag(self, item, tag):
        if 'tags' in item and tag in item['tags']:
            if item['tags'][tag] is not None:
                return item['tags'][tag]
            return '✓'
        return None

    def _format_item_prop(self, item, prop):
        if prop in item:
            return item[prop]
        return None

    # Collators

    def _all_tags(self,
            item_set=None,
            with_values=False
    ) -> list[Any]:
        assert self._global_manifest is not None, '_global_manifest is initialised in STARTING phase, but this method is only run during RUNNING phase'

        # Cache the result for all items
        all_tags_data = []

        if item_set is None and self._all_tags_data is not None:
            return self._all_tags_data

        # NOTE: Key/value *pairs* are unique, not keys, so return a list
        process_items = (
            item_set
            if item_set is not None
            else self._global_manifest.items()
        )
        all_tags_data = list(dict.fromkeys(
            (tag_name, tag_value) if with_values else tag_name
            for item in process_items.values()
            for tag_name, tag_value in item['tags'].items()
        ))

        if item_set is None:
            self._all_tags_data = all_tags_data

        return all_tags_data

    def _all_extra_props(self, item_set=None):
        assert self._global_manifest is not None, '_global_manifest is initialised in STARTING phase, but this method is only run during RUNNING phase'

        # Cache the result for all items
        all_extra_props_data = []

        if item_set is None and self._all_extra_props_data is not None:
            return self._all_extra_props_data

        # NOTE: Key/value *pairs* are unique, not keys, so return a list
        process_items = (
            item_set
            if item_set is not None
            else self._global_manifest.items()
        )
        all_extra_props_data = list(dict.fromkeys(
            prop_name
            for item in process_items.values()
            for prop_name in item.keys()
            if prop_name not in ('ref', 'tags')
        ))

        if item_set is None:
            self._all_extra_props_data = all_extra_props_data

        return all_extra_props_data
