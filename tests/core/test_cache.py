"""Unit tests for cache module (TDD for Day 4)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.cache import CacheManager, FileCache, MemoryCache


def test_memory_cache_set_and_get() -> None:
    """MemoryCache should return value after set."""
    cache = MemoryCache()

    cache.set("foo", {"x": 1}, ttl=10)

    assert cache.get("foo") == {"x": 1}
    assert cache.exists("foo") is True


def test_memory_cache_miss_returns_none() -> None:
    """MemoryCache miss should return None."""
    cache = MemoryCache()

    assert cache.get("missing") is None
    assert cache.exists("missing") is False


def test_memory_cache_ttl_expiration() -> None:
    """MemoryCache should expire keys after ttl."""
    cache = MemoryCache()
    cache.set("short", "ok", ttl=0.1)

    time.sleep(0.2)

    assert cache.get("short") is None
    assert cache.exists("short") is False


def test_memory_cache_delete_and_clear() -> None:
    """MemoryCache should support delete and clear operations."""
    cache = MemoryCache()
    cache.set("a", 1)
    cache.set("b", 2)

    cache.delete("a")
    assert cache.get("a") is None
    assert cache.get("b") == 2

    cache.clear()
    assert cache.get("b") is None


def test_file_cache_persistence_across_instances(tmp_path: Path) -> None:
    """FileCache should persist cache files across instances."""
    cache_dir = tmp_path / "cache"

    writer = FileCache(cache_dir=cache_dir)
    writer.set("persist", {"v": 42}, ttl=10)

    reader = FileCache(cache_dir=cache_dir)
    assert reader.get("persist") == {"v": 42}


def test_file_cache_json_serializer(tmp_path: Path) -> None:
    """FileCache should support JSON serializer mode."""
    cache = FileCache(cache_dir=tmp_path, serializer="json")

    cache.set("json-key", {"a": 1, "b": "x"}, ttl=10)

    assert cache.get("json-key") == {"a": 1, "b": "x"}


def test_file_cache_ttl_expiration(tmp_path: Path) -> None:
    """FileCache should remove expired entries when read."""
    cache = FileCache(cache_dir=tmp_path)
    cache.set("ttl-file", "v", ttl=0.1)

    time.sleep(0.2)

    assert cache.get("ttl-file") is None
    assert cache.exists("ttl-file") is False


def test_cache_manager_get_or_set_and_cache_key() -> None:
    """CacheManager should provide get_or_set and deterministic cache key."""
    manager = CacheManager(backend=MemoryCache())
    calls = 0

    def factory() -> int:
        nonlocal calls
        calls += 1
        return 7

    key = manager.cache_key("kline", "000001", "2026-01-01", 20)
    value1 = manager.get_or_set(key, factory, ttl=10)
    value2 = manager.get_or_set(key, factory, ttl=10)

    assert value1 == 7
    assert value2 == 7
    assert calls == 1
    assert key.startswith("kline:")
    assert key == manager.cache_key("kline", "000001", "2026-01-01", 20)
    assert key != manager.cache_key("kline", "000002", "2026-01-01", 20)


def test_memory_cache_thread_safety_optional() -> None:
    """MemoryCache should be safe for concurrent set/get workloads."""
    cache = MemoryCache()

    def worker(i: int) -> int | None:
        key = f"k-{i}"
        cache.set(key, i, ttl=5)
        value = cache.get(key)
        if isinstance(value, int):
            return value
        return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker, range(100)))

    assert results == list(range(100))
