import os

from redis.asyncio import ConnectionPool, Redis


class RedisConnectionPool:
    _pool: ConnectionPool | None = None

    @classmethod
    def get_connection(cls) -> Redis:
        if cls._pool is None:
            cls._pool = ConnectionPool.from_url(os.environ.get('REDIS_URL'))
        return Redis(connection_pool=cls._pool)