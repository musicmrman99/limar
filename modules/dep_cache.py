from argparse import Namespace
from collections import defaultdict
from hashlib import sha1
from typing import Any, Callable, TypedDict
from core.modulemanager import ModuleAccessor

# (type, name[, version])
CacheKey = tuple[str, str]
VersionedCacheKey = tuple[str, str, str]
CacheKeyIndex = dict[CacheKey, dict[CacheKey, None]]

class _ComputableCache(TypedDict):
    latest_key: VersionedCacheKey | None
    key_is_dirty: bool
_ComputablesCache = dict[CacheKey, _ComputableCache]

# {
#   cache_key: {cache_key: None, ...},
#   versioned_cache_key: {versioned_cache_key: None, ...},
#   ...
# }
ComputeVersionFn = Callable[..., str]
ComputeValueFn = Callable[..., Any]

class Computable:
    def __init__(self,
            version_fn: ComputeVersionFn,
            value_fn: ComputeValueFn,
            cacheable: bool = True
    ):
        self.version_fn: ComputeVersionFn = version_fn
        self.value_fn: ComputeValueFn = value_fn
        self.cacheable = cacheable

        self.latest_key: VersionedCacheKey | None = None
        self.key_is_dirty = True

class DepCacheModule:
    """
    MM module to manage dependencies between cached data.
    """

    _COMPUTABLES_CACHE_NAME = 'dep_cache.computables_cache.pickle'

    def __init__(self):
        self._computables: dict[CacheKey, Computable] = {}

        self._dependencies: CacheKeyIndex = defaultdict(lambda: {})
        self._dependents: CacheKeyIndex = defaultdict(lambda: {})

    def dependencies(self):
        return ['cache']

    def configure(self, *, mod: Namespace, **_):
        self._mod = mod # For methods that aren't directly given it

    def start(self, *, mod: Namespace, **_):
        try:
            key_state: _ComputablesCache = mod.cache.get(
                self._COMPUTABLES_CACHE_NAME
            )
        except KeyError:
            return

        for cache_key, computable_cache in key_state.items():
            try:
                computable = self._computables[cache_key]
                computable.latest_key = computable_cache['latest_key']
                computable.key_is_dirty = computable_cache['key_is_dirty']
            except KeyError:
                # Likely due to changes to LIMAR modules or _ComputablesCache.
                # Try to ignore them. If this results in strange behaviour, it
                # is recommended to delete the key cache entry entirely to
                # recompute everything.
                pass

    def stop(self, *, mod: Namespace, **_):
        key_state: _ComputablesCache = {
            cache_key: {
                'latest_key': computable.latest_key,
                'key_is_dirty': computable.key_is_dirty
            }
            for cache_key, computable in self._computables.items()
        }
        mod.cache.set(self._COMPUTABLES_CACHE_NAME, key_state)

    # Invokation
    # --------------------

    @staticmethod
    def _digest_for(value: str):
        return sha1(value.encode('utf-8')).hexdigest()

    @classmethod
    def _default_version_fn(cls, *sources):
        if len(sources) == 0:
            return ''
        elif len(sources) == 1:
            return sources[0][0]
        return cls._digest_for(
            ''.join(*(str(source[0]) for source in sources))
        )

    @ModuleAccessor.invokable_as_service
    def set(self,
            key: CacheKey,
            source_keys: list[CacheKey],
            compute_value: ComputeValueFn,
            compute_version: ComputeVersionFn = _default_version_fn,
            cacheable: bool = True
    ):
        self._computables[key] = Computable(
            compute_version,
            compute_value,
            cacheable=cacheable
        )

        self._dependencies[key].update({
            key: None
            for key in source_keys
        })
        for source_key in source_keys:
            self._dependents[source_key][key] = None

    @ModuleAccessor.invokable_as_service
    def get(self, key: CacheKey | VersionedCacheKey):
        """
        Get the contents of the cache entry of the given type with the given
        name, and optionally of the given version.

        If a version is not included in the key, then get the latest version.
        """

        cache_key = self._get_key(key)
        sources = None

        # Get vkey
        if len(key) == 3:
            versioned_key = key
            key_is_dirty = False
        else:
            versioned_key = self._computables[cache_key].latest_key
            key_is_dirty = self._computables[cache_key].key_is_dirty

        if key_is_dirty or versioned_key is None:
            # Recompute vkey
            sources = [
                self.get(source_key)
                for source_key in self._dependencies[cache_key]
            ]
            version = self._computables[cache_key].version_fn(sources)
            versioned_key = (*cache_key, version)

            # Set new vkey and invalidate dependent vkeys
            prev_versioned_key = self._computables[cache_key].latest_key
            self._computables[cache_key].latest_key = versioned_key
            self._computables[cache_key].key_is_dirty = False

            if prev_versioned_key != versioned_key:
                pass # Invalidate dependent keys

        # Get value
        value = None
        if self._computables[cache_key].cacheable:
            try:
                value = self._mod.cache.get(self._key_str(versioned_key))
            except KeyError:
                pass

        if value is None:
            if sources is None:
                sources = [
                    self.get(source_key)
                    for source_key in self._dependencies[cache_key]
                ]
            value = self._computables[cache_key].value_fn(*(
                source[1] for source in sources
            ))

            if self._computables[cache_key].cacheable:
                self._mod.cache.set(self._key_str(versioned_key), value)

            # Unset the now-unknown latest keys for all dependents

            # if the version number has changed
            # AND the item is cacheable
            # AND the cache is missing
            # - recurse through dependencies, setting latest_key to None

            # Invalidate dependents

        return (versioned_key, value)

    @ModuleAccessor.invokable_as_service
    def delete(self, key: CacheKey | VersionedCacheKey):
        if key not in self._computables:
            return # Wasn't set using dep-cache, so don't touch it

        # TODO: Invalidation chain

    # Utils
    # --------------------

    def _key_str(self, key: VersionedCacheKey):
        type, name, version = key
        return f"{type}.{name}.{version}.pickle"

    def _get_key(self, key: CacheKey | VersionedCacheKey) -> CacheKey:
        return key[:2]
