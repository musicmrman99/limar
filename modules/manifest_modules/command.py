from graphlib import CycleError, TopologicalSorter

from core.exceptions import LIMARException
from modules.command_utils.command_transformer import CommandTransformer

class Command:
    def __init__(self):
        self._current_command = None
        self._command_tr = CommandTransformer()

    @staticmethod
    def context_type():
        return 'command'

    @staticmethod
    def can_be_root():
        return True

    # Hooks
    # --------------------------------------------------

    def on_enter_context(self, context, *_, **__):
        # Ignore 'requirement' contexts
        if len(context['opts']) == 0:
            return

        # Require command in 'declaration' contexts
        if 'command' not in context['opts']:
            raise LIMARException(
                "A declaration @command context must be given a `command` to"
                " execute"
            )

        command = self._command_tr.parse(context['opts']['command'])

        if self._current_command is not None:
            raise LIMARException(
                "Can only have one nested @query context: tried to nest"
                f" '{self._command_tr.format_text(command)}' inside"
                f" '{self._command_tr.format_text(self._current_command)}'"
            )

        self._current_command = command

    def on_exit_context(self, *_, **__):
        self._current_command = None

    def on_declare_item(self, contexts, item, *_, **__):
        item['tags'].add('command')
        if self._current_command is not None:
            item['command'] = self._current_command

    def on_exit_manifest(self, items, item_sets, *_, **__):
        # Verify that required contexts were declared for all commands
        for item in items.values():
            if (
                'command' in item['tags'] and
                'command' not in item and

                # Ignore any items with a tag that starts with `__`
                all(
                    not name.startswith('__')
                    for name in item['tags'].raw().keys()
                )
            ):
                raise LIMARException(
                    "@command context requires a command to be declared for"
                    f" item '{item['ref']}'"
                )

        # Build the dependency and dependant lists
        for item in items.values():
            if 'command' in item:
                item['command']['dependencies'] = self._dependency_refs_of(item)
                item['command']['dependants'] = (
                    self._dependant_refs_of(item, items)
                )

        # Using the above, build the transitive dependency and dependant lists
        for item in items.values():
            if 'command' in item:
                item['command']['transitiveDependencies'] = (
                    self._transitive_dependency_refs_of(item, items)
                )
                item['command']['transitiveDependants'] = (
                    self._transitive_dependant_refs_of(item, items)
                )

    # Utils
    # --------------------------------------------------

    # FIXME: This is bad coupling to specific modules !!!!!
    #        (but an item knowing its own deps is worth it for now)
    # TODO: These only support `info.query(<ref>)` deps for now

    def _dependency_refs_of(self, item):
        return tuple(
                {
                param[2][0] # 1st item of info.query() args
                for param in item['command']['parameters']
                if param[0:2] == ('info', 'query')
            }.union({
                # 1st item of info.query() args
                subcommand['subcommand'][2][0][0]
                for subcommand in item['command']['subcommands']
                if (
                    subcommand['type'] == 'limar' and
                    subcommand['subcommand'][0:2] == ('info', 'query')
                )
            })
        )

    def _dependant_refs_of(self, item, items):
        return tuple(
            {
                dep_ref
                for dep_ref, dep_item in items.items()
                if 'command' in dep_item and any(
                    param[0:3] == ('info', 'query', (item['ref'],))
                    for param in dep_item['command']['parameters']
                )
            }.union({
                dep_ref
                for dep_ref, dep_item in items.items()
                if 'command' in dep_item and any(
                    subcommand['type'] == 'limar' and
                    subcommand['subcommand'][0:3] ==
                        ('info', 'query', ([item['ref']],))
                    for subcommand in dep_item['command']['subcommands']
                )
            })
        )

    def _transitive_dependency_refs_of(self, item, items) -> tuple[str, ...]:
        """
        Get the set of transitive dependency commands of the given command.
        """

        # Only contains items that are in the directed subgraph starting from
        # the given item.
        sorter = TopologicalSorter({
            dep_ref: items[dep_ref]['command']['dependencies']
            for dep_ref in (
                self._unordered_transitive_dependency_refs_of(item, items)
            )
            if 'command' in items[dep_ref]
        })
        try:
            return tuple(sorter.static_order())
        except CycleError as e:
            raise LIMARException(
                f"Cannot resolve command manifest dependencies due to cycle"
                f" '{e.args[1]}'"
            )

    def _transitive_dependant_refs_of(self, item, items) -> tuple[str, ...]:
        """
        Get the set of transitively dependant commands of the given command.
        """

        # Only contains items that are in the directed subgraph starting from
        # the given item.
        sorter = TopologicalSorter({
            dep_ref: items[dep_ref]['command']['dependants']
            for dep_ref in (
                self._unordered_transitive_dependant_refs_of(item, items)
            )
            if 'command' in items[dep_ref]
        })
        try:
            return tuple(sorter.static_order())
        except CycleError as e:
            raise LIMARException(
                f"Cannot resolve command manifest dependants due to cycle"
                f" '{e.args[1]}'"
            )

    def _unordered_transitive_dependency_refs_of(self,
            item, items
    ) -> tuple[str, ...]:
        dependencies = set()
        for dep_ref in item['command']['dependencies']:
            dependencies.update(
                self._unordered_transitive_dependency_refs_of(
                    items[dep_ref], items
                )
            )
            dependencies.add(dep_ref)
        return tuple(dependencies)

    def _unordered_transitive_dependant_refs_of(self,
            item, items
    ) -> tuple[str, ...]:
        dependants = set()
        for dep_ref in item['command']['dependants']:
            dependants.update(
                self._unordered_transitive_dependant_refs_of(
                    items[dep_ref], items
                )
            )
            dependants.add(dep_ref)
        return tuple(dependants)
