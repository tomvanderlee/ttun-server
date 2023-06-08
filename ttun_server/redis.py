import os

from aioredis import ConnectionPool, Redis


class RedisConnectionPool:
    instance: 'RedisConnectionPool' = None

    def __init__(self):
       self.pool = ConnectionPool.from_url(os.environ.get('REDIS_URL'))

    def __del__(self):
        self.pool.disconnect()

    @classmethod
    def get_connection(cls) -> Redis:
        if cls.instance is None:
            cls.instance = RedisConnectionPool()

        return Redis(connection_pool=cls.instance.pool)
