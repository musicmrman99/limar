from argparse import Namespace
from typing import Any, Callable, Iterable

class CacheUtils:
    def __init__(self, mod: Namespace):
        self._mod = mod

    def is_enabled(self, command_item):
        return 'cache' in command_item and command_item['cache']['enabled']

    def retention_of(self, command_item):
        return (
            command_item['cache']['retention']
            if 'cache' in command_item
            else 'batch'
        )

    def key(self, *parts):
        return '.'.join(parts).replace('/', '.')+".pickle"

    def with_caching(self,
            key: str,
            fn: Callable,
            args: list[Any] = [],
            invalid_on_run: Iterable[str] = set()
    ):
        try:
            output = self._mod.cache.get(key)
        except KeyError:
            output = fn(*args)
            self._mod.cache.set(key, output)
            self._mod.cache.delete(*invalid_on_run)

        self._mod.log.debug(key, output)
        return output
