from collections.abc import AsyncIterable

from aiohttp_client_cache import BaseCache, CacheBackend, ResponseOrKey
from aiohttp_client_cache.docs import extend_init_signature

import pylav.sql.tables.cache


def postgres_template():
    pass


@extend_init_signature(CacheBackend, postgres_template)
class PostgresCacheBackend(CacheBackend):
    """Wrapper for higher-level cache operations.
    In most cases, the only thing you need to specify here is which storage class(es) to use"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.redirects = PostgresStorage(**kwargs)
        self.responses = PostgresStorage(**kwargs)


class PostgresStorage(BaseCache):
    """interface for lower-level backend storage operations"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def contains(self, key: str) -> bool:
        """Check if a key is stored in the cache"""
        return await pylav.sql.tables.cache.AioHttpCacheRow.exists().where(
            pylav.sql.tables.cache.AioHttpCacheRow.key == key
        )

    async def clear(self) -> None:
        """Delete all items from the cache"""
        await pylav.sql.tables.cache.AioHttpCacheRow.raw("TRUNCATE TABLE aiohttp_client_cache")

    async def delete(self, key: str) -> None:
        """Delete an item from the cache"""
        await pylav.sql.tables.cache.AioHttpCacheRow.delete().where(pylav.sql.tables.cache.AioHttpCacheRow.key == key)

    async def keys(self) -> AsyncIterable[str]:
        """Get all keys stored in the cache"""
        for entry in await pylav.sql.tables.cache.AioHttpCacheRow.select(
            pylav.sql.tables.cache.AioHttpCacheRow.key
        ).output(load_json=True, nested=True):
            yield entry["key"]

    async def read(self, key: str) -> ResponseOrKey:
        """Read an item from the cache"""
        response = (
            await pylav.sql.tables.cache.AioHttpCacheRow.select(pylav.sql.tables.cache.AioHttpCacheRow.value)
            .where(pylav.sql.tables.cache.AioHttpCacheRow.key == key)
            .first()
            .output(load_json=True, nested=True)
        )
        return self.deserialize(response["value"]) if response else None

    async def size(self) -> int:
        """Get the number of items in the cache"""
        return await pylav.sql.tables.cache.AioHttpCacheRow.count()

    def values(self) -> AsyncIterable[ResponseOrKey]:
        """Get all values stored in the cache"""
        return self._values()

    async def _values(self) -> AsyncIterable[ResponseOrKey]:
        for entry in await pylav.sql.tables.cache.AioHttpCacheRow.select(
            pylav.sql.tables.cache.AioHttpCacheRow.value
        ).output(load_json=True, nested=True):
            yield self.deserialize(entry["value"])

    async def write(self, key: str, item: ResponseOrKey):
        """Write an item to the cache"""
        # TODO: When piccolo add support to on conflict clauses using RAW here is more efficient
        #  Tracking issue: https://github.com/piccolo-orm/piccolo/issues/252
        await pylav.sql.tables.cache.AioHttpCacheRow.raw(
            """
            INSERT INTO aiohttp_client_cache (key, value)
            VALUES ({}, {})
            ON CONFLICT (key) DO NOTHING
            """,
            key,
            self.serialize(item),
        )

    async def bulk_delete(self, keys: set[str]) -> None:
        """Delete multiple items from the cache"""
        await pylav.sql.tables.cache.AioHttpCacheRow.delete().where(
            pylav.sql.tables.cache.AioHttpCacheRow.key.is_in(list(keys))
        )
