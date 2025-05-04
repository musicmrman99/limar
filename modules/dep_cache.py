from argparse import Namespace
from graphlib import TopologicalSorter
from hashlib import sha1

from core.modulemanager import ModuleAccessor
from modules.dep_cache_utils.types import *

class Computable:
    def __init__(self,
            version_fn: ComputeVersionFn,
            value_fn: ComputeValueFn,
            serialise_fn: SerialiseValueFn,
            deserialise_fn: DeserialiseValueFn,
            cacheable: bool = True
    ):
        self.version_fn: ComputeVersionFn = version_fn
        self.value_fn: ComputeValueFn = value_fn
        self.serialise_fn: SerialiseValueFn = serialise_fn
        self.deserialise_fn: DeserialiseValueFn = deserialise_fn
        self.cacheable = cacheable

        self._latest_vkey: VersionedCacheKey | None = None
        self._vkey_is_dirty = True

    def latest_vkey(self) -> VersionedCacheKey | None:
        return self._latest_vkey

    def set_latest_vkey(self, key: VersionedCacheKey):
        self._latest_vkey = key
        self._vkey_is_dirty = False

    def set_vkey_dirty(self):
        self._vkey_is_dirty = True

    def set_vkey_clean(self):
        self._vkey_is_dirty = False

    def vkey_is_dirty(self):
        return self._vkey_is_dirty

    def raw(self) -> ComputableCache:
        return {
            'latest_vkey': self._latest_vkey,
            'vkey_is_dirty': self._vkey_is_dirty
        }

    def configure_from_raw(self, computable_cache: ComputableCache):
        self._latest_vkey = computable_cache['latest_vkey']
        self._vkey_is_dirty = computable_cache['vkey_is_dirty']

class ComputableGraph:
    def __init__(self, *, mod: Namespace):
        self._mod = mod

        self._computables: dict[CacheKey, Computable] = {}
        self._dependencies: CacheKeyIndex = {}
        self._dependents: CacheKeyIndex = {}
        self._computed_dependencies: VersionedCacheKeyIndex = {}

    def add(self,
            key: CacheKey,
            source_keys: list[CacheKey],
            computable: Computable
    ):
        self._computables[key] = computable

        if key not in self._dependencies:
            self._dependencies[key] = {}
        self._dependencies[key].update({
            key: None
            for key in source_keys
        })

        self._dependents[key] = {}
        for source_key in source_keys:
            self._dependents[source_key][key] = None

    def latest_vkey_for(self, key: CacheKey) -> VersionedCacheKey:
        """
        Get the latest vkey for the given key.

        If the key is clean, return it, otherwise get the vkeys for its
        dependencies (recursively), recompute this vkey, mark all dependent
        vkeys dirty between this key and each key that does not change, and
        return the computed vkey. If getting dependency vkeys results in this
        vkey being marked clean, then return it without recomputing it.

        For example, given A<-B<-C<-D<-E<-F, marking B as dirty will
        mark C, D, E, and F as dirty. On the next call for getting the latest
        vkey for E, the vkeys for C, D, and E start being recomputed. If D
        returns the same key, then E and F are marked as clean, and we skip
        recomputing them.
        """

        latest_vkey = self._computables[key].latest_vkey()

        # Technically, `latest_key is not None` is guaranteed if
        # `not key_is_dirty`, but the type checker doesn't know that, and it's
        # difficult to tell it.
        key_is_dirty = self._computables[key].vkey_is_dirty()
        if not key_is_dirty and latest_vkey is not None:
            return latest_vkey # Base-case: clean

        # Get vkeys for sources, and check if doing so marked this key as clean,
        # eg. if one dep key was dirty, but recomputing it resulted in the same
        # vkey.
        source_vkeys = [
            self.latest_vkey_for(source_key)
            for source_key in self._dependencies[key] # Base-case: empty
        ]

        key_is_dirty = self._computables[key].vkey_is_dirty()
        if not key_is_dirty and latest_vkey is not None:
            return latest_vkey

        # If not, recompute vkey
        sources: KeySources = [
            (source_vkey, self.value_for(source_vkey))
            for source_vkey in source_vkeys
        ]
        version = self._computables[key].version_fn(key, sources)
        computed_vkey = (*key, version)
        self._computables[key].set_latest_vkey(computed_vkey)

        # Mark all dependent vkeys dirty between this key and each key that does
        # not change.
        if latest_vkey != computed_vkey:
            for key in self._transitive_dependents_of(key):
                self._computables[key].set_vkey_dirty()
        else:
            for key in self._transitive_dependents_of(key):
                if all(
                    not self._computables[dep_key].vkey_is_dirty()
                    for dep_key in self._dependencies[key]
                ):
                    self._computables[key].set_vkey_clean()

        return computed_vkey

    def latest_value_for(self, key: CacheKey) -> Any:
        return self.value_for(self.latest_vkey_for(key))

    def value_for(self, vkey: VersionedCacheKey) -> Any:
        key = self._key_for(vkey)

        value = None
        if self._computables[key].cacheable:
            try:
                value = self._computables[key].deserialise_fn(
                    self._mod.cache.get(self._key_str(vkey))
                )
            except KeyError:
                pass

        if value is None:
            if vkey not in self._computed_dependencies:
                self._computed_dependencies[vkey] = {
                    self.latest_vkey_for(source_key): None
                    for source_key in self._dependencies[key]
                }

            sources: ValueSources = [
                self.value_for(source_vkey)
                # Base-case: empty
                for source_vkey in self._computed_dependencies[vkey]
            ]
            value = self._computables[key].value_fn(vkey, sources)

            if self._computables[key].cacheable:
                self._mod.cache.set(
                    self._key_str(vkey),
                    self._computables[key].serialise_fn(value)
                )

        return value

    def raw(self) -> ComputableGraphCache:
        return {
            'computables': {
                cache_key: computable.raw()
                for cache_key, computable in self._computables.items()
            },
            'computed_dependencies': self._computed_dependencies
        }

    def configure_from_raw(self, computable_graph_cache: ComputableGraphCache):
        keys_not_found = 0
        for cache_key, computable_cache in (
            computable_graph_cache['computables'].items()
        ):
            try:
                computable = self._computables[cache_key]
            except KeyError:
                keys_not_found += 1
                self._mod.log.warning(
                    f"dep-cache: cache_key {repr(cache_key)} not found when"
                    " loading from computable graph cache."
                )
                continue

            computable.configure_from_raw(computable_cache)

        if keys_not_found > 0:
            self._mod.log.warning(
                f"dep-cache: The above warnings may indicate a compatiblity"
                " issue with a previous version of LIMAR. If you experience"
                " unexpected behaviour, clearing your cache may help."
            )

        self._computed_dependencies = (
            computable_graph_cache['computed_dependencies']
        )

    def _key_for(self, vkey: VersionedCacheKey) -> CacheKey:
        return vkey[:2]

    def _key_str(self, key: VersionedCacheKey):
        type, name, version = key
        name_str = '.'+name if name != '' else ''
        version_str = '.'+version if version != '' else ''
        return f"{type}{name_str}{version_str}.pickle"

    def _transitive_dependencies_of(self, key: CacheKey):
        # Only contains keys that are in the directed subgraph starting from
        # the given key.
        sorter = TopologicalSorter({
            dep_key: self._dependencies[dep_key]
            for dep_key in self._unordered_transitive_dependencies_of(key)
        })
        # May throw CycleError, but only due to user error
        return list(sorter.static_order())

    def _transitive_dependents_of(self, key: CacheKey):
        # Only contains keys that are in the directed subgraph starting from
        # the given key.
        sorter = TopologicalSorter({
            dep_key: self._dependents[dep_key]
            for dep_key in self._unordered_transitive_dependents_of(key)
        })
        # May throw CycleError, but only due to user error
        return list(sorter.static_order())

    def _unordered_transitive_dependencies_of(self, key: CacheKey):
        dependencies = set()
        for dep_key in self._dependencies[key]:
            dependencies.update(
                self._unordered_transitive_dependencies_of(dep_key)
            )
            dependencies.add(dep_key)
        return dependencies

    def _unordered_transitive_dependents_of(self, key: CacheKey):
        dependents = set()
        for dep_key in self._dependents[key]:
            dependents.update(
                self._unordered_transitive_dependents_of(dep_key)
            )
            dependents.add(dep_key)
        return dependents

class DepCacheModule:
    """
    MM module to manage dependencies between cached data.
    """

    _COMPUTABLE_GRAPH_CACHE_NAME = 'dep_cache.computable_graph_cache.pickle'

    def dependencies(self):
        return ['cache', 'log']

    def configure(self, *, mod: Namespace, **_):
        self._mod = mod # For methods that aren't directly given it
        self._computable_graph = ComputableGraph(mod=mod)

    def start(self, *, mod: Namespace, **_):
        try:
            computable_graph_cache: ComputableGraphCache = mod.cache.get(
                self._COMPUTABLE_GRAPH_CACHE_NAME
            )
        except KeyError:
            return

        self._computable_graph.configure_from_raw(computable_graph_cache)

    def stop(self, *, mod: Namespace, **_):
        mod.cache.set(
            self._COMPUTABLE_GRAPH_CACHE_NAME,
            self._computable_graph.raw()
        )

    # Invokation
    # --------------------

    @staticmethod
    def from_source_versions(key: CacheKey, sources: KeySources):
        if len(sources) == 0:
            return ''
        elif len(sources) == 1:
            return sources[0][0][2]

        combined_version = ''.join(source[0][2] for source in sources)
        return sha1(combined_version.encode('utf-8')).hexdigest()

    @ModuleAccessor.invokable_as_config
    def add(self,
            key: CacheKey,
            source_keys: list[CacheKey],
            compute_value: ComputeValueFn,
            serialise_value: SerialiseValueFn = lambda x: x,
            deserialise_value: DeserialiseValueFn = lambda x: x,
            compute_version: ComputeVersionFn = from_source_versions,
            cacheable: bool = True
    ):
        self._computable_graph.add(
            key,
            source_keys,
            Computable(
                compute_version,
                compute_value,
                serialise_value,
                deserialise_value,
                cacheable=cacheable
            )
        )

    @ModuleAccessor.invokable_as_service
    def get(self, key: CacheKey | VersionedCacheKey):
        """
        Get the contents of the cache entry of the given type with the given
        name, and optionally of the given version.

        If a version is not included in the key, then get the latest version.
        """

        if len(key) == 3:
            return self._computable_graph.value_for(key)
        return self._computable_graph.latest_value_for(key)
