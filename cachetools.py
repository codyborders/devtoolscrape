import time
from collections import OrderedDict


class TTLCache:
    def __init__(self, maxsize, ttl):
        self.maxsize = int(maxsize)
        self.ttl = float(ttl)
        self._store = OrderedDict()

    def _purge(self):
        now = time.monotonic()
        expired = [key for key, (_, expiry) in self._store.items() if expiry <= now]
        for key in expired:
            self._store.pop(key, None)
        if self.maxsize:
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)

    def get(self, key, default=None):
        self._purge()
        item = self._store.get(key)
        if item is None:
            return default
        value, expiry = item
        if expiry <= time.monotonic():
            self._store.pop(key, None)
            return default
        return value

    def __getitem__(self, key):
        self._purge()
        if key not in self._store:
            raise KeyError(key)
        value, expiry = self._store[key]
        if expiry <= time.monotonic():
            self._store.pop(key, None)
            raise KeyError(key)
        return value

    def __setitem__(self, key, value):
        self._purge()
        expiry = time.monotonic() + self.ttl
        self._store[key] = (value, expiry)
        self._store.move_to_end(key)
        self._purge()

    def __contains__(self, key):
        self._purge()
        return key in self._store

    def __len__(self):
        self._purge()
        return len(self._store)