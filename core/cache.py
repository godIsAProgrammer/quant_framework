"""Cache backend abstractions and implementations."""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import Any, Literal


class CacheBackend(ABC):
    """Abstract cache backend interface."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Get a cached value by key.

        Args:
            key: Cache key.

        Returns:
            Cached value or ``None`` when key is missing/expired.
        """

    @abstractmethod
    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a cached value with optional ttl in seconds."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete one cache key."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return whether a non-expired cache key exists."""


class MemoryCache(CacheBackend):
    """In-memory cache backed by a dictionary with TTL support."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, float | None]] = {}
        self._lock = RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None

            value, expires_at = item
            if self._is_expired(expires_at):
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        expires_at = self._expires_at(ttl)
        with self._lock:
            if ttl is not None and ttl <= 0:
                self._data.pop(key, None)
                return
            self._data[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    @staticmethod
    def _expires_at(ttl: float | None) -> float | None:
        if ttl is None:
            return None
        return time.time() + ttl

    @staticmethod
    def _is_expired(expires_at: float | None) -> bool:
        return expires_at is not None and time.time() >= expires_at


class FileCache(CacheBackend):
    """File-system cache backend with pickle/json serialization and TTL."""

    def __init__(
        self,
        cache_dir: str | Path,
        serializer: Literal["pickle", "json"] = "pickle",
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._serializer = serializer
        self._lock = RLock()

    def get(self, key: str) -> Any | None:
        path = self._path_for_key(key)
        with self._lock:
            if not path.exists():
                return None

            record = self._read_record(path)
            if record is None:
                return None

            expires_at = record.get("expires_at")
            if isinstance(expires_at, (int, float)) and time.time() >= float(
                expires_at
            ):
                path.unlink(missing_ok=True)
                return None

            return record.get("value")

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        path = self._path_for_key(key)
        if ttl is not None and ttl <= 0:
            self.delete(key)
            return

        record = {
            "expires_at": self._expires_at(ttl),
            "value": value,
        }

        with self._lock:
            self._write_record(path, record)

    def delete(self, key: str) -> None:
        path = self._path_for_key(key)
        with self._lock:
            path.unlink(missing_ok=True)

    def clear(self) -> None:
        with self._lock:
            for file in self._cache_dir.glob("cache_*"):
                if file.is_file():
                    file.unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def _path_for_key(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        suffix = ".json" if self._serializer == "json" else ".pkl"
        return self._cache_dir / f"cache_{digest}{suffix}"

    @staticmethod
    def _expires_at(ttl: float | None) -> float | None:
        if ttl is None:
            return None
        return time.time() + ttl

    def _write_record(self, path: Path, record: dict[str, Any]) -> None:
        if self._serializer == "json":
            data = json.dumps(record, ensure_ascii=False).encode("utf-8")
            path.write_bytes(data)
            return

        data = pickle.dumps(record)
        path.write_bytes(data)

    def _read_record(self, path: Path) -> dict[str, Any] | None:
        try:
            if self._serializer == "json":
                text = path.read_text(encoding="utf-8")
                obj = json.loads(text)
            else:
                obj = pickle.loads(path.read_bytes())  # noqa: S301
        except (json.JSONDecodeError, OSError, pickle.PickleError, EOFError):
            return None

        if not isinstance(obj, dict):
            return None
        return obj


class CacheManager:
    """Facade for cache operations on top of a cache backend."""

    def __init__(self, backend: CacheBackend) -> None:
        self.backend = backend

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: float | None = None,
    ) -> Any:
        """Return cached value when hit, otherwise compute and cache it."""
        cached = self.backend.get(key)
        if cached is not None:
            return cached

        value = factory()
        self.backend.set(key, value, ttl)
        return value

    @staticmethod
    def cache_key(prefix: str, *args: Any) -> str:
        """Build deterministic cache key from prefix and arbitrary arguments."""
        payload = "|".join(repr(arg) for arg in args)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"
