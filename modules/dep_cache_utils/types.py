from typing import Any, Callable, TypeVar, TypedDict

T = TypeVar('T')
DictSet = dict[T, None]

# (type, name[, version])
CacheKey = tuple[str, str]
VersionedCacheKey = tuple[str, str, str]
CacheKeyIndex = dict[CacheKey, DictSet[CacheKey]]
VersionedCacheKeyIndex = dict[VersionedCacheKey, DictSet[VersionedCacheKey]]

class ComputableCache(TypedDict):
    latest_vkey: VersionedCacheKey | None
    vkey_is_dirty: bool

class ComputableGraphCache(TypedDict):
    computables: dict[CacheKey, ComputableCache]
    computed_dependencies: VersionedCacheKeyIndex

KeySources = list[tuple[VersionedCacheKey, Any]]
ValueSources = list[Any]

ComputeVersionFn = Callable[[CacheKey, KeySources], str]
ComputeValueFn = Callable[[CacheKey, ValueSources], Any]
SerialiseValueFn = Callable[[Any], Any]
DeserialiseValueFn = Callable[[Any], Any]
