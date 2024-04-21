import os.path
from pathlib import Path
import pickle

class Store():
    def __init__(self, persist_dir='/tmp'):
        self._persist_dir = Path(persist_dir).absolute()
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        self._cache = {}
        self._marked_for_removal = set()

    # Core Methods

    def set(self, key, value):
        self._cache[key] = value
        if key in self._marked_for_removal:
            self._marked_for_removal.remove(key)

    def get(self, key):
        if key not in self._cache:
            try:
                self._cache[key] = pickle.loads(self._path_for(key).read_bytes())
            except OSError as e:
                raise KeyError(f"Key '{key}' not found in this store") from e
        return self._cache[key]

    def remove(self, key):
        if key in self._cache:
            del self._cache[key]
        self._marked_for_removal.add(key)

    def persist(self):
        for key, value in self._cache.items():
            key_path = self._path_for(key)
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(pickle.dumps(value))

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

    def __setitem__(self, key, value):
        self.set(key, value)

    def __getitem__(self, key):
        return self.get(key)

    def __delitem__(self, key):
        self.remove(key)

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        self.flush()

    # Utils

    def _path_for(self, key):
        if len(key) > 0 and key[0] == '/':
            key = key[1:]
        return self._persist_dir / key
