from pathlib import Path
import pickle
import re

from core.exceptions import LIMARException

# Types
from typing import Any

class Store:
    def __init__(self, persist_dir: str = '/tmp'):
        self._persist_dir = Path(persist_dir).resolve()
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._cache = {}
        self._attrs = {}
        self._marked_for_removal = set()

    # Attribute Methods

    def setattrs(self, key: str, **attrs: Any):
        self._attrs[key] = attrs

    def getattrs(self, key: str):
        if key not in self._attrs:
            self.setattrs(key)
        return self._attrs[key]

    def delattrs(self, key: str):
        if key in self._attrs:
            del self._attrs[key]

    def setattr(self, key: str, attr_name: str, attr_value: Any):
        attrs = self.getattrs(key)
        attrs[attr_name] = attr_value

    def getattr(self, key: str, attr_name: str):
        attrs = self.getattrs(key)
        if attr_name not in attrs:
            self.setattr(key, attr_name, None)
        return attrs[attr_name]

    # Content Methods

    def list(self,
            pattern: str | None = None,
            read_persistent: bool = True
    ) -> list[str]:
        known_entries = set(self._cache.keys())
        if read_persistent is True:
            known_entries.update(
                str(self._key_for(entry))
                for entry in self._persist_dir.iterdir()
            )

        if pattern is not None:
            regex = re.compile(pattern)
            known_entries = {
                key
                for key in known_entries
                if regex.search(key)
            }

        return sorted(known_entries)

    def get(self, key: str, read_persistent: bool = True):
        if key not in self._cache and read_persistent:
            try:
                key_path = self._path_for(key)
                if self.getattr(key, 'type') == 'pickle':
                    self._cache[key] = pickle.loads(key_path.read_bytes())
                else:
                    self._cache[key] = key_path.read_text()
            except OSError as e:
                raise KeyError(f"Key '{key}' not found in this store") from e
        return self._cache[key]

    def set(self, key: str, value: Any):
        self._cache[key] = value
        if key in self._marked_for_removal:
            self._marked_for_removal.remove(key)

    def delete(self, key: str):
        if key in self._cache:
            del self._cache[key]
        self._marked_for_removal.add(key)

    def persist(self):
        for key, value in self._cache.items():
            key_path = self._path_for(key)
            key_path.parent.mkdir(parents=True, exist_ok=True)

            if self.getattr(key, 'type') == 'pickle':
                key_path.write_bytes(pickle.dumps(value))
            else:
                key_path.write_text(value)

        for key in self._marked_for_removal:
            key_path = self._path_for(key)
            if key_path.exists():
                key_path.unlink()

            # Try to remove parent dirs until a non-empty one is found)
            try:
                for dir in key_path.absolute().parents:
                    if dir == self._persist_dir:
                        break
                    dir.rmdir()
            except OSError:
                pass

        self._marked_for_removal = set()

    def flush(self):
        self.persist()
        self._cache = {}

    # Pythonic Interface

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    def __getitem__(self, key: str):
        return self.get(key)

    def __delitem__(self, key: str):
        self.delete(key)

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        self.flush()

    def __str__(self):
        return f'<Store @ {self._persist_dir}>'

    # Utils

    def _path_for(self, key: str):
        if len(key) > 0 and key[0] == '/':
            key = key[1:]
        key_path = Path(key)

        if '..' in key_path.parts:
            raise LIMARException(
                "Store keys must not contain the special path fragment '..':"
                f" found in key '{key_path}'")

        return (self._persist_dir / key_path).resolve()

    def _key_for(self, key_path: Path):
        if not key_path.is_relative_to(self._persist_dir):
            raise LIMARException(
                f"Could not get key for path '{key_path}': Path is not within"
                f" the Store directory ('{self._persist_dir}')"
            )

        return key_path.relative_to(self._persist_dir)
