import re

from core.store import Store
from core.modulemanager import ModuleAccessor
from core.modules.docs_utils.docs_arg import docs_for

# Types
from typing import Any
from core.envparse import EnvironmentParser
from argparse import ArgumentParser, BooleanOptionalAction, Namespace

class CacheModule:
    """
    MM module to manage cached data.
    """

    # Lifecycle
    # --------------------

    def __init__(self, store: Store | None = None):
        self._store = store

    def dependencies(self):
        return ['log', 'docs']

    def configure_env(self, *, parser: EnvironmentParser, **_):
        parser.add_variable('ROOT')

    def configure_root_args(self, *, parser: ArgumentParser, **_):
        parser.add_argument('--read-cache',
            action=BooleanOptionalAction, default=None,
            help="""Don't read from cache files if they exist.""")

        parser.add_argument('--write-cache',
            action=BooleanOptionalAction, default=None,
            help="""Don't persist the cache on module stop.""")

        parser.add_argument('--cache',
            action=BooleanOptionalAction, default=None,
            help="""
            Short for `--read-cache` and `--write-cache`. Those options override
            this one if they are given.
            """)

        parser.add_argument('--cache-root', default=None,
            help="""Override the cache root to the given value.""")

    def configure_args(self, *, mod: Namespace, parser: ArgumentParser, **_):
        cache_subparsers = parser.add_subparsers(dest="cache_command")

        # Subcommands / List Cache Entires
        list_parser = cache_subparsers.add_parser('list',
            epilog=docs_for(self.list))
        mod.docs.add_docs_arg(list_parser)

        # Subcommands / Show Cache Entry
        show_parser = cache_subparsers.add_parser('show',
            epilog=docs_for(self.get))
        mod.docs.add_docs_arg(show_parser)

        show_parser.add_argument('entry_name', metavar='ENTRY_NAME',
            help="""Name of the entry to show the contents of.""")

        # Subcommands / Delete Cache Entry
        delete_parser = cache_subparsers.add_parser('delete',
            epilog=docs_for(self.delete_and_persist_matching))
        mod.docs.add_docs_arg(delete_parser)

        delete_parser.add_argument('entry_patterns', metavar='ENTRY_PATTERNS',
            nargs='*',
            help="""Regexes to delete the matched entries of.""")

        # Subcommands / Clear Cache
        clear_parser = cache_subparsers.add_parser('clear',
            epilog=docs_for(self.clear_and_persist))
        mod.docs.add_docs_arg(clear_parser)

    def configure(self, *,
            mod: Namespace,
            env: Namespace,
            args: Namespace,
            **_
    ):
        self._mod = mod # For methods that aren't directly given it

        # Create cache store
        if self._store is None:
            if args.cache_root is not None:
                self._store = Store(args.cache_root)
            else:
                self._store = Store(env.ROOT)

        # Enable/disable caching
        self._read_cache = (
            args.read_cache if args.read_cache is not None
            else (
                args.cache if args.cache is not None
                else True
            )
        )
        self._write_cache = (
            args.write_cache if args.write_cache is not None
            else (
                args.cache if args.cache is not None
                else True
            )
        )

    def start(self, *_, **__):
        pass

    def __call__(self, *, args: Namespace, **_) -> Any:
        output = None

        if args.cache_command == 'list':
            output = self.list()

        elif args.cache_command == 'show':
            output = self.get(args.entry_name)

        elif args.cache_command == 'delete':
            output = self.delete_and_persist_matching(*args.entry_patterns)

        elif args.cache_command == 'clear':
            output = self.clear_and_persist()

        return output

    def stop(self, *_, **__):
        self._flush()

    # Invokation
    # --------------------

    @ModuleAccessor.invokable_as_service
    def get_store_str(self):
        """Return a string representation of the cache Store."""

        return str(self._store)

    @ModuleAccessor.invokable_as_service
    def list(self):
        """
        List all cache entries, including those in the cache directory that
        haven't yet been loaded if reading is enabled.
        """

        assert self._store is not None, f'{self.list.__name__}() called before {self.configure.__name__}()'

        return self._store.list(read_persistent=self._read_cache)

    @ModuleAccessor.invokable_as_service
    def get(self, name: str):
        """Get the contents of the cache entry with the given name."""

        assert self._store is not None, f'{self.get.__name__}() called before {self.configure.__name__}()'

        self._store.setattr(name, 'type', 'pickle')
        data = self._store.get(name, read_persistent=self._read_cache)
        self._mod.log.info(
            f"Retrieved cached '{name}' from {self.get_store_str()} ("+(
                "posibly from disk" if self._read_cache
                else "from memory"
            )+")"
        )
        return data

    @ModuleAccessor.invokable_as_service
    def set(self, name: str, data: Any):
        """Set the cache entry with the given name to the given data."""

        assert self._store is not None, f'{self.set.__name__}() called before {self.configure.__name__}()'

        self._store.setattr(name, 'type', 'pickle')
        self._store.set(name, data)
        self._mod.log.info(
            f"Cached '{name}' in {self.get_store_str()} (not yet persisted)"
        )

    @ModuleAccessor.invokable_as_service
    def set_and_persist(self, name: str, data: Any):
        """
        Set the cache entry with the given name to the given data, and persist
        if enabled.
        """

        self.set(name, data)
        self._persist()

    @ModuleAccessor.invokable_as_service
    def delete(self, *names: str):
        """Delete the cache entries with the given names."""

        assert self._store is not None, f'{self.delete.__name__}() called before {self.configure.__name__}()'

        for name in names:
            self._store.delete(name)
            self._store.delattrs(name)
            self._mod.log.info(
                f"Deleted cached '{name}' from {self.get_store_str()} (not yet"
                " persisted)"
            )

    @ModuleAccessor.invokable_as_service
    def delete_and_persist(self, *names: str):
        """
        Delete the cache entries with the given names, and persist if enabled.
        """

        self.delete(*names)
        self._persist()

    @ModuleAccessor.invokable_as_service
    def delete_matching(self, *patterns: str):
        """Delete the cache entries that match the given regex patterns."""

        assert self._store is not None, f'{self.delete.__name__}() called before {self.configure.__name__}()'

        entry_names = self.list()

        names: set[str] = set()
        for pattern in patterns:
            matcher = re.compile(pattern)
            for name in entry_names:
                if matcher.search(name) is not None:
                    names.add(name)

        self.delete(*names)

    @ModuleAccessor.invokable_as_service
    def delete_and_persist_matching(self, *patterns: str):
        """Delete the cache entries that match the given regex patterns."""

        assert self._store is not None, f'{self.delete.__name__}() called before {self.configure.__name__}()'

        self.delete_matching(*patterns)
        self._persist()

    @ModuleAccessor.invokable_as_service
    def clear(self):
        """Delete all cache entries."""

        self.delete(*self.list())
        self._mod.log.info("Deleted all cache entries (not yet persisted)")

    @ModuleAccessor.invokable_as_service
    def clear_and_persist(self):
        """Delete all cache entries, and persist if enabled."""

        self.clear()
        self._persist()

    # Utils
    # --------------------

    def _persist(self):
        """Persist the cache to storage, if writing to the cache is enabled."""

        assert self._store is not None, f'{self._persist.__name__}() called before {self.configure.__name__}()'

        if self._write_cache:
            self._store.persist()
            self._mod.log.info(f"Persisted cache in {self.get_store_str()}")
        else:
            self._mod.log.info(
                f"Did not persist cache in {self.get_store_str()} (writing to"
                " cache is disabled)"
            )

    def _flush(self):
        """
        Flush the cache to storage (ie. persist, then clear the ephemeral
        store) if writing to the cache is enabled.
        """

        assert self._store is not None, f'{self._flush.__name__}() called before {self.configure.__name__}()'

        if self._write_cache:
            self._store.flush()
            self._mod.log.info(f"Flushed cache in {self.get_store_str()}")
        else:
            self._mod.log.info(
                f"Did not flush cache in {self.get_store_str()} (writing to"
                " cache is disabled)"
            )
