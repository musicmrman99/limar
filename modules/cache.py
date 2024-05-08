from core.store import Store

# Types
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
        return ['log']

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

    # TODO: Allow inspecting, clearing, and otherwise managing the cache via the
    #       CLI.
    #def configure_args(self, *, parser: ArgumentParser, **_):

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
                self._store = Store(env.VCS_CACHE_ROOT)

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

    def stop(self, *_, mod: Namespace, **__):
        if self._write_cache:
            assert self._store is not None, 'CacheModule.stop() called before CacheModule.configure()'
            self._store.flush()
            mod.log().info(f"Flushed cache in {self.get_store_str()}")
        else:
            mod.log().info(
                f"Did not flush cache in {self.get_store_str()} (writing to"
                " cache is disabled)"
            )

    # Invokation
    # --------------------

    def get_store_str(self):
        return str(self._store)

    def set(self, name, data):
        assert self._store is not None, 'CacheModule.set() called before CacheModule.configure()'
        self._store.setattr(name, 'type', 'pickle')
        self._store.set(name, data)
        self._mod.log().info(
            f"Cached '{name}' in {self.get_store_str()} (not yet persisted)"
        )

    def get(self, name):
        assert self._store is not None, 'CacheModule.get() called before CacheModule.configure()'
        self._store.setattr(name, 'type', 'pickle')
        data = self._store.get(name, read_persistent=self._read_cache)
        self._mod.log().info(
            f"Retrieved cached '{name}' from {self.get_store_str()} ("+(
                "posibly from disk" if self._read_cache
                else "from memory"
            )+")"
        )
        return data

    def delete(self, name):
        assert self._store is not None, 'CacheModule.delete() called before CacheModule.configure()'
        self._store.delete(name)
        self._store.delattrs(name)
        self._mod.log().info(
            f"Deleted cached '{name}' from {self.get_store_str()} (not yet"
            " persisted)"
        )
